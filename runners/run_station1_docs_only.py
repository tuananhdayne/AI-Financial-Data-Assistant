"""
RUNNER TRẠM 1: CHUYÊN DỤNG DOCUMENT RETRIEVAL (DOCS_F2MACRO)
Mục tiêu: Quét toàn bộ 1,012 câu hỏi thi theo Bộ 4 Giải pháp Nâng cấp Stage 1 và đóng gói submission_docs_f2.zip.
"""

import sys
import os
import json
import zipfile
import shutil
from tqdm import tqdm

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))

from station1_doc_filter import filter_documents_for_question

def run_doc_retrieval_pipeline():
    print("=== BẮT ĐẦU CHẠY PIPELINE CHUYÊN DỤNG TRẠM 1: LỌC BCTC (DOCS_F2MACRO) ===")
    
    questions_file = 'd:/ROAD_AI/questions/questions.jsonl'
    metadata_file = 'd:/ROAD_AI/metadata.json'
    
    with open(metadata_file, 'r', encoding='utf-8') as f:
        metadata_db = json.load(f)
        
    questions = []
    with open(questions_file, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                questions.append(json.loads(line.strip()))
                
    print(f"Tổng số câu hỏi cần định danh BCTC: {len(questions)}")
    
    submission_list = []
    
    for item in tqdm(questions, desc="Filtering Documents (Stage 1)"):
        q_id = item["id"]
        q_text = item["question"]
        
        # Trạm 1: Document Level Filter với 4 Nâng cấp Chống Mất Recall
        t1_res = filter_documents_for_question(q_text, metadata_db)
        relevant_docs = t1_res["relevant_docs"]
        
        submission_list.append({
            "id": q_id,
            "relevant_docs": relevant_docs,
            "relevant_tables": [],
            "answer": 0.0,
            "pandas_query": "float(0.0)"
        })
        
    out_json = 'd:/ROAD_AI/submission_docs_f2.json'
    with open(out_json, 'w', encoding='utf-8') as f:
        json.dump(submission_list, f, ensure_ascii=False, indent=2)
    print(f"\nGhi file JSON nộp bài Trạm 1: {out_json}")
    
    out_zip = 'd:/ROAD_AI/submission_docs_f2.zip'
    temp_dir = 'd:/ROAD_AI/temp_submission_docs'
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)
    os.makedirs(temp_dir, exist_ok=True)
    
    with open(os.path.join(temp_dir, 'submission.json'), 'w', encoding='utf-8') as f:
        json.dump(submission_list, f, ensure_ascii=False, indent=2)
        
    with zipfile.ZipFile(out_zip, 'w', zipfile.ZIP_DEFLATED) as z:
        for root, dirs, files in os.walk(temp_dir):
            for file in files:
                full_p = os.path.join(root, file)
                rel_p = os.path.relpath(full_p, temp_dir)
                z.write(full_p, rel_p)
                
    shutil.rmtree(temp_dir)
    print(f"\n=== ĐÃ HOÀN THÀNH PIPELINE LỌC BCTC (STAGE 1)! ===")
    print(f"Tệp nộp bài Trạm 1: {out_zip} (Dung lượng: {os.path.getsize(out_zip)} bytes)")

if __name__ == '__main__':
    run_doc_retrieval_pipeline()
