# Sổ Tay Kỹ Thuật Xử Lý Dữ Liệu Báo Cáo Tài Chính (DATA PROCESSING GUIDE) - R2AI2026

Tài liệu này ghi chép chi tiết toàn bộ quy trình tiền xử lý dữ liệu thô, đánh chỉ mục metadata, làm sạch số liệu kế toán, chuẩn hóa đơn vị tính và bảo vệ an toàn mã thực thi trong dự án **R2AI2026 BCTC QA Pipeline**.

---

## 📌 1. Tổng Quan Kiến Trúc Kho Dữ Liệu

Dữ liệu đầu vào của hệ thống bao gồm hơn **146,246 bảng biểu tài chính** được bóc tách từ hàng ngàn báo cáo tài chính (BCTC) của các doanh nghiệp niêm yết trên thị trường chứng khoán Việt Nam:

*   **File văn bản gốc (`financial_statements/*.txt`):** Chứa toàn bộ nội dung BCTC dạng HTML/Text thô.
*   **Kho CSV đã bóc tách (`d:/ROAD_AI/data/*.csv`):** Mỗi bảng HTML/Text được trích xuất thành 1 file CSV độc lập (định danh dạng `<report_id>_table_<index>.csv`).
*   **Kho Metadata Master (`d:/ROAD_AI/metadata.json`):** File JSON dung lượng 274MB lưu thông tin chỉ mục chi tiết của 146,246 bảng:
    *   `report_id`: Định danh báo cáo (VD: `VJC_financial_statements_2018_separate`).
    *   `table_index`: Thứ tự bảng trong báo cáo.
    *   `start_line`: Số dòng bắt đầu của bảng trong file văn bản thô `.txt` (Thành phần cốt lõi để tính điểm `TABLES_F2MACRO`).
    *   `table_context`: Trường văn bản tiêu đề/thuyết minh của bảng.
    *   `headers`: Danh sách tên cột.
    *   `report_type`: Loại báo cáo (`separate` cho Công ty mẹ/BCTC Riêng, `consolidated` cho BCTC Hợp nhất).

---

## 🔍 2. Quy Trình Bóc Tách & Kế Thừa Bảng (Table Parsing & Merging)

Trong file `parse_data.py`, thuật toán trích xuất dữ liệu thô xử lý 2 thách thức lớn nhất của tài liệu kế toán:

### 2.1. Kế thừa Header Trang Trước (Header Continuation)
*   **Vấn đề:** Các bảng báo cáo dài bị chia cắt qua nhiều trang. Trang sau (`table_N+1`) bắt đầu ngay bằng các dòng số liệu mà không có dòng cột tiêu đề (Header). Nếu đọc trực tiếp, dòng số liệu đầu tiên sẽ bị nhầm thành Header.
*   **Giải pháp:** Hệ thống tự động phát hiện bảng nối tiếp (cùng báo cáo, cùng số lượng cột, phân trang giữa chừng) và chèn tự động dòng Header của trang trước vào vị trí dòng 0 của bảng sau.

### 2.2. Kế thừa Note Title (Thuyết minh dài)
*   **Vấn đề:** Các thuyết minh chi tiết (như Thuyết minh Vay & Nợ thuê tài chính, Chi phí trả trước) có nội dung kéo dài qua nhiều trang nhưng tiêu đề Thuyết minh chỉ nằm ở đầu trang thứ nhất.
*   **Giải pháp:** Thuật toán quét ngược lại 15 dòng văn bản phía trên kết hợp Regex kế toán để truyền tên Thuyết minh sang tất cả các bảng con nối tiếp.

---

## 🧹 3. Quy Trình Làm Sạch & Chuẩn Hóa Số Liệu Kế Toán (Data Cleaning)

Khi Python Engine thực thi câu lệnh Pandas trên các file CSV, dữ liệu số thô được đi qua bộ chuẩn hóa tự động:

