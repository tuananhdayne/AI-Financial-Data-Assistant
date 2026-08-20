"""
MAIN CLI ENTRYPOINT FOR VIFINQA / ROAD_AI HYBRID FINANCIAL AGENT
Cung cấp giao diện dòng lệnh đồng nhất để khởi chạy các trạm xử lý & Agent:
- Mode 'station1': Lọc thô tệp BCTC (DOCS_F2MACRO)
- Mode 'station2': Lọc tinh bảng & khóa dòng startline (TABLES_F2MACRO) -> submission_table_f2.zip
- Mode 'agent':    Khởi chạy Hybrid Financial Agentic Workflow -> submission_final.zip
- Mode 'full':     Khởi chạy liên hoàn toàn bộ hệ thống
"""

import sys
import os
import argparse

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src'))
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'runners'))

def main():
    parser = argparse.ArgumentParser(description="ROAD_AI Hybrid Financial Agent CLI Entrypoint")
    parser.add_argument(
        "--mode", 
        type=str, 
        default="agent", 
        choices=["station1", "station2", "agent", "full"],
        help="Chọn chế độ chạy: 'station1' (Lọc BCTC), 'station2' (Retrieval Bảng F2), 'agent' (Hybrid Financial Agent), 'full' (Liên hoàn từ A-Z)"
    )
    parser.add_argument("--sample", type=int, default=None, help="Chạy kiểm thử trên mẫu N câu hỏi đầu tiên")
    args = parser.parse_args()
    
    if args.mode == "station1":
        from run_station1_docs_only import run_doc_retrieval_pipeline
        run_doc_retrieval_pipeline()
        
    elif args.mode == "station2":
        from run_station2_tables_only import run_table_retrieval_pipeline
        run_table_retrieval_pipeline()
        
    elif args.mode == "agent" or args.mode == "full":
        from financial_agent import run_financial_agent_pipeline
        run_financial_agent_pipeline(sample_size=args.sample)

if __name__ == '__main__':
    main()
