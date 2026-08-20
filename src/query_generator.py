import json
import os
import sys
import re
import requests
import pandas as pd

# Configure standard output to UTF-8
sys.stdout.reconfigure(encoding='utf-8')

# API Config
LM_STUDIO_API_URL = "http://localhost:1234/api/v1/chat"
MODEL_NAME = "qwen2.5-coder-7b-instruct"

# Cờ báo hiệu lỗi LLM để tự động chuyển sang chế độ offline siêu nhanh
LLM_FAILED = (os.environ.get("FORCE_OFFLINE", "False") == "True")



def load_json_file(file_path):
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def find_column_indices(df):
    cols = [str(c) for c in df.columns]
    # Thiết lập mặc định
    code_col = '1' if '1' in cols else (cols[1] if len(cols) > 1 else cols[0])
    item_col = '0' if '0' in cols else cols[0]
    val_col = '3' if '3' in cols else (cols[-1] if len(cols) > 0 else '0')
    
    # Quét 3 dòng đầu tìm chữ tiêu đề
    for idx in range(min(len(df), 3)):
        row_vals = [str(df.iloc[idx, c]).strip().lower() for c in range(len(df.columns))]
        for c_idx, val in enumerate(row_vals):
            if 'mã số' in val or 'ma so' in val or 'code' in val:
                code_col = str(cols[c_idx])
            elif 'chỉ tiêu' in val or 'chi tieu' in val or 'item' in val:
                item_col = str(cols[c_idx])
                
    # Nếu bảng chỉ có 3 cột (Chỉ tiêu, Giá trị năm nay, Giá trị năm trước)
    # Ta cần kiểm tra xem cột '1' có thực sự chứa mã số kế toán hay chứa số liệu lớn
    if len(cols) == 3:
        if '1' in df.columns:
            col1_vals = df['1'].dropna().astype(str).str.strip().tolist()
            # Lọc các giá trị số nguyên ngắn dạng mã kế toán (độ dài <= 3 ký tự)
            small_digits = [v for v in col1_vals if v.replace('.', '').isdigit() and len(v.replace('.', '')) <= 3]
            non_empty = [v for v in col1_vals if v != '']
            
            # Nếu đa số (>50%) các giá trị không rỗng là mã kế toán ngắn, thì cột '1' mới là cột mã số
            if len(non_empty) > 0 and len(small_digits) / len(non_empty) > 0.5:
                code_col = '1'
                val_col = '2'
            else:
                code_col = None  # Không có cột mã số
                val_col = '1'    # Giá trị năm nay nằm ở cột '1'
        else:
            code_col = None
            val_col = '1'
    elif '3' in cols:
        val_col = '3'
    return code_col, item_col, val_col