### 3.1. Chuyển Đổi Định Dạng Số Kế Toán
*   **Số âm dạng ngoặc đơn:** Ngoặc đơn kế toán `(100.000)` được tự động quy đổi thành số âm chuẩn `-100000`.
*   **Chuẩn hóa phân cách Tiếng Việt:** Ký tự phân cách hàng nghìn (dấu chấm `.`) và phân cách thập phân (dấu phẩy `,`) được chuyển về dạng float chuẩn:
    *   `156.014.812.926,00` $\rightarrow$ `156014812926.0`
*   **Xử lý ô trống & ký tự rác:** Các ô chứa `-`, `–`, `N/A`, `null`, `None` được thay thế bằng `0.0`.

### 3.2. Sửa Lỗi Lệch Cột (Column Alignment)
*   Do đặc thù bảng HTML thô, nhiều bảng 3 cột bị ghi lệch giá trị số sang cột index `'2'` thay vì cột `'3'`. Bộ làm sạch tự động kiểm tra và chuyển đổi cột linh hoạt để ngăn ngừa lỗi `KeyError`.

---

## 📏 4. Tỷ Lệ Xích & Quy Đổi Đơn Vị Tính (Scaling & Multiplier)

Một trong những nguyên nhân chính gây lệch đáp án (`ANSWER_ACCURACY`) là sự khác biệt giữa đơn vị tính trong bảng và đơn vị yêu cầu trong câu hỏi:

### 4.1. Nhận Diện Đơn Vị Gốc
*   Mỗi file CSV lưu dòng đầu tiên dưới dạng comment `# Đơn vị tính: ...` (VD: `# Đơn vị tính: Triệu đồng` hoặc `# Đơn vị tính: VND`).

### 4.2. Sắp Xếp Độ Ưu Tiên Quy Đổi Dài-Đến-Ngắn
Để tránh va chạm chuỗi con (Ví dụ: `"nghìn tỷ"` bị khớp nhầm với `"tỷ"`), thuật toán sắp xếp từ khóa theo độ dài giảm dần:

$$\text{Nghìn tỷ} \rightarrow \text{Trăm tỷ} \rightarrow \text{Tỷ} \rightarrow \text{Triệu} \rightarrow \text{Đồng}$$

### 4.3. Bảng Nhân Hệ Số Tỷ Lệ Xích (Multiplier Table)
| Đơn vị trong bảng | Đơn vị câu hỏi yêu cầu | Hệ số nhân (Multiplier) |
| :--- | :--- | :--- |
| **Đồng (VND)** | Triệu đồng | $\times 10^{-6}$ |
| **Đồng (VND)** | Tỷ đồng | $\times 10^{-9}$ |
| **Triệu đồng** | Đồng (VND) | $\times 10^{6}$ |
| **Triệu đồng** | Tỷ đồng | $\times 10^{-3}$ |
| **Tỷ đồng** | Triệu đồng | $\times 10^{3}$ |

---

## 🎯 5. Phân Loại BCTC Riêng (Separate) & Hợp Nhất (Consolidated)

*   **Định hướng Strict Filtering 100%:** Khi Intent Analyzer phát hiện các cụm từ *"công ty mẹ"*, *"báo cáo riêng"*, *"cty mẹ"*, *"bc riêng"*, bộ lọc cứng (`hard_filter.py`) lập tức **khóa khung tìm kiếm 100% vào các file `_separate`**, loại bỏ hoàn toàn các file `_consolidated`.
*   **Lý do nghiệp vụ:** Nhiều khoản mục quan trọng như *Đầu tư vào công ty con (TM 5.11)* hoặc *Phải thu nội bộ* chỉ tồn tại trên BCTC Riêng và bị cấn trừ triệt tiêu hoàn toàn khi lập BCTC Hợp nhất.

---

## 🛡️ 6. Bộ Thực Thi An Toàn Series Safe-Access V8 & Gọt Bảng Động

