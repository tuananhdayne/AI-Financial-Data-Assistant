---
pretty_name: ViFinQA - AI Financial Data Assistant
language:
- vi
task_categories:
- question-answering
- table-question-answering
size_categories:
- 1K<n<10K
tags:
- finance
- financial-reasoning
- numerical-reasoning
- vietnamese
- agentic-workflow
- rag
configs:
- config_name: default
  data_files:
  - split: train
    path: questions/questions.jsonl
---

# ViFinQA - AI Financial Data Assistant (Hybrid Financial Agentic Workflow)

## Project Overview

**ViFinQA (AI Financial Data Assistant)** là hệ thống Tác tử Tài chính Đa tầng (Hybrid Financial Agentic Workflow) xử lý tự động truy hồi thông tin và tính toán chỉ số tài chính dựa trên 1,012 câu hỏi và 1,973 Báo cáo Tài chính (146,246 bảng dữ liệu CSV) từ 100 công ty niêm yết trên thị trường chứng khoán Việt Nam giai đoạn 2015–2025.

Bản cập nhật Master bổ sung mô hình **Autonomous Financial Agent (`src/financial_agent.py`)** kết hợp **Chuẩn hóa nhị phân Startline (`re.finditer`)**, **Truy hồi Thân bảng (`searchable_cells`)**, **Ngưỡng điểm động ($S_1 > 1.20 \times S_2$)**, và **Gọt Bảng Động (Cross-Station Dynamic Table Pruning)**.

---

## 🏛️ Kiến Trúc Hệ Thống (Master Architecture)

Hệ thống được tổ chức thành 2 mô hình chạy song song:

### 1. Hybrid Financial Agentic Workflow (`main.py --mode agent`)
- ⚡ **Tầng 1 - Fast Path Router (~90% câu hỏi):** Bóc tách Ticker, Năm và Mã số kế toán Thông tư 200 từ `synonyms.json` và `formulas_and_codes.json`. Sinh và nghiệm thu code an toàn `get_val` trực tiếp trong Sandbox trong **0.0001s/câu**.
- 🔄 **Tầng 2 - LLM Fallback & Self-Healing Agent (~10% câu khó):** Tự động kích hoạt khi Tầng 1 thất bại. Vòng lặp Agent gửi `[Câu hỏi + Cấu trúc Bảng + 120 dòng Văn bản + Traceback Mã lỗi]` tới **Qwen2.5 LLM** để viết lại câu lệnh Pandas, thử lại trên Sandbox (tối đa 2-3 vòng).
- ✂️ **Tầng 3 - Dynamic Pruning & Unit Scaling:** Phân tích AST của câu lệnh Pandas đã thực thi thành công, loại bỏ các bảng không được sử dụng (`df2`, `df3`...) khỏi `relevant_tables` để tối đa hóa điểm `TABLES_PRECISION`, đồng thời nhân hệ số quy đổi đơn vị (tỷ, triệu, nghìn, %).

### 2. 3-Station Modular RAG Pipeline (`main.py --mode station1 / station2 / full`)
- **Trạm 1 (Document Level):** Lọc thô tài liệu theo Ticker, Năm và Loại báo cáo (Separate / Consolidated) (**`DOCS_F2MACRO = 0.9615 (96.15%)`**).
- **Trạm 2 (Table Level & Startline Mapper):** Định vị bảng bằng BM25 + BGE-M3 Dense Vector Cosine Search (1024D) + Rule-Based Boosters, khóa chính xác vị trí dòng bắt đầu `<report_id>|<start_line>`.
- **Trạm 3 (Execution Engine):** Sandbox Pandas, `get_val` engine, và tính toán số liệu chính xác.

---

## 🛠️ Cấu Trúc Thư Mục Dự Án (Directory Layout)

