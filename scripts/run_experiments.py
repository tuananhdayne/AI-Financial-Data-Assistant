import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../src'))
import os
import sys
import shutil
import subprocess
import time

# Configure stdout to UTF-8
sys.stdout.reconfigure(encoding='utf-8')

def clean_temp_files():
    partial_path = 'd:/ROAD_AI/submission_partial.json'
    if os.path.exists(partial_path):
        try:
            os.remove(partial_path)
            print(f"Đã xoá tệp tạm: {partial_path}")
        except Exception as e:
            print(f"Không thể xoá tệp tạm: {e}")

def run_experiment(name, env_vars, resume=True):
    print(f"\n======================================================================")
    print(f"BẮT ĐẦU THỬ NGHIỆM: {name}")
    print(f"Cấu hình môi trường: {env_vars}")
    print(f"======================================================================\n")
    
    # Xoá file partial chỉ khi không chọn resume
    if not resume:
        clean_temp_files()
    else:
        print("  -> Đang khôi phục (Resume) tiến trình từ kết quả đã lưu trong submission_partial.json...")
    
    # Thiết lập biến môi trường hiện tại
    current_env = os.environ.copy()
    for k, v in env_vars.items():
        current_env[k] = v
        
    start_time = time.time()
    
    # Thực thi subprocess run_pipeline_all.py
    try:
        process = subprocess.Popen(
            [sys.executable, os.path.join(os.path.dirname(__file__), 'run_pipeline_all.py')],
            env=current_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding='utf-8'
        )
        
        # Đọc và in log đầu ra trực tiếp
        while True:
            output = process.stdout.readline()
            if output == '' and process.poll() is not None:
                break
            if output:
                # In ra log của tiến trình con để người dùng theo dõi
                sys.stdout.write(output)
                sys.stdout.flush()
                
        rc = process.poll()
        if rc != 0:
            print(f"\n[Error]: Tiến trình chạy thử nghiệm {name} kết thúc với mã lỗi {rc}!")
            return False
            
    except Exception as e:
        print(f"\n[Error]: Phát sinh lỗi khi chạy thử nghiệm {name}: {e}")
        return False
        
    duration = time.time() - start_time
    print(f"\nThử nghiệm {name} HOÀN THÀNH sau {duration:.2f} giây (~{duration/60:.2f} phút).")
    # Giữ nguyên 1-index gốc như đặc tả vàng của BTC (không dịch chuyển chỉ mục)
    sub_json = 'd:/ROAD_AI/submission.json'
    sub_zip = 'd:/ROAD_AI/submission.zip'
    
    dest_json = f'd:/ROAD_AI/submission_{name.lower().replace(" ", "_")}.json'
    dest_zip = f'd:/ROAD_AI/submission_{name.lower().replace(" ", "_")}.zip'
    
    if os.path.exists(sub_json):
        shutil.copy(sub_json, dest_json)
        print(f"  -> Lưu tệp JSON: {dest_json}")
    if os.path.exists(sub_zip):
        shutil.move(sub_zip, dest_zip)
        print(f"  -> Di chuyển tệp ZIP nộp bài: {dest_zip}")
        
    # Tự động tạo thêm bản startline tương ứng
    create_startline_submission(name)
        
    return True

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
    import shutil
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

