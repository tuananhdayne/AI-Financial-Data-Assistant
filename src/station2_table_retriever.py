"""
TRẠM 2: ĐỊNH VỊ BẢNG & KHÓA DÒNG BẮT ĐẦU (TABLE LEVEL - LỌC TINH)
Mục tiêu: Tìm chính xác bảng CSV chứa số liệu và khóa vị trí dòng bắt đầu <report_id>|<start_line> chuẩn BTC.
Chỉ số đánh giá: TABLES_F2MACRO
"""

import sys
import os
import json

# Append src to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from retriever import retrieve_relevant_tables

def retrieve_tables_for_question(target_desc, candidate_tables, top_n=2):
    """
    Trạm 2: Quét BM25 Top 25 + Re-ranking BGE-M3 Dense Vector Cosine & Heuristics.
    Trả về danh sách bảng kèm vị trí dòng mở đầu <report_id>|<start_line>.
    """
    retrieved_tables = retrieve_relevant_tables(target_desc, candidate_tables, top_n=top_n)
    
    formatted_relevant_tables = []
    for t in retrieved_tables:
        report_id = t.get("report_id", "")
        start_line = t.get("start_line", 1)
        parent_start = t.get("parent_table_start_line")
        
        # Primary start_line tag
        primary_tag = f"{report_id}|{start_line}"
        if primary_tag not in formatted_relevant_tables:
            formatted_relevant_tables.append(primary_tag)
            
        # Optional parent start_line tag for continuation tables
        if parent_start and parent_start != start_line:
            parent_tag = f"{report_id}|{parent_start}"
            if parent_tag not in formatted_relevant_tables:
                formatted_relevant_tables.append(parent_tag)
        
    return {
        "retrieved_tables": retrieved_tables,
        "formatted_relevant_tables": formatted_relevant_tables
    }

if __name__ == '__main__':
    from station1_doc_filter import filter_documents_for_question
    
    metadata_path = 'd:/ROAD_AI/metadata.json'
    with open(metadata_path, 'r', encoding='utf-8') as f:
        metadata_db = json.load(f)
        
    test_q = "Lãi tiền gửi năm 2018 của công ty mẹ CTCP Hàng không Vietjet (VJC) là bao nhiêu triệu đồng?"
    t1_res = filter_documents_for_question(test_q, metadata_db)
    t2_res = retrieve_tables_for_question(t1_res["target_description"], t1_res["candidate_tables"])
    
    print(f"\n[Trạm 2 Test] Bảng được chọn (khóa dòng start_line):")
    for item in t2_res["formatted_relevant_tables"]:
        print(f"  -> {item}")
