"""
RUNNER TRẠM 2 MASTER: TỐI ƯU HÓA TABLE RETRIEVAL (TABLES_F2MACRO)
Mục tiêu: Đóng gói đồng thời 2 gói nộp bài:
  1. submission_table_f2.zip (Pure Heuristics Rule-Based - Fast Mode)
  2. submission_table_f2_bge.zip (BGE-M3 Vector Dense Search + Qwen LLM)
Chỉ số đánh giá: TABLES_F2MACRO (Recall quan trọng gấp đôi Precision).
"""

import sys
import os
import json
import zipfile
import shutil
from tqdm import tqdm

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))

from station1_doc_filter import filter_documents_for_question
from station2_table_retriever import retrieve_tables_for_question

def process_questions(questions, metadata_db, force_offline=True):
    os.environ["FORCE_OFFLINE"] = "True" if force_offline else "False"
    
    submission_list = []
    copied_csvs = set()
    
    desc_label = "Pure Heuristics (Offline)" if force_offline else "BGE-M3 Vector Rerank (Live)"
    
    for item in tqdm(questions, desc=f"Retrieving Tables [{desc_label}]"):
        q_id = item["id"]
        q_text = item["question"]
        
        # Trạm 1: Document Level Filter
        t1_res = filter_documents_for_question(q_text, metadata_db)
        target_desc = t1_res["target_description"]
        
        # Dynamic Top-K Quota Tuning (F2 Optimization)
        years = target_desc.get("year", [])
        tickers = target_desc.get("ticker", [])
        formula = target_desc.get("formula_applied")
        
        q_lower = q_text.lower()
        is_formula_q = (formula is not None) or any(kw in q_lower for kw in ['roe', 'roa', 'biên lợi nhuận', 'd/e', 'thanh toán', 'cfo margin', 'vốn lưu động', 'nwc', 'vòng quay', 'sg&a', 'tỷ lệ nợ', 'nợ nần'])
        is_multi_year = isinstance(years, list) and len(years) > 1
        is_multi_ticker = isinstance(tickers, list) and len(tickers) > 1
        
        if is_formula_q:
            # Formula questions require both Balance Sheet and Income Statement tables (4-6 tables)
            calc_top_n = 4
        elif is_multi_year:
            calc_top_n = max(4, len(years) * 2)
        elif is_multi_ticker:
            calc_top_n = max(4, len(tickers) * 2)
        else:
            # Single-metric questions: keep Top 2-3 tables to guarantee 100% Recall!
            calc_top_n = 2
            
        t2_res = retrieve_tables_for_question(target_desc, t1_res["candidate_tables"], top_n=calc_top_n)
        
        relevant_docs = t1_res["relevant_docs"]
        relevant_tables = t2_res["formatted_relevant_tables"]
        
        for t in t2_res["retrieved_tables"]:
            copied_csvs.add(t["csv_path"])
            
        submission_list.append({
            "id": q_id,
            "relevant_docs": relevant_docs,
            "relevant_tables": relevant_tables,
            "answer": 0.0,
            "pandas_query": "float(0.0)"
        })
        
    return submission_list, copied_csvs

def package_submission(submission_list, copied_csvs, json_path, zip_path):
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(submission_list, f, ensure_ascii=False, indent=2)
    print(f"Ghi file JSON nộp bài: {json_path}")
    
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

def run_table_retrieval_pipeline(run_bge=True):
    print("=== BẮT ĐẦU CHẠY PIPELINE CHUYÊN DỤNG TRẠM 2 (TABLE RETRIEVAL F2 MACRO) ===")
    
    questions_file = 'd:/ROAD_AI/questions/questions.jsonl'
    metadata_file = 'd:/ROAD_AI/metadata.json'
    
    with open(metadata_file, 'r', encoding='utf-8') as f:
        metadata_db = json.load(f)
        
    questions = []
    with open(questions_file, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                questions.append(json.loads(line.strip()))
                
    print(f"Tổng số câu hỏi cần truy hồi bảng: {len(questions)}")
    
    # 1. GÓI NỘP BÀI 1: Pure Heuristics Offline (Fast Mode)
    print("\n--- GIAI ĐOẠN 1: SINH GÓI NỘP BÀI PURE HEURISTICS (submission_table_f2.zip) ---")
    list_heuristics, csvs_heuristics = process_questions(questions, metadata_db, force_offline=True)
    package_submission(
        list_heuristics, 
        csvs_heuristics, 
        'd:/ROAD_AI/submission_table_f2.json', 
        'd:/ROAD_AI/submission_table_f2.zip'
    )
    
    # 2. GÓI NỘP BÀI 2: BGE-M3 Vector Dense Search (Live Mode)
    if run_bge:
        print("\n--- GIAI ĐOẠN 2: SINH GÓI NỘP BÀI BGE-M3 VECTOR SEARCH (submission_table_f2_bge.zip) ---")
        list_bge, csvs_bge = process_questions(questions, metadata_db, force_offline=False)
        package_submission(
            list_bge, 
            csvs_bge, 
            'd:/ROAD_AI/submission_table_f2_bge.json', 
            'd:/ROAD_AI/submission_table_f2_bge.zip'
        )
        
    print("\n=== ĐÃ HOÀN THÀNH ĐÓNG GÓI SONG SONG CẢ 2 BẢN NỘP BÀI TRẠM 2! ===")

if __name__ == '__main__':
    run_table_retrieval_pipeline(run_bge=True)
