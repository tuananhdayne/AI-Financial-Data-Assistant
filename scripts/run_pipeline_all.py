import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../src'))
import os
import sys
import json
import shutil
import zipfile
import traceback
import time
from tqdm import tqdm

# Configure stdout to UTF-8
sys.stdout.reconfigure(encoding='utf-8')

# Import our pipeline modules
try:
    from intent_analyzer import build_target_description
    from hard_filter import apply_hard_filter
    from retriever import retrieve_relevant_tables
    from query_generator import generate_pandas_query
    from python_engine import execute_and_correct_query
except ImportError as e:
    print(f"Lỗi import các module pipeline: {e}")
    sys.exit(1)

def process_single_question(question_item, metadata_db):
    q_id = question_item.get("id")
    question_text = question_item.get("question")
    
    result = {
        "id": q_id,
        "question": question_text,
        "answer": 0.0,
        "relevant_docs": [],
        "relevant_tables": [],
        "evidence": [],
        "pandas_query": ""
    }
    
    used_csv_files = []
    
    try:
        # 1. Intent Analysis
        target_desc = build_target_description(question_text)
        
        # 2. Hard Filtering
        candidates = apply_hard_filter(target_desc, metadata_db)
        
        # 3. Retrieval (Dynamic top_n: 3 by default, higher for multi-year)
        years = target_desc.get("year")
        if isinstance(years, list):
            top_n = max(3, len(years))
        else:
            top_n = 3
        retrieved = retrieve_relevant_tables(target_desc, candidates, top_n=top_n)
        
        if retrieved:
            result["relevant_docs"] = list(set([r['report_id'] for r in retrieved]))
            result["relevant_tables"] = [f"{r['report_id']}|{r['start_line']}" for r in retrieved]
            
            evidence_list = []
            for idx, r in enumerate(retrieved):
                var_name = f"df{idx+1}"
                csv_name = os.path.basename(r['csv_path'])
                evidence_list.append({
                    "variable": var_name,
                    "csv_path": f"data/{csv_name}"
                })
                used_csv_files.append(r['csv_path'])
                
            result["evidence"] = evidence_list
            
            # 4. Generate Pandas Query
            pandas_query = generate_pandas_query(target_desc, retrieved)
            
            if pandas_query:
                # 5. Execution & Self-Correction (max_retries=4 for thoroughness)
                answer, final_query = execute_and_correct_query(target_desc, retrieved, pandas_query, max_retries=4)
                
                if answer is not None:
                    result["answer"] = float(answer)
                result["pandas_query"] = final_query if final_query else pandas_query
            else:
                result["pandas_query"] = ""
                
    except Exception as e:
        print(f"\n[Error processing Question #{q_id}]: {e}")
        
    return result, used_csv_files

