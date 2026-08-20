import json
import os
import sys
import shutil
import zipfile
import time
from tqdm import tqdm

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, 'd:/ROAD_AI')
sys.path.insert(0, 'd:/ROAD_AI/src')

from src.intent_analyzer import build_target_description
from src.hard_filter import apply_hard_filter
from src.retriever import retrieve_relevant_tables

def main():
    questions_path = 'd:/ROAD_AI/questions/questions_full.jsonl'
    metadata_path = 'd:/ROAD_AI/metadata.json'
    output_json_path = 'd:/ROAD_AI/submission_table_f2.json'
    output_zip_path = 'd:/ROAD_AI/submission_table_f2.zip'
    
    print("=== BẮT ĐẦU CHẠY PIPELINE CHUYÊN DỤNG TỐI ƯU TABLE RETRIEVAL (F2 MACRO) ===")
    
    if not os.path.exists(questions_path) or not os.path.exists(metadata_path):
        print("Lỗi: Không tìm thấy tệp câu hỏi hoặc metadata.json!")
        return
        
    metadata_db = json.load(open(metadata_path, 'r', encoding='utf-8'))
    csv_to_meta = {x['csv_path']: x for x in metadata_db}
    
    questions = []
    with open(questions_path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                questions.append(json.loads(line))
                
    total_q = len(questions)
    print(f"Tổng số câu hỏi cần truy hồi bảng: {total_q}")
    
    results = []
    all_used_csvs = set()
    
    for q in tqdm(questions, desc="Retrieving Tables"):
        q_id = q.get("id")
        q_text = q.get("question")
        
        item_res = {
            "id": q_id,
            "question": q_text,
            "answer": 0.0,
            "relevant_docs": [],
            "relevant_tables": [],
            "evidence": [],
            "pandas_query": "float(0.0)"
        }
        
        try:
            target_desc = build_target_description(q_text)
            candidates = apply_hard_filter(target_desc, metadata_db)
            
            years = target_desc.get("year")
            if isinstance(years, list):
                top_n = max(3, len(years))
            else:
                top_n = 3
                
            retrieved = retrieve_relevant_tables(target_desc, candidates, top_n=top_n)
            
            if retrieved:
                item_res["relevant_docs"] = list(set([r['report_id'] for r in retrieved]))
                item_res["relevant_tables"] = [f"{r['report_id']}|{r['start_line']}" for r in retrieved]
                
                evidence_list = []
                for idx, r in enumerate(retrieved):
                    var_name = f"df{idx+1}"
                    csv_name = os.path.basename(r['csv_path'])
                    evidence_list.append({
                        "variable": var_name,
                        "csv_path": f"data/{csv_name}"
                    })
                    all_used_csvs.add(r['csv_path'])
                    
                item_res["evidence"] = evidence_list
        except Exception as e:
            print(f"\n[Lỗi Q{q_id}]: {e}")
            
        results.append(item_res)
        
    print(f"\nGhi file JSON nộp bài: {output_json_path}")
    with open(output_json_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
        
    # Đóng gói ZIP nộp bài
    print("\n--- ĐÓNG GÓI TỆP ZIP TABLE RETRIEVAL F2 ---")
    temp_dir = 'd:/ROAD_AI/temp_submission_table'
    temp_data_dir = os.path.join(temp_dir, 'data')
    
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)
    os.makedirs(temp_data_dir, exist_ok=True)
    
    shutil.copy(output_json_path, os.path.join(temp_dir, 'submission.json'))
    
    print(f"Sao chép {len(all_used_csvs)} tệp CSV bằng chứng vào thư mục temp...")
    for csv_rel in all_used_csvs:
        src_path = os.path.join('d:/ROAD_AI', csv_rel)
        dest_path = os.path.join(temp_data_dir, os.path.basename(csv_rel))
        if os.path.exists(src_path):
            shutil.copy2(src_path, dest_path)
            
    if os.path.exists(output_zip_path):
        os.remove(output_zip_path)
        
    with zipfile.ZipFile(output_zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        zipf.write(os.path.join(temp_dir, 'submission.json'), 'submission.json')
        for root, dirs, files in os.walk(temp_data_dir):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.join('data', file)
                zipf.write(file_path, arcname)
                
    shutil.rmtree(temp_dir)
    
    print(f"\n=== ĐÃ HOÀN THÀNH PIPELINE TRUY HỒI BẢNG (TABLE RETRIEVAL)! ===")
    print(f"Tệp nộp bài: {output_zip_path} (Dung lượng: {os.path.getsize(output_zip_path)} bytes)")

if __name__ == '__main__':
    main()