def get_surrounding_text_from_report(r, num_lines_before=15, num_lines_after=120):
    ticker = r.get("ticker")
    year = r.get("year")
    report_id = r.get("report_id")
    start_line = r.get("start_line", 1)
    
    if not ticker or not year or not report_id:
        return ""
        
    possible_paths = [
        os.path.join('d:/ROAD_AI/financial_statements', str(ticker), str(year), report_id, f"{report_id}_extracted.txt"),
        os.path.join('d:/ROAD_AI/financial_statements', str(ticker), str(year), report_id, f"{report_id}.txt"),
    ]
    
    txt_path = None
    for p in possible_paths:
        if os.path.exists(p):
            txt_path = p
            break
            
    if not txt_path:
        return ""
        
    try:
        with open(txt_path, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
        start_idx = max(0, start_line - num_lines_before)
        end_idx = min(len(lines), start_line + num_lines_after)
        surrounding_lines = lines[start_idx:end_idx]
        text = "".join(surrounding_lines).strip()
        # Loại bỏ các bảng biểu HTML cồng kềnh để tránh n_keep context overflow
        text_clean = re.sub(r'<table.*?>.*?</table>', '[Bảng HTML đã ẩn]', text, flags=re.DOTALL | re.IGNORECASE)
        text_clean = re.sub(r'<tr.*?>.*?</tr>', '', text_clean, flags=re.DOTALL | re.IGNORECASE)
        text_clean = re.sub(r'<td.*?>.*?</td>', '', text_clean, flags=re.DOTALL | re.IGNORECASE)
        return text_clean.strip()
    except Exception:
        return ""

def get_table_schema_prompt(retrieved_tables, target_desc=None):
    schema_prompt = ""
    codes = target_desc.get("target_codes", []) if target_desc else []
    metrics = target_desc.get("target_metrics", []) if target_desc else []
    
    for idx, r in enumerate(retrieved_tables):
        var_name = f"df{idx+1}"
        csv_full_path = os.path.join('d:/ROAD_AI', r['csv_path'])
        schema_prompt += f"Bảng {var_name} (đường dẫn: {r['csv_path']}):\n"
        schema_prompt += f"Ngữ cảnh bảng: {r.get('table_context', '').strip()}\n"
        
        # Thêm đoạn văn bản thuyết minh xung quanh bảng từ file text gốc
        surrounding_text = get_surrounding_text_from_report(r)
        if surrounding_text:
            schema_prompt += f"Văn bản giải thích xung quanh bảng:\n[BẮT ĐẦU VĂN BẢN]\n{surrounding_text}\n[KẾT THÚC VĂN BẢN]\n"
        if os.path.exists(csv_full_path):
            try:
                df = pd.read_csv(csv_full_path, comment='#')
                df.columns = [str(i) for i in range(len(df.columns))]
                code_col, item_col, val_col = find_column_indices(df)
                
                # Chọn lọc dòng thông minh để giảm tối đa kích thước prompt tránh 500/OOM trong LM Studio
                rows_to_show = set(range(min(5, len(df))))
                rows_to_show.update(range(max(0, len(df)-2), len(df)))
                
                for row_idx, row in df.iterrows():
                    if code_col and code_col in df.columns:
                        val_code = str(row[code_col]).strip()
                        if val_code in codes:
                            rows_to_show.update(range(max(0, row_idx-1), min(len(df), row_idx+2)))
                    if item_col and item_col in df.columns:
                        val_item = str(row[item_col]).strip().lower()
                        for m in metrics:
                            if str(m).strip().lower() in val_item:
                                rows_to_show.update(range(max(0, row_idx-1), min(len(df), row_idx+2)))
                                
                sorted_rows = sorted(list(rows_to_show))
                df_subset = df.iloc[sorted_rows]
                
                schema_prompt += f"Dữ liệu bảng (Đoạn chọn lọc):\n"
                schema_prompt += df_subset.to_string() + "\n"
                if len(sorted_rows) < len(df):
                    schema_prompt += f"... [Đã ẩn {len(df) - len(sorted_rows)} dòng không liên quan] ...\n"
                
                schema_prompt += f"GỢI Ý CỘT CHO {var_name}: Cột mã số = '{code_col}', Cột chỉ tiêu = '{item_col}', Cột giá trị = '{val_col}'\n"
                
                if code_col in df.columns:
                    unique_codes = sorted(list(df[code_col].dropna().astype(str).str.strip().unique()))
                    # Chỉ hiển thị các mã số có độ dài ngắn (thường là mã kế toán từ 2-4 ký tự)
                    codes_clean = [c for c in unique_codes if len(c) <= 6 and c.replace('.', '').isdigit()]
                    schema_prompt += f"Mã số kế toán hiện có trong cột '{code_col}' của {var_name}: {codes_clean}\n"
            except Exception as e:
                schema_prompt += f"Lỗi load schema: {e}\n"
        else:
            schema_prompt += "File CSV không tồn tại.\n"
        schema_prompt += "-" * 50 + "\n"
    return schema_prompt

def generate_pandas_query(target_desc, retrieved_tables):
    global LLM_FAILED
    if LLM_FAILED:
        return fallback_query_generator(target_desc, retrieved_tables)
        
    if not retrieved_tables:
        return ""
        
    scaling = target_desc.get("scaling_factor", 1.0)
    is_percent = target_desc.get("is_percent", False)
    codes = target_desc.get("target_codes", [])
    
    # 1. HỆ THỐNG ĐỊNH HƯỚNG TỰ ĐỘNG (DETERMINISTIC FALLBACK)
    # Chỉ áp dụng nếu chỉ tiêu trong câu hỏi khớp với chỉ tiêu chuẩn của Thông tư 200 để tránh so khớp nhầm mã mục cha cho tiểu mục
    is_standard_metric = False
    try:
        with open('d:/ROAD_AI/configs/formulas_and_codes.json', 'r', encoding='utf-8') as f:
            f_db = json.load(f)
        standard_names = []
        for cat in ["balance_sheet", "income_statement", "cash_flow_statement_direct_and_indirect"]:
            standard_names.extend([k.lower().strip() for k in f_db["circular_200_standard_codes"].get(cat, {}).keys()])
        
        # Thêm từ đồng nghĩa của các chỉ tiêu chính
        for cat in ["balance_sheet_bank", "income_statement_bank", "balance_sheet_security", "income_statement_security"]:
            if cat in f_db.get("banking_and_securities_standard_codes", {}):
                standard_names.extend([k.lower().strip() for k in f_db["banking_and_securities_standard_codes"][cat].keys()])
                
        for m in target_desc.get("target_metrics", []):
            m_clean = str(m).lower().strip()
            # Khớp chính xác hoặc khớp từ đồng nghĩa quan trọng
            if m_clean in standard_names or any(s in m_clean for s in ["lợi nhuận sau thuế", "doanh thu thuần", "tổng tài sản", "vốn chủ sở hữu", "nợ phải trả"]):
                is_standard_metric = True
                break
    except Exception:
        is_standard_metric = False

    if os.environ.get("USE_DETERMINISTIC_GEN", "True") == "True" and not target_desc.get("formula_applied") and len(codes) > 0 and is_standard_metric:
        for idx, r in enumerate(retrieved_tables):
            csv_full_path = os.path.join('d:/ROAD_AI', r['csv_path'])
            if os.path.exists(csv_full_path):
                try:
                    df = pd.read_csv(csv_full_path, comment='#')
                    code_col, item_col, val_col = find_column_indices(df)
                    
                    # Chuẩn hóa cột df
                    df.columns = [str(c) for c in df.columns]
                    
                    # Thử khớp từng mã số gợi ý trong codes
                    for target_code in codes:
                        if code_col in df.columns:
                            rows = df[df[code_col].astype(str).str.strip() == str(target_code)]
                            if not rows.empty:
                                # Kiểm tra xem giá trị lấy ra có chứa số liệu không (tránh ô trống/NaN)
                                val_series = rows[val_col]
                                if not val_series.empty:
                                    val_raw = val_series.values[0]
                                    if pd.notna(val_raw) and str(val_raw).strip() != '' and str(val_raw).strip().lower() != 'nan':
                                        var_name = f"df{idx+1}"
                                        suffix = " * 100" if is_percent else ""
                                        query = f"float(pd.Series({var_name}[{var_name}['{code_col}'].astype(str).str.strip() == '{target_code}']['{val_col}'].values).replace(['-', '–', 'N/A', ''], '0').fillna('0').get(0, 0.0)) * {scaling}{suffix}"
                                        print(f"   [Deterministic Generator] Thành công! Sinh query từ mã {target_code} (không NaN): {query}")
                                        return query
                except Exception as e:
                    print(f"Warning: Lỗi sinh query deterministic cho {r['report_id']}: {e}")
                    
    # Nếu không phải câu hỏi có công thức và cũng không khớp deterministic thành công,
    # ta trả về tín hiệu để bypass LLM sang trực tiếp Fuzzy Matcher để tiết kiệm thời gian chạy (từ 40s -> 0.01s).
    if not target_desc.get("formula_applied"):
        print("   [Query Generator] Bypass LLM cho câu hỏi tra cứu thông thường.")
        return "FALLBACK_FUZZY_MATCH"

    print(f"--- BẮT ĐẦU SINH TRUY VẤN (Query Generator Phase) ---")
    print(f"Gọi Qwen2.5-Coder sinh câu lệnh Pandas...")
    
    # 1. Tạo chuỗi schema các bảng
    schema_prompt = get_table_schema_prompt(retrieved_tables, target_desc)
    
    # Lọc mã số đích gợi ý: Chỉ giữ lại các mã thực sự tồn tại trong các DataFrame được chọn
    valid_codes = []
    for code in target_desc.get("target_codes", []):
        code_exists = False
        for r in retrieved_tables:
            csv_path = os.path.join('d:/ROAD_AI', r['csv_path'])
            if os.path.exists(csv_path):
                try:
                    df = pd.read_csv(csv_path, comment='#')
                    code_col, _, _ = find_column_indices(df)
                    if code_col in df.columns:
                        if str(code).strip() in df[code_col].dropna().astype(str).str.strip().values:
                            code_exists = True
                            break
                except Exception:
                    pass
        if code_exists:
            valid_codes.append(code)
    target_codes_to_prompt = valid_codes
    
    # Tính toán chính xác phép chia đơn vị để truyền thẳng cho LLM
    scaling = target_desc.get("scaling_factor", 1.0)
    is_percent = target_desc.get("is_percent", False)
    
    divisor_str = "1e9"
    unit_instruction = ""
    if scaling == 1e-9:
        unit_instruction = "BẮT BUỘC: Phép toán phải chia cho 1e9 (ví dụ: / 1e9)"
        divisor_str = "1e9"
    elif scaling == 1e-6:
        unit_instruction = "BẮT BUỘC: Phép toán phải chia cho 1e6 (ví dụ: / 1e6)"
        divisor_str = "1e6"
    elif scaling == 1.0:
        unit_instruction = "Giữ nguyên đơn vị gốc (không chia tỷ lệ)"
        divisor_str = "1"
    else:
        unit_instruction = f"BẮT BUỘC: Nhân với {scaling}"
        divisor_str = f"(1/{scaling})"
        
    if is_percent:
        unit_instruction += " và nhân thêm với 100 ở cuối (ví dụ: * 100)"
        
    # Detect if there are consecutive tables from the same report (split tables)
    continuation_hints = []
    for idx_a in range(len(retrieved_tables)):
        for idx_b in range(idx_a + 1, len(retrieved_tables)):
            r_a = retrieved_tables[idx_a]
            r_b = retrieved_tables[idx_b]
            if r_a.get("report_id") == r_b.get("report_id") and abs(r_a.get("table_index", 0) - r_b.get("table_index", 999)) == 1:
                df_a_name = f"df{idx_a+1}"
                df_b_name = f"df{idx_b+1}"
                continuation_hints.append(
                    f"6. Split Table: {df_a_name} and {df_b_name} are contiguous pages of the SAME table. "
                    f"If the queried information spans both or is on the second page, you can combine them using `pd.concat([{df_a_name}, {df_b_name}])`."
                )
    split_table_rule = ""
    if continuation_hints:
        split_table_rule = "\n".join(continuation_hints) + "\n"
        
    # 2. Xây dựng System Prompt với Kiến thức Tài chính Kế toán Chuyên sâu & 5 Quy tắc Vàng
    system_prompt = (
        "You are a Senior Vietnamese Financial Analyst & Python Pandas Expert deeply familiar with Circular 200/2014/TT-BTC, Banking TT49/2014/TT-NHNN, and Securities TT210/2014/TT-BTC.\n"
        "FINANCIAL DOMAIN KNOWLEDGE SYSTEM:\n"
        "- Balance Sheet (Bảng Cân đối Kế toán): Code 100 (Current Assets), Code 200 (Non-current Assets), Code 300 (Liabilities), Code 400 (Equity). Fundamental Formula: Code 100 + Code 200 = Code 300 + Code 400.\n"
        "- Income Statement (Báo cáo Kết quả Kinh doanh): Code 01 (Gross Revenue), Code 10 (Net Revenue), Code 20 (Gross Profit), Code 21 (Financial Income), Code 30 (Net Operating Profit), Code 50 (Profit Before Tax), Code 60 (Net Profit After Tax).\n"
        "- Cash Flow Statement (Báo cáo Lưu chuyển Tiền tệ): Operating Cash Flow (Code 20), Investing Cash Flow (Code 30), Financing Cash Flow (Code 40).\n"
        "- Notes (Thuyết minh BCTC): Thuyết minh Tiền gửi, Vay và Nợ thuê tài chính, Doanh thu tài chính, Chi phí QLDN, Chi phí Bán hàng, Tài sản thế chấp.\n"
        "- Banking & Securities Chart of Accounts: FVTGL (Tài sản tài chính ghi nhận thông qua lãi/lỗ), HTM (Đầu tư giữ đến ngày đáo hạn), AFS (Tài sản tài chính sẵn sàng để bán), Cho vay khách hàng, Tiền gửi khách hàng.\n\n"
        "DATA STRUCTURE:\n"
        f"{schema_prompt}\n\n"
        "RULES FOR QUERY GENERATION:\n"
        "1. Columns are strings: '0', '1', '2', '3'...\n"
        "2. Text Filtering: Use `df1[df1['0'].astype(str).str.contains('keyword', case=False, na=False)]`.\n"
        "3. Keywords: Use 2-3 core financial accounting terms only. Never include years or company names in contains().\n"
        "4. Safe Series Access: To prevent IndexError/ValueError, convert to Series and use `.get(0, 0.0)`. Never use `.values[0]`. "
        "Example: `float(pd.Series(df1[df1['1'].astype(str).str.strip() == '200']['3'].values).replace(['-', '–', 'N/A', ''], '0').fillna('0').get(0, 0.0))`\n"
        f"5. Scale: {unit_instruction}.\n"
        f"{split_table_rule}"
    )
    
    formula_info = ""
    if target_desc.get("formula_applied") and target_desc.get("formula_details"):
        details = target_desc["formula_details"]
        formula_info = (
            f"\n[BẮT BUỘC CHÚ Ý] CÔNG THỨC TÀI CHÍNH CẦN ÁP DỤNG: {target_desc['formula_applied']}\n"
            f"- Công thức lý thuyết: {details.get('formula')}\n"
            f"- Hướng dẫn nghiệp vụ: {details.get('description')}\n"
            f"- Biểu mẫu cấu trúc Pandas gợi ý: {details.get('pandas_logic')}\n"
            f"Hãy tự động đổi tên DataFrame (như balance_df -> df1, income_df -> df1) và tên cột (như 'val' -> '3') để tương thích với các DataFrame thực tế của bạn.\n"
        )
        
    user_input = (
        f"Câu hỏi: {target_desc['question']}\n"
        f"Chỉ tiêu cần tìm: {target_desc['target_metrics']}\n"
        f"Mã số kế toán đích gợi ý: {target_codes_to_prompt}\n"
        f"Đơn vị quy đổi: {target_desc['unit']}\n"
        f"Quy định phép chia/nhân đơn vị: {unit_instruction}\n"
        f"{formula_info}"
    )
    
    payload = {
        "model": MODEL_NAME,
        "system_prompt": system_prompt,
        "input": user_input,
        "max_tokens": 128
    }
    
    # Thử gọi qua nhiều Endpoint khác nhau của LM Studio để đảm bảo tương thích mọi phiên bản
    content = ""
    success = False
    
    # 1. Thử OpenAI-compatible chat completions (Khuyên dùng cho LM Studio mới)
    try:
        openai_url = "http://localhost:1234/v1/chat/completions"
        openai_payload = {
            "model": MODEL_NAME,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_input}
            ],
            "temperature": 0.0,
            "max_tokens": 128
        }
        response = requests.post(openai_url, json=openai_payload, timeout=60)
        if response.status_code == 200:
            data = response.json()
            if "choices" in data and len(data["choices"]) > 0:
                content = data["choices"][0]["message"]["content"]
                success = True
                print("   [LM Studio API] Gọi thành công qua cổng OpenAI-compatible Chat Completions!")
    except Exception:
        pass

    # 2. Thử REST API v1 chat (Cấu hình cũ của LM Studio)
    if not success:
        try:
            response = requests.post("http://localhost:1234/api/v1/chat", json=payload, timeout=5)
            if response.status_code == 200:
                data = response.json()
                if "output" in data and len(data["output"]) > 0:
                    content = data["output"][0]["content"]
                    success = True
                    print("   [LM Studio API] Gọi thành công qua cổng REST API v1 Chat!")
                elif "choices" in data and len(data["choices"]) > 0:
                    content = data["choices"][0]["message"]["content"]
                    success = True
                    print("   [LM Studio API] Gọi thành công qua cổng REST API v1 Chat (choices)!")
        except Exception:
            pass

    if not success:
        print("Warning: Lỗi gọi LM Studio API để sinh code. Sử dụng Fallback cho câu hỏi này...")
        return fallback_query_generator(target_desc, retrieved_tables)
        
    # Loại bỏ thẻ suy nghĩ <think>...</think> của DeepSeek R1 (nếu có)
    if "<think>" in content and "</think>" in content:
        content = content.split("</think>")[-1].strip()
    elif "<think>" in content:
        content = content.split("<think>")[-1].strip()
    
    # Làm sạch câu lệnh (bỏ dấu ```python hoặc ``` ở đầu/cuối nếu LLM tự thêm vào)
    query_clean = content.replace("```python", "").replace("```", "").strip()
    # Thay thế xuống dòng nếu có (đảm bảo 1 dòng)
    query_clean = query_clean.replace("\n", " ").strip()
    
    return query_clean