def main():
    questions_path = 'd:/ROAD_AI/questions/questions_full.jsonl'
    metadata_path = 'd:/ROAD_AI/metadata.json'
    partial_results_path = 'd:/ROAD_AI/submission_partial.json'
    output_json_path = 'd:/ROAD_AI/submission_final.json'
    output_zip_path = 'd:/ROAD_AI/submission_final.zip'
    
    # 1. Load Data
    if not os.path.exists(questions_path):
        print(f"Error: Không tìm thấy file câu hỏi {questions_path}!")
        return
        
    if not os.path.exists(metadata_path):
        print(f"Error: Không tìm thấy file metadata.json!")
        return
        
    print("Đang tải dữ liệu metadata...")
    with open(metadata_path, 'r', encoding='utf-8') as f:
        metadata_db = json.load(f)
        
    print("Đang tải tập câu hỏi thi...")
    questions = []
    with open(questions_path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                questions.append(json.loads(line))
                
    total_q = len(questions)
    print(f"Tổng số câu hỏi cần dự đoán: {total_q}")
    
    # 2. Hỗ trợ RESUME (Đọc kết quả đã chạy từ trước)
    completed_results = {}
    all_used_csvs = set()
    
    if os.path.exists(partial_results_path):
        try:
            with open(partial_results_path, 'r', encoding='utf-8') as f:
                saved_data = json.load(f)
                for item in saved_data:
                    q_id = item["id"]
                    completed_results[q_id] = item
                    # Khôi phục danh sách file CSV đã dùng
                    for ev in item.get("evidence", []):
                        csv_path = ev.get("csv_path")
                        if csv_path:
                            # Chuyển đổi từ 'data/filename.csv' về 'data/filename.csv' cục bộ
                            # File nằm ở thư mục ROAD_AI/data/
                            csv_base = os.path.basename(csv_path)
                            all_used_csvs.add(f"data/{csv_base}")
            print(f"Đã tải {len(completed_results)} câu hỏi đã xử lý xong trước đó. Sẽ chạy tiếp tục...")
        except Exception as e:
            print(f"Không thể đọc file submission_partial.json ({e}). Bắt đầu lại từ đầu.")
            completed_results = {}
            
    # 3. Chạy vòng lặp TUẦN TỰ (Sequential) để bảo vệ LM Studio khỏi bị crash/500
    print("\nBắt đầu chạy dự đoán toàn bộ câu hỏi (Tuần tự)...")
    
    try:
        for q in tqdm(questions, desc="Processing Questions"):
            q_id = q.get("id")
            
            # Bỏ qua nếu đã có kết quả
            if q_id in completed_results:
                continue
                
            res, csvs = process_single_question(q, metadata_db)
            completed_results[q_id] = res
            all_used_csvs.update(csvs)
            
            # Ghi tiến độ tức thời ra file submission_partial.json
            with open(partial_results_path, 'w', encoding='utf-8') as f:
                json.dump(list(completed_results.values()), f, ensure_ascii=False, indent=2)
                
            # Nghỉ ngắn giữa các câu để tránh nghẽn GPU
            time.sleep(0.05)
            
    except KeyboardInterrupt:
        print("\nTiến trình bị dừng bởi người dùng. Đã lưu tiến độ hiện tại.")
        sys.exit(0)
        
    # 4. Sắp xếp lại danh sách kết quả theo thứ tự ID câu hỏi gốc
    ordered_results = []
    for q in questions:
        q_id = q.get("id")
        if q_id in completed_results:
            ordered_results.append(completed_results[q_id])
        else:
            # Fallback nếu thiếu câu
            ordered_results.append({
                "id": q_id,
                "question": q.get("question"),
                "answer": 0.0,
                "relevant_docs": [],
                "relevant_tables": [],
                "evidence": [],
                "pandas_query": ""
            })
            
    # Ghi file kết quả submission.json cuối cùng
    print(f"\nGhi file kết quả nộp bài cuối cùng: {output_json_path}")
    with open(output_json_path, 'w', encoding='utf-8') as f:
        json.dump(ordered_results, f, ensure_ascii=False, indent=2)
        
    # AUTOMATIC RERUN FOR ZERO ANSWERS VIA DEEP FALLBACK
    print("\n--- BẮT ĐẦU QUÉT VÀ RERUN TỰ ĐỘNG CÁC CÂU CÓ ĐÁP ÁN 0.0 ---")
    try:
        from scratch.rerun_zero_answers_deep_fallback import rerun_zero_answers
        rerun_zero_answers(output_json_path)
    except Exception as e_rerun:
        print(f"Warning: Không thể rerun tự động các câu 0.0 ({e_rerun}). Tiến hành nén ZIP trực tiếp.")
        
    # 5. Đóng gói ZIP nộp bài theo chuẩn BTC
    print("\n--- BẮT ĐẦU ĐÓNG GÓI ZIP NỘP BÀI ---")
    temp_dir = 'd:/ROAD_AI/temp_submission'
    temp_data_dir = os.path.join(temp_dir, 'data')
    
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)
    os.makedirs(temp_data_dir, exist_ok=True)
    
    # Sao chép submission.json
    shutil.copy(output_json_path, os.path.join(temp_dir, 'submission.json'))
    
