# Tóm Tắt Hệ Thống Dữ Liệu BCTC - R2AI2026 Text-to-Pandas

Tài liệu này tổng hợp toàn bộ các tệp dữ liệu đã được trích xuất, chuẩn hóa và làm giàu tri thức để phục vụ dự án sinh mã truy vấn tài chính tự động.

---

## 1. Kết Quả Trích Xuất Dữ Liệu Thô (CSV Database)
*   **Tổng số báo cáo tài chính gốc đã xử lý:** 1.973 báo cáo thô dạng `.txt` (100 doanh nghiệp giai đoạn 2015-2025).
*   **Tổng số bảng dữ liệu trích xuất thành công:** **146.246** bảng.
*   **Thư mục lưu trữ CSV:** [data/](file:///d:/ROAD_AI/data/)
*   **Chuẩn hóa định dạng CSV:**
    *   **Mã hóa:** `UTF-8 with BOM` (`utf-8-sig`) hiển thị tiếng Việt hoàn hảo, không lỗi font khi mở trực tiếp bằng Excel trên Windows.
    *   **Làm sạch số:** Loại bỏ dấu phân cách hàng nghìn, chuyển đổi ngoặc âm `(123)` thành `-123`, xử lý dấu `%`. Các ô số được lưu dưới dạng chuỗi số nguyên/số thực chuẩn để Pandas tự động nhận diện đúng kiểu dữ liệu khi load.

---

## 2. Các File Chỉ Mục & Tri Thức Bổ Trợ (Knowledge Base)

Hệ thống bao gồm 4 file JSON cốt lõi đóng vai trò là "bộ não" hỗ trợ mô hình RAG tìm kiếm tài liệu và sinh truy vấn Pandas:

### A. Chỉ mục Metadata chính: [metadata.json](file:///d:/ROAD_AI/metadata.json)
Lưu thông tin định vị, ngữ cảnh và cấu trúc cột của toàn bộ 146.246 bảng. Mỗi bản ghi bao gồm:
*   `report_id`: Mã định danh báo cáo (tên folder gốc loại bỏ `.txt`).
*   `ticker` & `year` & `company_name`: Thông tin công ty và năm tài chính.
*   `table_index`: Số thứ tự bảng trong báo cáo (1-based index).
*   `start_line` & `page_number`: Vị trí dòng bắt đầu và số trang trong file gốc.
*   `table_context`: Đoạn văn bản 6 dòng trước bảng (tiêu đề, thuyết minh, đơn vị tính).
*   `table_type`: Phân loại loại bảng (`Balance Sheet`, `Income Statement`, `Cash Flow Statement`, `Notes`, `Other/Details`).
*   `headers`: Mảng tiêu đề cột thực tế của bảng phục vụ định vị mốc thời gian.

### B. Từ điển Công thức & Mã số Thông tư 200: [formulas_and_codes.json](file:///d:/ROAD_AI/formulas_and_codes.json)
Bản đồ ánh xạ các chỉ số tài chính xuất hiện trong câu hỏi sang mã số báo cáo tài chính tiêu chuẩn của Bộ Tài chính Việt Nam:
*   *Mã số tiêu chuẩn:* Tổng tài sản (`270`), Nợ phải trả (`300`), Vốn chủ sở hữu (`400`), Doanh thu thuần (`10`), Lợi nhuận sau thuế (`60` hoặc `61`).
*   *Công thức nâng cao kèm mẫu Pandas:* Hướng dẫn tính toán cụ thể cho ROE, ROA, Biên lợi nhuận gộp/ròng, Hệ số thanh toán nhanh, Hệ số khả năng thanh toán lãi vay, Số ngày tồn kho, Tỷ số dồn tích (Accrual Ratio).

### C. Từ điển Đồng nghĩa Công ty: [synonyms.json](file:///d:/ROAD_AI/synonyms.json)
Ánh xạ 100 mã cổ phiếu (Ticker) sang danh sách các tên gọi tiếng Việt đầy đủ, tên viết tắt thương hiệu thông dụng, hoặc tên không dấu:
*   *Ví dụ:* `VCB` ──► `["vcb", "vietcombank", "ngoại thương việt nam", "ngân hàng tmcp ngoại thương việt nam"]`.
*   Giúp bộ tìm kiếm thực thể (Entity Matching) từ câu hỏi đạt độ chính xác 100%.

### D. Tập dữ liệu kiểm thử vàng cục bộ: [validation_set.json](file:///d:/ROAD_AI/validation_set.json)
Chứa 3 câu hỏi thực tế được gán nhãn thủ công đầy đủ thông tin về bảng đích, đường dẫn CSV, câu lệnh Pandas chuẩn và đáp án chính xác để chạy đánh giá cục bộ.

---

## 3. Script Kiểm Thử & Đánh Giá Tự Động: [evaluate.py](file:///d:/ROAD_AI/evaluate.py)
Kịch bản Python dùng để chạy đánh giá hiệu năng hệ thống RAG + Sinh code Pandas trên máy cá nhân:
*   **Tính toán chỉ số F2 Score** cho bộ tìm kiếm bảng (Retriever).
*   **Tính toán chỉ số Execution Accuracy** cho bộ sinh code (Generator).
*   In ra báo cáo chi tiết câu hỏi nào bị lỗi thực thi hoặc lệch số liệu để bạn tinh chỉnh Prompt/Thuật toán tức thì.
*   *Lệnh chạy:* `python d:/ROAD_AI/evaluate.py`

---

## 4. Cẩm Nang Prompt Bất Bại Cho LLM: [data_alignment_guide.md](file:///C:/Users/84867/.gemini/antigravity/brain/d59c4414-4907-47a6-adc8-230c743c287a/data_alignment_guide.md)
Tập hợp các quy tắc cần nạp vào Prompt của LLM viết code Pandas:
1.  **Nhân 100 khi hỏi %:** Nhân kết quả với 100 nếu câu hỏi chứa ký tự `%` hoặc cụm từ `"phần trăm"`.
2.  **Luôn ép kiểu String cho cột Mã số:** Tránh lỗi kiểu dữ liệu bằng cách ép chuỗi: `df[df['1'].astype(str).str.strip() == '60']`.
3.  **Hệ thống dự phòng (Fallback):** Tự động chuyển sang dùng Regex `str.contains()` tìm theo tên chỉ tiêu ở cột `'0'` khi bảng bị mất cột Mã số.
4.  **Định dạng số nộp bài:** Giữ nguyên số thô kiểu số thực/số nguyên của JSON, tuyệt đối không định dạng thành chuỗi chứa dấu phân cách hàng nghìn.
5. **Series Safe-Access & get_val Engine (V15):** Sử dụng helper `get_val(df, code, keyword)` cho phép quét mã số và từ khóa trên BẤT KỲ CỘT NÀO, tự động trích xuất cột số cuối năm qua `.iloc[:, -2]` bọc trong Series safe-access `.get(0, 0.0)`.
6. **Startline Alignment:** Khóa truy hồi bảng `relevant_tables` nộp bài được đồng bộ 100% theo vị trí dòng bắt đầu (`<report_id>|<start_line>`), bứt phá chỉ số `TABLES_F2MACRO` trên hệ thống chấm thi BTC.
7. **Master V16 Heuristic Boost Table & BGE Embedding Scoring:** Chuẩn hóa BGE-M3 1024D Vector Cosine Scoring, mở rộng phễu BM25 Top 25 bảng, và thu nhỏ thang điểm cộng/trừ tay về tỷ lệ chuẩn (`+25đ` Metric Perfect, `+15đ` Substring, `+8đ` Secondary, `-200đ` Phạt bảng rác, `-100đ` Phạt bên liên quan/đầu tư tài chính).
8. **Modular 3-Part Architecture & Flexible Workflow (V17):** Phân chia độc lập Trạm 1 (Document Level - `DOCS_F2MACRO`), Trạm 2 (Table Level & Startline - `TABLES_F2MACRO`), Trạm 3 (Execution Level - Pandas & Calculation). Hỗ trợ chạy linh hoạt 3 chế độ (Tối ưu Bảng riêng, Tối ưu Code riêng, hoặc Liên hoàn Full Pipeline).