```text
d:/ROAD_AI/
├── configs/                      # Cấu hình từ điển domain & validation set
│   ├── formulas_and_codes.json   # Mã chỉ tiêu Thông tư 200 & 18 công thức tài chính
│   ├── synonyms.json             # Từ điển đồng nghĩa & bóc tách Ticker/Năm
│   └── validation_set.json       # Bộ dữ liệu kiểm thử cục bộ
├── data/                         # Thư mục dữ liệu bảng CSV (146,246 bảng)
├── financial_statements/         # Thư mục văn bản BCTC OCR (.txt gốc)
├── questions/                    # Bộ câu hỏi thi đấu ViFinQA (1,012 câu)
│   └── questions.jsonl
├── src/                          # Mã nguồn lõi Tác tử & 3 Trạm
│   ├── financial_agent.py        # Master Financial Agentic Workflow
│   ├── station1_doc_filter.py    # Trạm 1: Document Level Filter
│   ├── station2_table_retriever.py# Trạm 2: Table Level & Startline Mapper
│   ├── station3_pandas_engine.py # Trạm 3: Execution & Dynamic Pruning
│   ├── intent_analyzer.py        # Phân tích ý định câu hỏi & LLM Prompts
│   ├── hard_filter.py            # Lọc cứng Ticker, Năm & Loại báo cáo
│   ├── retriever.py              # BM25 & BGE-M3 Vector Cosine Scoring
│   └── python_engine.py          # Sandbox thực thi Pandas & Self-Correction
├── runners/                      # Các kịch bản khởi chạy chuyên dụng
│   ├── run_station1_docs_only.py
│   ├── run_station2_tables_only.py# Sinh song song submission_table_f2.zip & bge.zip
│   └── run_full_pipeline.py
├── scripts/                      # Đánh giá & công cụ phụ trợ
│   └── evaluate.py               # Đánh giá F2 Macro & Execution Accuracy cục bộ
├── code_stock.csv                # Từ điển mã cổ phiếu -> tên công ty
├── main.py                       # CLI Entrypoint đồng nhất cho toàn bộ hệ thống
├── parse_data.py                 # Chuẩn hóa nhị phân re.finditer & tạo metadata.json
├── PROJECT_HISTORY_AND_LESSONS.md# Lịch sử dự án & 8 bài học kinh nghiệm
├── DATA_PROCESSING_GUIDE.md      # Hướng dẫn xử lý dữ liệu Thông tư 200
└── README.md                     # Tài liệu tổng quan dự án
```

---

## ⚡ Hướng Dẫn Sử Dụng Command Line (CLI)

```bash
# 1. Khởi chạy Master Hybrid Financial Agent (Tùy chọn chạy mẫu --sample 10)
python main.py --mode agent --sample 10

# 2. Khởi chạy Master Hybrid Financial Agent toàn bộ 1,012 câu -> xuất submission_final.zip
python main.py --mode agent

# 3. Khởi chạy Trạm 2 Table Retrieval -> xuất đồng thời submission_table_f2.zip & submission_table_f2_bge.zip
python main.py --mode station2

# 4. Khởi chạy Trạm 1 Document Retrieval (Lọc BCTC)
python main.py --mode station1
```

---

## 🏆 Điểm Số Benchmark Đã Kiểm Thử Trực Tiếp

- **`DOCS_F2MACRO`**: **`0.9615 (96.15%)`** (Trạm 1 Lọc tài liệu)
- **`DOCS_PRECISION`**: **`0.9655 (96.55%)`**
- **`DOCS_RECALL`**: **`0.9642 (96.42%)`**
- **`DOCS_MRR5`**: **`0.9740 (97.40%)`**
- **Startline Alignment:** Khóa dòng nhị phân **`re.finditer`** đạt độ chính xác 100% về vị trí offset dòng `<report_id>|<start_line>`.

---

## 📝 Giấy Phép & Nguồn Dữ Liệu

Dữ liệu BCTC nguồn trích từ tập dữ liệu công khai TiniX Vietnam OCR Annual Financial Statements (CC BY-NC 4.0). Chi tiết tham khảo `yeucau.md` và `DATA_PROCESSING_GUIDE.md`.
