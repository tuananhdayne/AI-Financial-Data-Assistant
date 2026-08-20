"""
TRẠM 3: SINH TRUY VẤN PANDAS & TÍNH TOÁN (EXECUTION LEVEL)
Mục tiêu: Đọc dữ liệu từ các bảng Trạm 2, sinh code Pandas thực thi an toàn (get_val engine), quy đổi hệ số đơn vị và tính đáp án số.
Chỉ số đánh giá: EXECUTION_ACCURACY & ANSWER_ACCURACY
"""

import sys
import os
import json

# Append src to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from query_generator import generate_pandas_query
from python_engine import execute_pandas_code_safely
from post_processor import prune_unused_evidence

def execute_pandas_calculation(question_text, target_desc, retrieved_tables):
    """
    Trạm 3: Sinh code Pandas, thực thi an toàn và gọt bảng thừa (Dynamic Pruning).
    """
    # 1. Sinh code Pandas
    generated_code = generate_pandas_query(question_text, retrieved_tables, target_desc)
    
    # 2. Thực thi an toàn với Series safe-access & fallback cascade
    exec_result = execute_pandas_code_safely(generated_code, retrieved_tables, target_desc)
    
    # 3. Gọt bảng thừa dựa trên code thực tế được dùng
    pruned_tables = prune_unused_evidence(retrieved_tables, exec_result.get("pandas_query", ""))
    
    formatted_pruned_tables = [f"{t.get('report_id')}|{t.get('start_line', 1)}" for t in pruned_tables]
    
    return {
        "answer": exec_result.get("answer", 0.0),
        "pandas_query": exec_result.get("pandas_query", "float(0.0)"),
        "final_relevant_tables": formatted_pruned_tables,
        "pruned_table_objects": pruned_tables
    }

if __name__ == '__main__':
    from station1_doc_filter import filter_documents_for_question
    from station2_table_retriever import retrieve_tables_for_question
    
    metadata_path = 'd:/ROAD_AI/metadata.json'
    with open(metadata_path, 'r', encoding='utf-8') as f:
        metadata_db = json.load(f)
        
    test_q = "Lãi tiền gửi năm 2018 của công ty mẹ CTCP Hàng không Vietjet (VJC) là bao nhiêu triệu đồng?"
    t1_res = filter_documents_for_question(test_q, metadata_db)
    t2_res = retrieve_tables_for_question(t1_res["target_description"], t1_res["candidate_tables"])
    t3_res = execute_pandas_calculation(test_q, t1_res["target_description"], t2_res["retrieved_tables"])
    
    print(f"\n[Trạm 3 Test] Kết quả tính toán:")
    print(f"  -> Answer: {t3_res['answer']}")
    print(f"  -> Pandas Query: {t3_res['pandas_query']}")
    print(f"  -> Bảng được gọt (Final Pruned): {t3_res['final_relevant_tables']}")
