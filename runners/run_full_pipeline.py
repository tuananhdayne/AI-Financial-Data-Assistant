"""
RUNNER FULL PIPELINE: TỰ ĐỘNG CHẠY LIÊN HOÀN TRẠM 1 -> TRẠM 2 -> TRẠM 3
Mục tiêu: Đóng gói tệp nộp bài hoàn chỉnh submission_final.zip.
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
from station3_pandas_engine import execute_pandas_calculation

def run_full_master_pipeline():
    print("=== BẮT ĐẦU CHẠY PIPELINE LIÊN HOÀN TRẠM 1 -> TRẠM 2 -> TRẠM 3 ===")
    
    questions_file = 'd:/ROAD_AI/questions/questions.jsonl'
    metadata_file = 'd:/ROAD_AI/metadata.json'
    
    with open(metadata_file, 'r', encoding='utf-8') as f:
        metadata_db = json.load(f)
        
    questions = []
    with open(questions_file, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                questions.append(json.loads(line.strip()))
                
    print(f"Tổng số câu hỏi cần thực thi: {len(questions)}")
    
    submission_list = []
    copied_csvs = set()
    
    for item in tqdm(questions, desc="Executing Master Pipeline"):
        q_id = item["id"]
        q_text = item["question"]
        
        # Trạm 1: Document Filter
        t1_res = filter_documents_for_question(q_text, metadata_db)
        
        # Trạm 2: Table Retrieval & Startline Mapping
        t2_res = retrieve_tables_for_question(t1_res["target_description"], t1_res["candidate_tables"], top_n=2)
        
        # Trạm 3: Pandas Engine & Safe Calculation & Dynamic Pruning
        t3_res = execute_pandas_calculation(q_text, t1_res["target_description"], t2_res["retrieved_tables"])
        
        for t in t3_res["pruned_table_objects"]:
            copied_csvs.add(t["csv_path"])
            
        submission_list.append({
            "id": q_id,
            "relevant_docs": t1_res["relevant_docs"],
            "relevant_tables": t3_res["final_relevant_tables"],
            "answer": t3_res["answer"],
            "pandas_query": t3_res["pandas_query"]
        })
        
    out_json = 'd:/ROAD_AI/submission_final.json'
    with open(out_json, 'w', encoding='utf-8') as f:
        json.dump(submission_list, f, ensure_ascii=False, indent=2)
    print(f"\nGhi file JSON nộp bài: {out_json}")
    
    out_zip = 'd:/ROAD_AI/submission_final.zip'
    temp_dir = 'd:/ROAD_AI/temp_submission_final'
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
            
    with zipfile.ZipFile(out_zip, 'w', zipfile.ZIP_DEFLATED) as z:
        for root, dirs, files in os.walk(temp_dir):
            for file in files:
                full_p = os.path.join(root, file)
                rel_p = os.path.relpath(full_p, temp_dir)
                z.write(full_p, rel_p)
                
    shutil.rmtree(temp_dir)
    print(f"\n=== ĐÃ HOÀN THÀNH PIPELINE LIÊN HOÀN FULL THÀNH CÔNG! ===")
    print(f"Tệp nộp bài: {out_zip} (Dung lượng: {os.path.getsize(out_zip)} bytes)")

if __name__ == '__main__':
    run_full_master_pipeline()