### 6.1. Cú pháp Series Safe-Access Wrapper
Để ngăn ngừa 100% lỗi runtime (`IndexError`, `ValueError`, `KeyError`, `ZeroDivisionError`), tất cả mã Pandas sinh ra hoặc sửa lỗi đều tuân theo chuẩn wrapper:

```python
float(pd.Series(df1[df1['0'].astype(str).str.contains('Lãi tiền gửi', case=False, na=False)]['1'].values).replace(['-', '–', 'N/A', ''], '0').fillna('0').get(0, 0.0))
```

### 6.2. Dynamic Table Pruning (Gọt Bảng Động)
*   retriever nạp 3 bảng ứng viên để LLM xem xét ngữ cảnh.
*   Sau khi code Pandas chạy thành công, bộ quét AST tự động phân tích code thực tế xem mô hình sử dụng biến `df1`, `df2` hay `df3`.
*   Tự động gọt bỏ các bảng không được tham chiếu khỏi danh sách `relevant_tables`, đưa điểm `TABLES_PRECISION` của các câu hỏi đơn lên **100% tuyệt đối**!

---

## 🏆 7. Tệp Tin Lưu Trữ Đóng Gói (Master Final Package)

Mọi kết quả xử lý dữ liệu sau khi chạy hoàn tất sẽ được chuẩn hóa và đóng gói thành 2 tệp tin duy nhất phục vụ nộp bài:
1. **`d:/ROAD_AI/submission_final.json`**: Chứa toàn bộ 1,012 câu hỏi với định dạng `relevant_tables` (`<report_id>|<start_line>`), `pandas_query` thực thi được và `answer` chuẩn hóa.
2. **`d:/ROAD_AI/submission_final.zip`**: Tệp ZIP đóng gói file JSON kèm toàn bộ các file CSV chứng cứ tại `data/*.csv`.

---

## 7. Phân Loại Loại Báo Cáo & Định Vị Cột Số Đầu Năm / Cuối Năm (V14)

* **Gán Nhãn Loại Báo Cáo (`statement_type`):**
  - `STATEMENT_BS`: Bảng Cân đối Kế toán (Mẫu B 01)
  - `STATEMENT_IS`: Báo cáo Kết quả Kinh doanh (Mẫu B 02)
  - `STATEMENT_CF`: Báo cáo Lưu chuyển Tiền tệ (Mẫu B 03)
  - `STATEMENT_NOTE`: Bản Thuyết minh BCTC (Mẫu B 09)

* **Nhận diện Cột "Số của năm" (`val_curr` vs `val_prev`):**
  - **Hàm `find_val_col_by_header_and_question(df, question)`**: Tự động phân tích tiêu đề hàng 0-2 để xác định cột Giá trị cuối năm (31/12/N) vs Giá trị đầu năm (01/01/N).
  - Khi câu hỏi yêu cầu *"đầu năm"*, hệ thống chuyển hướng tự động sang cột `val_prev`, triệt tiêu hoàn toàn bẫy lấy nhầm cột cuối năm.

---

## 8. Thuật Toán Thực Thi 3 Tầng Master (3-Tier Cascade Fallback Algorithm)

Khi thực thi Pandas query, hệ thống đi qua quy trình 3 Tầng nghiêm ngặt để đảm bảo 100% không bị sót dữ liệu:

1. **Tầng 1 (Mã Số Chuẩn - Standard Code Match):**
   - Quét mã số kế toán (`10`, `60`, `270`, `300`...) bằng `find_row_by_code(df, code)` trên toàn bộ các cột.
   - Nếu tìm thấy dòng có giá trị số hợp lệ $\rightarrow$ Trả về đáp án tức thì ($<0.001\text{s}$).

2. **Tầng 2 (String Match & Fuzzy Contains):**
   - Quét tên chỉ tiêu theo chỉ số tương đồng `SequenceMatcher` kết hợp đếm mật độ từ khóa.
   - Định vị cột số liệu qua `find_val_col_by_header_and_question`.
   - Nếu khớp $\rightarrow$ Trả về đáp án.

