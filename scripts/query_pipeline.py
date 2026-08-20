import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../src'))
import sys
import json
import os

# Configure standard output to UTF-8
sys.stdout.reconfigure(encoding='utf-8')

def run_pipeline_for_question_id(q_id):
    questions_path = 'd:/ROAD_AI/questions/questions.jsonl'
    metadata_path = 'd:/ROAD_AI/metadata.json'
    
    if not os.path.exists(questions_path):
        print(f"Error: Không tìm thấy file câu hỏi {questions_path}!")
        return
        
    # 1. Tìm câu hỏi trong questions.jsonl theo ID
    target_question = None
    with open(questions_path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                item = json.loads(line)
                if item.get("id") == q_id:
                    target_question = item.get("question")
                    break
                    
    if not target_question:
        print(f"Error: Không tìm thấy câu hỏi với ID = {q_id} trong file questions.jsonl!")
        return
        
    print(f"======================================================================")
    print(f"CHẠY PIPELINE CHO CÂU HỎI THI #{q_id}")
    print(f"Nội dung câu hỏi: '{target_question}'")
    print(f"======================================================================\n")
    
    # Import các module đã xây dựng
    try:
        from intent_analyzer import build_target_description
        from hard_filter import apply_hard_filter
        from retriever import retrieve_relevant_tables
    except ImportError as e:
        print(f"Error import module: {e}")
        return
        
    # Tải cơ sở dữ liệu metadata
    if not os.path.exists(metadata_path):
        print("Error: metadata.json không tồn tại!")
        return
    with open(metadata_path, 'r', encoding='utf-8') as f:
        metadata_db = json.load(f)
        
    # Bước 1: Phân tích ý định
    print("Bước 1: Đang gọi LLM (LM Studio) phân tích Ý định & Chỉ tiêu...")
    target_desc = build_target_description(target_question)
    print(f"  -> Ticker bóc tách:       {target_desc['ticker']}")
    print(f"  -> Năm bóc tách:          {target_desc['year']}")
    print(f"  -> Loại báo cáo:          {target_desc['report_type']}")
    print(f"  -> Đơn vị hỏi:            {target_desc['unit']}")
    print(f"  -> Phân tích chỉ tiêu:    {target_desc['target_metrics']}")
    print(f"  -> Mã số kế toán đích:   {target_desc['target_codes']}")
    print(f"  -> Hệ số quy đổi đơn vị:  {target_desc['scaling_factor']}")
    print("-" * 70)
    
    # Bước 2: Bộ lọc cứng
    print("Bước 2: Đang chạy Bộ lọc cứng (Hard-Filtering)...")
    candidates = apply_hard_filter(target_desc, metadata_db)
    print("-" * 70)
    
    # Bước 3: Truy xuất bảng
    print("Bước 3: Đang chạy Retriever (BM25 + Code Booster)...")
    retrieved = retrieve_relevant_tables(target_desc, candidates, top_n=2)
    print("-" * 70)
    
    print("\n[KẾT QUẢ ĐẦU RA PIPELINE]:")
    print(f"Danh sách các file CSV được gợi ý sử dụng:")
    for idx, r in enumerate(retrieved):
        print(f"  {idx+1}. Thư mục: {r['csv_path']}")
        print(f"     Báo cáo:  {r['report_id']}")
        print(f"     Bảng số:  {r['table_index']} (Dòng gốc: {r['start_line']}, Trang gốc: {r['page_number']})")
        print(f"     Loại bảng: {r['table_type']}")
        print(f"     Xem trước ngữ cảnh: \n{r['table_context']}\n")
    print(f"======================================================================")

if __name__ == '__main__':
    q_id = 1
    if len(sys.argv) > 1:
        try:
            q_id = int(sys.argv[1])
        except ValueError:
            print("Vui lòng nhập ID câu hỏi là một số nguyên!")
            sys.exit(1)
            
    run_pipeline_for_question_id(q_id)
