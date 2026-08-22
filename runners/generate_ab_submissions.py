import sys
import os
import json
import zipfile
import shutil
from tqdm import tqdm

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))

from station1_doc_filter import filter_documents_for_question
from station2_table_retriever import retrieve_tables_for_question

def process_ab_questions(questions, metadata_db):
    list_index = []
    list_line = []
    
    copied_csvs = set()
    
    for item in tqdm(questions, desc="Generating A/B Submissions (Index vs Line)"):
        q_id = item["id"]
        q_text = item["question"]
        
        t1_res = filter_documents_for_question(q_text, metadata_db)
        target_desc = t1_res["target_description"]
        
        years = target_desc.get("year", [])
        tickers = target_desc.get("ticker", [])
        formula = target_desc.get("formula_applied")
        q_lower = q_text.lower()
        
        is_formula_q = (formula is not None) or any(kw in q_lower for kw in ['roe', 'roa', 'biên lợi nhuận', 'd/e', 'thanh toán', 'cfo margin', 'vốn lưu động', 'nwc', 'vòng quay', 'sg&a', 'tỷ lệ nợ', 'nợ nần'])
        is_multi_year = isinstance(years, list) and len(years) > 1
        is_multi_ticker = isinstance(tickers, list) and len(tickers) > 1
        
        if is_formula_q:
            calc_top_n = 4
        elif is_multi_year:
            calc_top_n = max(4, len(years) * 2)
        elif is_multi_ticker:
            calc_top_n = max(4, len(tickers) * 2)
        else:
            calc_top_n = 2
            
        t2_res = retrieve_tables_for_question(target_desc, t1_res["candidate_tables"], top_n=calc_top_n)
        retrieved = t2_res["retrieved_tables"]
        relevant_docs = t1_res["relevant_docs"]
        
        for t in retrieved:
            copied_csvs.add(t["csv_path"])
            
        # Format Index list: <report_id>|<table_index>
        tables_index = []
        for t in retrieved:
            r_id = t.get("report_id", "")
            t_idx = t.get("table_index", 1)
            tag = f"{r_id}|{t_idx}"
            if tag not in tables_index:
                tables_index.append(tag)
                
        # Format Line list: <report_id>|<start_line>
        tables_line = []
        for t in retrieved:
            r_id = t.get("report_id", "")
            s_line = t.get("start_line", 1)
            tag = f"{r_id}|{s_line}"
            if tag not in tables_line:
                tables_line.append(tag)
                
        list_index.append({
            "id": q_id,
            "relevant_docs": relevant_docs,
            "relevant_tables": tables_index,
            "answer": 0.0,
            "pandas_query": "float(0.0)"
        })
        
        list_line.append({
            "id": q_id,
            "relevant_docs": relevant_docs,
            "relevant_tables": tables_line,
            "answer": 0.0,
            "pandas_query": "float(0.0)"
        })
        
    return list_index, list_line, copied_csvs

def package_submission(submission_list, copied_csvs, json_path, zip_path):
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(submission_list, f, ensure_ascii=False, indent=2)
    print(f"Ghi file JSON: {json_path}")
    
    temp_dir = json_path.replace('.json', '_temp')
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)
    os.makedirs(temp_dir, exist_ok=True)
    
    with open(os.path.join(temp_dir, 'submission.json'), 'w', encoding='utf-8') as f:
        json.dump(submission_list, f, ensure_ascii=False, indent=2)
        
    for csv_rel_path in copied_csvs:
        src = os.path.join('d:/ROAD_AI', csv_rel_path)
        if os.path.exists(src):
            dst = os.path.join(temp_dir, csv_rel_path)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
            
    if os.path.exists(zip_path):
        os.remove(zip_path)
        
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as z:
        for root, dirs, files in os.walk(temp_dir):
            for file in files:
                full_p = os.path.join(root, file)
                rel_p = os.path.relpath(full_p, temp_dir)
                z.write(full_p, rel_p)
                
    shutil.rmtree(temp_dir)
    print(f"Đã đóng gói thành công: {zip_path} (Dung lượng: {os.path.getsize(zip_path)} bytes)")

def run_ab_pipeline():
    print("=== BẮT ĐẦU CHẠY PIPELINE TẠO 2 BẢN SUBMISSION NỘP THỬ (A/B TESTING) ===")
    
    questions_file = 'd:/ROAD_AI/questions/questions.jsonl'
    metadata_file = 'd:/ROAD_AI/metadata.json'
    
    with open(metadata_file, 'r', encoding='utf-8') as f:
        metadata_db = json.load(f)
        
    questions = []
    with open(questions_file, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                questions.append(json.loads(line.strip()))
                
    print(f"Tổng số câu hỏi: {len(questions)}")
    
    os.environ["FORCE_OFFLINE"] = "False"  # BGE-M3 Live Mode
    list_index, list_line, copied_csvs = process_ab_questions(questions, metadata_db)
    
    # Pack Package A (Index Format)
    print("\n--- GÓI A: FORMAT TABLE_INDEX (submission_table_f2_bge_index.zip) ---")
    package_submission(
        list_index,
        copied_csvs,
        'd:/ROAD_AI/submission_table_f2_bge_index.json',
        'd:/ROAD_AI/submission_table_f2_bge_index.zip'
    )
    
    # Pack Package B (Line Format)
    print("\n--- GÓI B: FORMAT START_LINE (submission_table_f2_bge_line.zip) ---")
    package_submission(
        list_line,
        copied_csvs,
        'd:/ROAD_AI/submission_table_f2_bge_line.json',
        'd:/ROAD_AI/submission_table_f2_bge_line.zip'
    )
    
    print("\n=== ĐÃ HOÀN THÀNH TẠO 2 BẢN NỘP THỬ SONG SONG A/B! ===")

if __name__ == '__main__':
    run_ab_pipeline()
