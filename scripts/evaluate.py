import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../src'))
import json
import os
import sys
import pandas as pd
import numpy as np
import traceback

sys.stdout.reconfigure(encoding='utf-8')

# =====================================================================
# SKELETON FUNCTIONS - BẠN SẼ THAY THẾ BẰNG MÔ HÌNH/ALGORITHM CỦA BẠN
# =====================================================================

def my_custom_retriever(question_text, ticker, year, report_type, metadata_db):
    """
    SỬ DỤNG BỘ TRUY XUẤT THẬT (REAL PIPELINE)
    """
    try:
        from intent_analyzer import build_target_description
        from hard_filter import apply_hard_filter
        from retriever import retrieve_relevant_tables
        
        # 1. Chạy phân tích ý định
        target_desc = build_target_description(question_text)
        
        # 2. Chạy bộ lọc cứng
        candidates = apply_hard_filter(target_desc, metadata_db)
        
        # 3. Chạy truy xuất bảng bằng BM25 + Code booster
        retrieved = retrieve_relevant_tables(target_desc, candidates, top_n=2)
        return retrieved
    except Exception as e:
        print(f"Lỗi khi thực thi bộ Retriever thật: {e}")
        return []

def my_custom_query_generator(question_id, question_text, retrieved_tables):
    """
    SỬ DỤNG BỘ SINH TRUY VẤN THẬT (REAL GENERATOR)
    """
    try:
        from intent_analyzer import build_target_description
        from query_generator import generate_pandas_query
        target_desc = build_target_description(question_text)
        query = generate_pandas_query(target_desc, retrieved_tables)
        return query
    except Exception as e:
        print(f"Lỗi khi thực thi bộ Generator thật: {e}")
        return ""

# =====================================================================
# HỆ THỐNG ĐÁNH GIÁ CỤC BỘ (EVALUATION ENGINE)
# =====================================================================

def evaluate_pipeline():
    validation_path = 'd:/ROAD_AI/configs/validation_set.json'
    metadata_path = 'd:/ROAD_AI/metadata.json'
    
    if not os.path.exists(validation_path):
        print(f"Error: Thư mục kiểm thử {validation_path} chưa được tạo!")
        return
    if not os.path.exists(metadata_path):
        print(f"Error: Không tìm thấy file metadata.json!")
        return
        
    with open(validation_path, 'r', encoding='utf-8') as f:
        val_set = json.load(f)
    with open(metadata_path, 'r', encoding='utf-8') as f:
        metadata_db = json.load(f)
        
    print(f"Bắt đầu đánh giá tích hợp trên {len(val_set)} câu hỏi mẫu...")
    print("-" * 70)
    
    retrieval_precisions = []
    retrieval_recalls = []
    retrieval_f2_scores = []
    
    correct_execution_count = 0
    total_questions = len(val_set)
    
    # Import python engine for execution & self-correction
    from python_engine import execute_and_correct_query
    from intent_analyzer import build_target_description
    
    for q in val_set:
        q_id = q['id']
        question_text = q['question']
        ticker = q['ticker']
        year = q['year']
        report_type = q['report_type']
        
        gold_docs = set(q['relevant_docs'])
        gold_tables = set(q['relevant_tables'])
        gold_answer = q['answer']
        
        print(f"\n[Câu hỏi #{q_id}]: {question_text}")
        
        # 1. Chạy bộ phân tích và truy xuất
        target_desc = build_target_description(question_text)
        retrieved_entries = my_custom_retriever(question_text, ticker, year, report_type, metadata_db)
        
        # Tính toán F2 cho Retrieval
        pred_tables = set([f"{item['report_id']}|{item['table_index']}" for item in retrieved_entries])
        true_positives = len(pred_tables.intersection(gold_tables))
        precision = true_positives / len(pred_tables) if len(pred_tables) > 0 else 0.0
        recall = true_positives / len(gold_tables) if len(gold_tables) > 0 else 0.0
        f2 = (5 * precision * recall) / (4 * precision + recall) if (4 * precision + recall) > 0 else 0.0
        
        retrieval_precisions.append(precision)
        retrieval_recalls.append(recall)
        retrieval_f2_scores.append(f2)
        
        print(f"  -> Retrieval: Precision={precision:.2f}, Recall={recall:.2f}, F2={f2:.2f}")
        
        # 2. Sinh câu lệnh Pandas bằng Qwen
        pandas_query = my_custom_query_generator(q_id, question_text, retrieved_entries)
        print(f"  -> Pandas Query ban đầu: {pandas_query}")
        
        if not pandas_query:
            print("  -> Kết quả: THẤT BẠI (Mô hình không sinh được code)")
            continue
            
        # 3. Thực thi và tự động sửa lỗi
        try:
            pred_answer, final_query = execute_and_correct_query(target_desc, retrieved_entries, pandas_query)
            
            if pred_answer is not None:
                # So khớp đáp án với sai số 1%
                is_correct = False
                if math_close(pred_answer, gold_answer, rel_tol=0.01):
                    is_correct = True
                    correct_execution_count += 1
                    
                print(f"  -> Đáp án thực thi: {pred_answer} | Đáp án chuẩn: {gold_answer}")
                print(f"  -> Kết quả: {'THÀNH CÔNG (Đúng đáp án)' if is_correct else 'THẤT BẠI (Lệch số liệu)'}")
            else:
                print("  -> Kết quả: THẤT BẠI (Lỗi thực thi sau khi sửa)")
        except Exception as e:
            print(f"  -> Kết quả: THẤT BẠI (Lỗi hệ thống thực thi: {e})")
            
    # -------------------------------------------------------------
    # BÁO CÁO TỔNG HỢP (SUMMARY REPORT)
    # -------------------------------------------------------------
    mean_precision = np.mean(retrieval_precisions)
    mean_recall = np.mean(retrieval_recalls)
    mean_f2 = np.mean(retrieval_f2_scores)
    exec_accuracy = correct_execution_count / total_questions if total_questions > 0 else 0.0
    
    print("\n" + "="*70)
    print("                      BÁO CÁO ĐÁNH GIÁ CHỈ SỐ LỚN")
    print("="*70)
    print(f"1. CHỈ SỐ TRUY HỒI (RETRIEVAL METRICS):")
    print(f"   - Macro Precision: {mean_precision * 100:.2f}%")
    print(f"   - Macro Recall:    {mean_recall * 100:.2f}%")
    print(f"   - Macro F2 Score:  {mean_f2 * 100:.2f}% (Chỉ số chấm điểm chính của BTC)")
    print(f"2. CHỈ SỐ THỰC THI (EXECUTION METRICS):")
    print(f"   - Execution Accuracy: {exec_accuracy * 100:.2f}% (Tỉ lệ code chạy đúng đáp án)")
    print("="*70)

def math_close(a, b, rel_tol=1e-09, abs_tol=0.0):
    try:
        return abs(a-b) <= max(rel_tol * max(abs(a), abs(b)), abs_tol)
    except:
        return False

if __name__ == '__main__':
    evaluate_pipeline()