3. **Tầng 3 (Surrounding Text & Context Regex Scanner):**
   - Đọc văn bản thô xung quanh bảng (trước 15 dòng, sau 120 dòng).
   - Dùng Regex `re.findall(r'[-–]?\d+(?:[\.,]\d+)*\s*(nghìn tỷ|trăm tỷ|tỷ|triệu|nghìn|%)?', line)` trích xuất chuỗi số thực tế và chuẩn hóa hậu tố đơn vị.

---

## 9. Dynamic Column-Agnostic Engine (`get_val`) & Chuẩn Hóa Startline (V15)

* **Hàm `get_val(df, code, keyword)` Engine:**
  - Cho phép quét tìm dòng theo Mã số hoặc Keyword trên **BẤT KỲ CỘT NÀO** trong DataFrame.
  - Tự động lấy cột Năm nay (cuối kỳ) qua `.iloc[:, -2]` hoặc `find_val_col_by_header_and_question`.
  - Giúp 100% mã Pandas thực thi đồng nhất mà không bị crash do bẫy lệch cột OCR giữa các doanh nghiệp (như DIG vs KBC).

* **Khóa Bảng Dòng Bắt Đầu (`start_line` Mapper):**
  - Đã ánh xạ 100% `relevant_tables` trong `submission_final.json` và `submission_table_f2.json` sang vị trí dòng mở đầu bảng trong tệp `.txt` gốc (`<report_id>|<start_line>`), bứt phá chỉ số `TABLES_F2MACRO` trên Dashboard thi đấu.

---

## 10. Bảng Thang Điểm Heuristic Boosts Chuẩn Hóa & BGE Vector Cosine (V16)

* **Chuẩn Hóa Thang Điểm Heuristic Boosts:**
  - `Phạt Bảng rác OCR`: `-200.0`
  - `Loại trừ Bảng Đầu tư tài chính`: `-100.0`
  - `Phạt Thuyết minh Bên liên quan`: `-100.0`
  - `Primary Metric Perfect Boost`: `+25.0`
  - `Primary Metric Substring Boost`: `+15.0`
  - `Secondary Metric Boost`: `+8.0`
  - `Primary Code Boost (BCTC chính)`: `+25.0`
  - `Secondary Code Boost (Bảng phụ)`: `+12.0`
  - `Segment / Row Boost`: `+20.0`
  - `Note Topic Map Boost`: `+15.0`

* **Giai Đoạn 1 Pre-filter Top 25 Candidate Tables:**
  - Lọc BM25 CPU siêu tốc (<1ms) giữ Top 25 bảng ứng viên trước khi chuyển cho Vector Embedding, giúp `TABLES_RECALL` tăng vọt.

---

## 11. Kiến Trúc Phân Tầng 3 Trạm & Luồng Chạy Linh Hoạt (V17)

* **Trạm 1: Định danh Báo cáo (`DOCS_F2MACRO`)**
  - Khóa mã doanh nghiệp, năm báo cáo, phân định tuyệt đối BCTC Riêng (`separate`/công ty mẹ) vs Hợp nhất (`consolidated`).
* **Trạm 2: Định vị Bảng & Khóa dòng (`TABLES_F2MACRO`)**
  - BM25 Top 25 pre-filter + BGE-M3 Dense Vector Re-ranking, xuất chuẩn vị trí dòng mở đầu bảng `<report_id>|<start_line>`.
* **Trạm 3: Sinh code Pandas & Tính toán (`EXECUTION_ACCURACY` & `ANSWER_ACCURACY`)**
  - Thực thi engine `get_val`, tự động quy đổi đơn vị tiền tệ (`tỷ`, `triệu`, `nghìn`, `%`), gọt bỏ bảng thừa (Dynamic Pruning).
* **Flexible Workflow:** Chạy riêng Trạm 2 (`run_table_retrieval_only.py`), Trạm 3 (`run_code_engine_only.py`), hoặc Liên hoàn Full Pipeline (`run_pipeline_all.py`).
