import json
import os
import sys

# Configure standard output to UTF-8
sys.stdout.reconfigure(encoding='utf-8')

def load_json_file(file_path):
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def apply_hard_filter(target_desc, metadata_db):
    ticker = target_desc.get("ticker")
    year = target_desc.get("year")
    report_type = target_desc.get("report_type", "consolidated")
    
    if not ticker and not year:
        print(f"Warning: Thiếu cả Ticker và Năm để lọc cứng! Trả về toàn bộ danh sách.")
        return metadata_db
        
    print(f"--- BẮT ĐẦU BỘ LỌC CỨNG (Hard-Filtering) ---")
    print(f"Đầu vào lọc: Ticker = {ticker} | Năm = {year} | Loại báo cáo = {report_type}")
    print(f"Tổng số bảng ban đầu trong kho: {len(metadata_db)} bảng.")
    
    filtered = metadata_db
    
    # 1. Lọc theo Ticker (nếu có)
    if ticker:
        ticker_list = ticker if isinstance(ticker, list) else [ticker]
        filtered = [item for item in filtered if item.get("ticker") in ticker_list]
        print(f"-> Sau khi lọc theo Ticker: {len(filtered)} bảng còn lại.")
        
    # 2. Lọc theo Năm (nếu có)
    if year:
        if isinstance(year, list):
            filtered = [item for item in filtered if item.get("year") in year]
        else:
            filtered = [item for item in filtered if item.get("year") == year]
        print(f"-> Sau khi lọc theo Năm: {len(filtered)} bảng còn lại.")
        
    # 3. Lọc theo Loại báo cáo (separate vs consolidated) - Ưu tiên tuyệt đối loại báo cáo yêu cầu
    if report_type == 'separate':
        separate_matches = [item for item in filtered if 'separate' in item.get("report_id", "").lower()]
        if separate_matches:
            final_candidates = separate_matches
        else:
            final_candidates = [item for item in filtered if 'consolidated' not in item.get("report_id", "").lower()]
    else:
        consolidated_matches = [item for item in filtered if 'consolidated' in item.get("report_id", "").lower()]
        if consolidated_matches:
            final_candidates = consolidated_matches
        else:
            final_candidates = [item for item in filtered if 'separate' not in item.get("report_id", "").lower()]
            
    print(f"-> Sau khi lọc theo Loại báo cáo ({report_type}): {len(final_candidates)} bảng còn lại.")
    print(f"---------------------------------------------")
    
    return final_candidates

if __name__ == '__main__':
    # 1. Chạy thử nghiệm Bước 1 để lấy Target Description
    try:
        from intent_analyzer import build_target_description
    except ImportError:
        print("Error: Không tìm thấy intent_analyzer.py!")
        sys.exit(1)
        
    test_q = "Lãi tiền gửi năm 2018 của công ty mẹ CTCP Hàng không Vietjet (VJC) là bao nhiêu triệu đồng?"
    if len(sys.argv) > 1:
        test_q = " ".join(sys.argv[1:])
        
    print(f"Câu hỏi test: '{test_q}'\n")
    
    # Lấy kết quả phân tích ý định
    target_desc = build_target_description(test_q)
    
    # 2. Tải cơ sở dữ liệu metadata
    metadata_db = load_json_file('d:/ROAD_AI/metadata.json')
    
    # 3. Chạy lọc cứng
    candidates = apply_hard_filter(target_desc, metadata_db)
    
    # 4. In thử kết quả mẫu
    print(f"\nDanh sách 3 bảng ứng viên đầu tiên sau khi lọc:")
    for idx, c in enumerate(candidates[:3]):
        print(f"Ứng viên #{idx+1}:")
        print(f"  - Report ID:  {c['report_id']}")
        print(f"  - Table Index: {c['table_index']} (Dòng bắt đầu: {c['start_line']})")
        print(f"  - Table Type:  {c['table_type']}")
        print(f"  - Context:     {c['table_context'].replace(chr(10), ' | ')[:100]}...")
        print("-" * 50)