def fallback_query_generator(target_desc, retrieved_tables):
    scaling = target_desc.get("scaling_factor", 1.0)
    codes = target_desc.get("target_codes", [])
    is_percent = target_desc.get("is_percent", False)
    suffix = " * 100" if is_percent else ""
    
    # Tìm cột thực tế bằng find_column_indices
    code_col, item_col, val_col = None, '0', '1'
    if retrieved_tables:
        r = retrieved_tables[0]
        csv_full_path = os.path.join('d:/ROAD_AI', r['csv_path'])
        if os.path.exists(csv_full_path):
            try:
                df_temp = pd.read_csv(csv_full_path, comment='#')
                df_temp.columns = [str(i) for i in range(len(df_temp.columns))]
                code_col, item_col, val_col = find_column_indices(df_temp)
            except Exception:
                pass
                
    if len(codes) > 0 and code_col:
        code = codes[0]
        return f"(pd.to_numeric(df1[df1['{code_col}'].astype(str).str.strip() == '{code}']['{val_col}'], errors='coerce').dropna().iloc[0] if len(df1[df1['{code_col}'].astype(str).str.strip() == '{code}']) > 0 else 0.0) * {scaling}{suffix}"
    else:
        metric = target_desc["target_metrics"][0] if target_desc["target_metrics"] else ""
        metric_keyword = re.sub(r'[\(\)\[\]\{\}\?\!\.\,\:\'\"]', '', metric).strip()
        metric_keyword = " ".join(metric_keyword.split()[:3])
        return f"(pd.to_numeric(df1[df1['{item_col}'].astype(str).str.contains('{metric_keyword}', case=False, na=False)]['{val_col}'], errors='coerce').dropna().iloc[0] if len(df1[df1['{item_col}'].astype(str).str.contains('{metric_keyword}', case=False, na=False)]) > 0 else 0.0) * {scaling}{suffix}"