def create_startline_submission(name):
    clean_name = name.lower().replace(" ", "_")
    input_json = f'd:/ROAD_AI/submission_{clean_name}.json'
    output_json = f'd:/ROAD_AI/submission_{clean_name}_startline.json'
    output_zip = f'd:/ROAD_AI/submission_{clean_name}_startline.zip'
    metadata_path = 'd:/ROAD_AI/metadata.json'
    temp_dir = f'd:/ROAD_AI/temp_startline_{clean_name}'
    
    if not os.path.exists(input_json):
        print(f"  -> [Warning] Không tìm thấy tệp {input_json} để chuyển sang startline!")
        return
        
    print(f"  -> Đang chuyển đổi vị trí bảng sang start_line cho {name}...")
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)
    os.makedirs(temp_dir, exist_ok=True)
    
    import json
    import re
    import zipfile
    
    with open(metadata_path, 'r', encoding='utf-8') as f:
        metadata_db = json.load(f)
    metadata_map = {}
    for item in metadata_db:
        rep_id = item['report_id']
        tbl_idx = item['table_index']
        metadata_map[(rep_id, tbl_idx)] = item['start_line']
        
    with open(input_json, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    new_data = []
    for item in data:
        new_item = item.copy()
        new_tables = []
        for tbl in item.get("relevant_tables", []):
            if "|" in tbl:
                doc_id, tbl_idx_str = tbl.split("|")
                try:
                    tbl_idx = int(tbl_idx_str)
                    start_line = metadata_map.get((doc_id, tbl_idx))
                    if start_line is not None:
                        new_tables.append(f"{doc_id}|{start_line}")
                    else:
                        new_tables.append(tbl)
                except ValueError:
                    new_tables.append(tbl)
            else:
                new_tables.append(tbl)
        new_item["relevant_tables"] = new_tables
        
        for ev in item.get("evidence", []):
            csv_path = ev["csv_path"]
            csv_base = os.path.basename(csv_path)
            src_file = os.path.join('d:/ROAD_AI/data', csv_base)
            dest_file = os.path.join(temp_dir, csv_base)
            if os.path.exists(src_file):
                clean_csv_file(src_file, dest_file)
                
        new_data.append(new_item)
        
    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump(new_data, f, ensure_ascii=False, indent=2)
        
    if os.path.exists(output_zip):
        os.remove(output_zip)
        
    with zipfile.ZipFile(output_zip, 'w', zipfile.ZIP_DEFLATED) as z:
        z.write(output_json, 'submission.json')
        for root, dirs, files in os.walk(temp_dir):
            for file in files:
                file_path = os.path.join(root, file)
                z.write(file_path, f"data/{file}")
                
    shutil.rmtree(temp_dir)
    print(f"  -> Đã lưu bản startline thành công tại: {output_zip}")

def main():
    experiments = [
        # Thử nghiệm 1: Hybrid RAG (Đầy đủ tính năng tốt nhất hiện tại)
        {
            "name": "Hybrid RAG",
            "env": {
                "USE_CODE_BOOSTER": "True",
                "USE_DETERMINISTIC_GEN": "True"
            }
        }
    ]
    
    print("======================================================================")
    print("KỊCH BẢN CHẠY LUÂN PHIÊN CÁC THỬ NGHIỆM ĐỂ TREO MÁY QUA ĐÊM")
    print("Danh sách các thử nghiệm sẽ chạy lần lượt:")
    for idx, exp in enumerate(experiments):
        print(f"  {idx+1}. {exp['name']}: {exp['env']}")
    print("======================================================================\n")
    
    # Chạy lần lượt (Mặc định chọn resume=True để bảo lưu tiến độ)
    for exp in experiments:
        success = run_experiment(exp["name"], exp["env"], resume=True)
        if not success:
            print(f"Thử nghiệm {exp['name']} thất bại. Chuyển sang thử nghiệm tiếp theo...")
            
    print("\n======================================================================")
    print("TẤT CẢ THỬ NGHIỆM QUA ĐÊM ĐÃ HOÀN THÀNH!")
    print("Các tệp ZIP kết quả sẵn sàng nộp bài trong thư mục d:/ROAD_AI/:")
    print("  1. submission_hybrid_rag.zip")
    print("  2. submission_llm_only.zip")
    print("  3. submission_bm25_only.zip")
    print("Hãy so sánh điểm số của cả 3 cấu hình trên Bảng xếp hạng ngày mai!")
    print("======================================================================")

if __name__ == '__main__':
    main()