def find_column_indices(df):
    cols = list(df.columns)
    code_col = None
    item_col = '0'
    val_col = '1'
    for idx in range(min(len(df), 3)):
        row_vals = [str(df.iloc[idx, c]).strip().lower() for c in range(len(df.columns))]
        for c_idx, val in enumerate(row_vals):
            if 'mã số' in val or 'ma so' in val or 'code' in val:
                code_col = str(cols[c_idx])
            elif 'chỉ tiêu' in val or 'chi tieu' in val or 'item' in val:
                item_col = str(cols[c_idx])
    if len(cols) == 3:
        if '1' in df.columns:
            col1_vals = df['1'].dropna().astype(str).str.strip().tolist()
            small_digits = [v for v in col1_vals if v.replace('.', '').isdigit() and len(v.replace('.', '')) <= 3]
            non_empty = [v for v in col1_vals if v != '']
            if len(non_empty) > 0 and len(small_digits) / len(non_empty) > 0.5:
                code_col = '1'
                val_col = '2'
            else:
                code_col = None
                val_col = '1'
        else:
            code_col = None
            val_col = '1'
    elif '3' in cols:
        val_col = '3'
    return code_col, item_col, val_col

def clean_csv_file(src_path, dest_path):
    import pandas as pd
    try:
        df = pd.read_csv(src_path)
        df.columns = [str(i) for i in range(len(df.columns))]
        code_col, item_col, val_col = find_column_indices(df)
        
        garbage_values = {'-', '–', 'N/A', 'n/a', '', 'nan', 'NaN', 'null', 'None'}
        
        def clean_val(x):
            if pd.isna(x):
                return '0'
            s = str(x).strip()
            if not s or s in garbage_values:
                return '0'
            
            is_negative = False
            if s.startswith('(') and s.endswith(')'):
                s = s[1:-1].strip()
                is_negative = True
                
            try:
                if '.' in s and ',' in s:
                    dot_idx = s.find('.')
                    comma_idx = s.find(',')
                    if dot_idx < comma_idx:
                        s_clean = s.replace('.', '').replace(',', '.')
                    else:
                        s_clean = s.replace(',', '')
                elif ',' in s:
                    parts = s.split(',')
                    if len(parts) == 2 and len(parts[1]) <= 2:
                        s_clean = s.replace(',', '.')
                    else:
                        s_clean = s.replace(',', '')
                else:
                    s_clean = s
                    
                val_float = float(s_clean)
                if is_negative:
                    val_float = -val_float
                return f"{val_float:.6f}".rstrip('0').rstrip('.') if '.' in f"{val_float:.6f}" else f"{val_float}"
            except ValueError:
                return s
                
        for col in df.columns:
            if col == item_col or col == code_col:
                df[col] = df[col].fillna('').astype(str).str.strip()
            else:
                df[col] = df[col].map(clean_val)
                
        df.to_csv(dest_path, index=False)
    except Exception as e:
        print(f"  -> [Error cleaning CSV {src_path}]: {e}")
        shutil.copy2(src_path, dest_path)

    # Sao chép chỉ các file CSV được tham chiếu
    print(f"Làm sạch và sao chép {len(all_used_csvs)} file CSV được sử dụng sang thư mục tạm...")
    for csv_rel in all_used_csvs:
        src_path = os.path.join('d:/ROAD_AI', csv_rel)
        dest_path = os.path.join(temp_data_dir, os.path.basename(csv_rel))
        if os.path.exists(src_path):
            clean_csv_file(src_path, dest_path)
        elif os.path.exists(os.path.join('d:/ROAD_AI/data', os.path.basename(csv_rel))):
            clean_csv_file(os.path.join('d:/ROAD_AI/data', os.path.basename(csv_rel)), dest_path)
            
    # Tạo file ZIP
    print(f"Đang nén file nộp bài vào {output_zip_path}...")
    if os.path.exists(output_zip_path):
        os.remove(output_zip_path)
        
    with zipfile.ZipFile(output_zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        zipf.write(os.path.join(temp_dir, 'submission.json'), 'submission.json')
        for root, dirs, files in os.walk(temp_data_dir):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.join('data', file)
                zipf.write(file_path, arcname)
                
    # Dọn dẹp thư mục temp và file partial nếu chạy xong hoàn toàn
    shutil.rmtree(temp_dir)
    if os.path.exists(partial_results_path):
        os.remove(partial_results_path)
        
    print(f"\n=== ĐÃ HOÀN THÀNH ĐÓNG GÓI THÀNH CÔNG! ===")
    print(f"Đường dẫn file ZIP nộp bài của bạn: {output_zip_path}")
    print(f"Hãy tải file submission.zip lên Dashboard tại http://leaderboard.aiguru.com.vn/")

if __name__ == '__main__':
    main()