if __name__ == '__main__':
    # Chạy thử nghiệm Bước 1, 2, 3 rồi sinh code
    try:
        from intent_analyzer import build_target_description
        from hard_filter import apply_hard_filter
        from retriever import retrieve_relevant_tables
    except ImportError:
        print("Error: Không tìm thấy intent_analyzer.py hoặc hard_filter.py hoặc retriever.py!")
        sys.exit(1)
        
    test_q = "Lợi nhuận sau thuế của CTCP Chứng khoán FPT năm 2023 là bao nhiêu tỷ đồng?"
    if len(sys.argv) > 1:
        test_q = " ".join(sys.argv[1:])
        
    print(f"Câu hỏi test: '{test_q}'\n")
    
    # 1. Phân tích ý định
    target_desc = build_target_description(test_q)
    
    # 2. Load metadata
    with open('d:/ROAD_AI/metadata.json', 'r', encoding='utf-8') as f:
        metadata_db = json.load(f)
        
    # 3. Lọc ứng viên
    candidates = apply_hard_filter(target_desc, metadata_db)
    
    # 4. Truy xuất bảng
    retrieved_tables = retrieve_relevant_tables(target_desc, candidates, top_n=2)
    
    # 5. Sinh câu truy vấn
    query = generate_pandas_query(target_desc, retrieved_tables)
    print(f"\n-> PANDAS QUERY SINH RA:")
    print(query)
