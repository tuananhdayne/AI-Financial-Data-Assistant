import json
import os
import sys
import traceback
import numpy as np
import pandas as pd
import requests
import difflib
import re

# Configure standard output to UTF-8
sys.stdout.reconfigure(encoding='utf-8')

# API Config
LM_STUDIO_API_URL = "http://localhost:1234/api/v1/chat"
MODEL_NAME = "qwen2.5-coder-7b-instruct"

def load_json_file(file_path):
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def find_column_indices(df):
    cols = [str(c) for c in df.columns]
    code_col = '1' if '1' in cols else (cols[1] if len(cols) > 1 else cols[0])
    item_col = '0' if '0' in cols else cols[0]
    val_col = '3' if '3' in cols else (cols[-1] if len(cols) > 0 else '0')
    
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
def find_row_by_code(df, code):
    """
    DYNAMIC COLUMN DETECTOR:
    Tự động quét toàn bộ các cột trong DataFrame để tìm chuỗi khớp với Mã số kế toán (VD: '60', '10', '270').
    Loại bỏ nguy cơ KeyError và lệch vị trí cột khi cấu trúc OCR thay đổi.
    """
    code_str = str(code).strip()
    for col in df.columns:
        try:
            matched = df[df[col].astype(str).str.strip() == code_str]
            if len(matched) > 0:
                return matched
        except Exception:
            pass
    return pd.DataFrame()

def get_val(df, code="", keyword=""):
    """
    TRỤ CỘT 3: DYNAMIC COLUMN-AGNOSTIC ENGINE
    Tự động tìm dòng theo Mã số hoặc Keyword tên chỉ tiêu trên BẤT KỲ CỘT NÀO.
    Tự động lấy cột Năm nay (cuối kỳ) qua .iloc[:, -2] hoặc find_val_col_by_header_and_question.
    """
    if df is None or len(df) == 0:
        return 0.0
    
    code_str = str(code).strip() if code else ""
    kw_str = str(keyword).strip().lower() if keyword else ""
    
    filtered = pd.DataFrame()
    if code_str:
        filtered = find_row_by_code(df, code_str)
        
    if filtered.empty and kw_str:
        for col in df.columns[:2]:
            try:
                matched = df[df[col].astype(str).str.lower().str.contains(kw_str, case=False, na=False)]
                if len(matched) > 0:
                    filtered = matched
                    break
            except Exception:
                pass
                
    if filtered.empty:
        return 0.0
        
    if len(filtered.columns) >= 3:
        val_series = filtered.iloc[:, -2]
    else:
        val_series = filtered.iloc[:, -1]
        
    clean = (
        val_series.astype(str)
        .str.replace(r'[^\d.-]', '', regex=True)
        .replace(['', '-', '–', 'N/A', 'nan', 'NaN'], '0')
    )
    
    try:
        vals = pd.to_numeric(clean, errors='coerce').fillna(0.0)
        return float(vals.iloc[0]) if len(vals) > 0 else 0.0
    except Exception:
        return 0.0

def find_val_col_by_header_and_question(df, question=None):
    """
    1. PHÂN BIỆT "SỐ ĐẦU NĂM" VS "SỐ CUỐI NĂM" TRONG FIND_VAL_COL:
    Nhận diện cột Giá trị cuối năm (31/12) vs Số đầu năm (01/01) dựa trên Header và Yêu cầu câu hỏi.
    """
    cols = [str(c) for c in df.columns]
    res = find_column_indices(df)
    if res and len(res) >= 3:
        _, _, default_val_col = res
    else:
        default_val_col = cols[-1] if cols else '0'
    
    val_curr_col = default_val_col
    val_prev_col = None
    
    q_lower = str(question).lower() if question else ""
    is_beginning_of_year = any(kw in q_lower for kw in ['đầu năm', 'dau nam', '01/01', 'đầu kỳ', 'dau ky', 'số đầu năm', 'đầu tháng'])
    is_end_of_year = any(kw in q_lower for kw in ['cuối năm', 'cuoi nam', '31/12', 'cuối kỳ', 'cuoi ky', 'số cuối năm', 'cuối tháng'])
    
    q_years = re.findall(r'\b(20\d{2})\b', q_lower) if question else []
    
    if len(cols) >= 3:
        for idx in range(min(len(df), 3)):
            row_vals = [str(df.iloc[idx, c]).strip().lower() for c in range(len(cols))]
            
            for c_idx, val in enumerate(row_vals):
                if c_idx < 1:
                    continue
                # Nhận diện cột Số đầu năm (01/01 / Số đầu năm / Năm trước)
                if any(kw in val for kw in ['01/01', 'đầu năm', 'dau nam', 'năm trước', 'nam truoc', 'số đầu năm']):
                    val_prev_col = str(cols[c_idx])
                # Nhận diện cột Số cuối năm (31/12 / Số cuối năm / Năm nay)
                elif any(kw in val for kw in ['31/12', 'cuối năm', 'cuoi nam', 'năm nay', 'nam nay', 'số cuối năm']):
                    val_curr_col = str(cols[c_idx])
                    
            # Khớp số năm cụ thể giữa câu hỏi và header (ví dụ 2020 vs 2019)
            if q_years:
                for target_y in q_years:
                    for c_idx, val in enumerate(row_vals):
                        if target_y in val and c_idx >= 1:
                            if is_beginning_of_year:
                                val_prev_col = str(cols[c_idx])
                            else:
                                val_curr_col = str(cols[c_idx])

    if is_beginning_of_year and val_prev_col is not None:
        return val_prev_col
        
    return val_curr_col

def get_table_schema_prompt(retrieved_tables):
    schema_prompt = ""
    for idx, r in enumerate(retrieved_tables):
        var_name = f"df{idx+1}"
        csv_full_path = os.path.join('d:/ROAD_AI', r['csv_path'])
        schema_prompt += f"Bảng {var_name} (đường dẫn: {r['csv_path']}):\n"
        if os.path.exists(csv_full_path):
            try:
                df = pd.read_csv(csv_full_path, comment='#')
                df.columns = [str(i) for i in range(len(df.columns))]
                df_preview = df.head(5)
                schema_prompt += df_preview.to_string() + "\n"
                
                # Trích xuất danh sách các mã số có trong bảng này để chỉ dẫn cho LLM
                code_col, item_col, val_col = find_column_indices(df)
                schema_prompt += f"GỢI Ý CỘT CHO {var_name}: Cột mã số = '{code_col}', Cột chỉ tiêu = '{item_col}', Cột giá trị = '{val_col}'\n"
                
                if code_col in df.columns:
                    unique_codes = sorted(list(df[code_col].dropna().astype(str).str.strip().unique()))
                    codes_clean = [c for c in unique_codes if len(c) <= 6 and c.replace('.', '').isdigit()]
                    schema_prompt += f"Mã số kế toán hiện có trong cột '{code_col}' của {var_name}: {codes_clean}\n"
            except Exception as e:
                schema_prompt += f"Lỗi load schema: {e}\n"
        else:
            schema_prompt += "File CSV không tồn tại.\n"
        schema_prompt += "-" * 50 + "\n"
    return schema_prompt

def fallback_fuzzy_match(df, target_metrics, item_col, val_col, question=None):
    best_row_idx = None
    best_score = -1.0
    best_val = None
    
    # Chuẩn hóa target metrics và câu hỏi
    metrics_clean = [str(m).strip().lower() for m in target_metrics]
    q_lower = str(question).lower() if question else ""
    
    for idx, row in df.iterrows():
        # Lấy tên chỉ tiêu trong bảng
        item_text = str(row[item_col]).strip() if pd.notna(row[item_col]) else ""
        item_text_lower = item_text.lower()
        if not item_text or item_text_lower in ['chỉ tiêu', 'chi tieu', 'item', 'b', 'a']:
            continue
            
        # Kiểm tra xem giá trị có hợp lệ không
        val_raw = row[val_col] if val_col in df.columns else None
        if pd.isna(val_raw) or str(val_raw).strip() == "" or str(val_raw).strip().lower() == "nan":
            continue
            
        try:
            # Làm sạch số liệu
            val_str = str(val_raw).replace(',', '').replace('(', '-').replace(')', '').strip()
            val_clean = "".join(val_str.split())
            val_float = float(val_clean)
        except Exception:
            continue
            
        # Tính điểm tương đồng
        max_score_for_row = 0.0
        for m_clean in metrics_clean:
            # Tách từ khóa
            m_words = [w for w in m_clean.replace('.', ' ').replace(',', ' ').replace('(', ' ').replace(')', ' ').split() if len(w) > 1]
            if not m_words:
                continue
                
            # Đếm số từ khóa xuất hiện trong chỉ tiêu của bảng
            matches = 0
            for w in m_words:
                if w in item_text_lower:
                    matches += 1
                    
            word_score = matches / len(m_words)
            
            # Tính độ tương đồng chuỗi tổng thể làm tie-breaker (thêm tối đa 0.09)
            seq_score = difflib.SequenceMatcher(None, item_text_lower, m_clean).ratio()
            
            score = word_score + seq_score * 0.09
            
            # Cộng thêm điểm nếu khớp đúng cụm từ liên tục
            if m_clean in item_text_lower:
                score += 0.1
                
            # Boost for "tổng cộng" / "cộng" if question is asking for total
            if item_text_lower in ['tổng cộng', 'cộng', 'tổng']:
                has_total_keyword = "tổng" in q_lower or "cộng" in q_lower or any("tổng" in m or "cộng" in m for m in metrics_clean)
                if has_total_keyword:
                    if score < 0.65:
                        score = 0.65
                
            # Kiểm tra khớp từ khóa phân khúc / dòng đặc thù từ câu hỏi
            if len(item_text_lower) >= 4 and item_text_lower not in ['tổng cộng', 'cộng', 'trong đó', 'chỉ tiêu', 'mã số', 'thuyết minh', 'năm nay', 'năm trước']:
                if q_lower and item_text_lower in q_lower:
                    # Nếu khớp hoàn toàn nhãn dòng trong câu hỏi, cho điểm cực cao (0.95) để ưu tiên
                    if score < 0.95:
                        score = 0.95
                        
            if score > max_score_for_row:
                max_score_for_row = score
                
        if max_score_for_row > best_score and max_score_for_row > 0.4:
            best_score = max_score_for_row
            best_row_idx = idx
            best_val = val_float
            
    return best_val, best_score

def sanitize_query(query_str):
    # Khử markdown code block
    if "```" in query_str:
        parts = query_str.split("```")
        for part in parts:
            part_strip = part.strip()
            if part_strip.startswith("python"):
                part_strip = part_strip[6:].strip()
            if "df" in part_strip or "float" in part_strip or "pd.to_numeric" in part_strip:
                query_str = part_strip
                break
                
    lines = query_str.splitlines()
    for line in lines:
        line_strip = line.strip()
        if "df" in line_strip or "float" in line_strip:
            # Bỏ chú thích tiếng Việt cuối dòng
            if "#" in line_strip:
                line_strip = line_strip.split("#")[0].strip()
            return line_strip
            
    return query_str.strip().replace("\n", " ")

def call_qwen_self_correct(target_desc, retrieved_tables, failed_query, error_message):
    schema_prompt = get_table_schema_prompt(retrieved_tables)
    
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
        
    system_prompt = (
        "Bạn là một chuyên gia sửa lỗi lập trình Python/Pandas.\n"
        "Nhiệm vụ của bạn là sửa lỗi cho một câu lệnh Pandas một dòng bị lỗi khi thực thi trên các DataFrame cho trước.\n\n"
        "CÁC DATAFRAME CHO TRƯỚC:\n"
        f"{schema_prompt}\n"
        "YÊU CẦU BẮT BUỘC:\n"
        "1. Bạn phải sửa biểu thức cũ và trả về DUY NHẤT câu lệnh Pandas mới một dòng (expression). Không giải thích, không viết block code nhiều dòng.\n"
        "2. TÊN CỘT TRONG PANDAS LUÔN LÀ CÁC CHUỒI SỐ: '0', '1', '2', '3', '4'...\n"
        "   - Cấm sử dụng tên cột là chữ như 'CHỈ TIÊU', 'Mã số', 'Thuyết minh', 'Năm nay'. Tên cột thật luôn là '0', '1', '2', '3'...\n"
        "   - HƯỚNG DẪN XÁC ĐỊNH CỘT: Hãy nhìn kỹ vào hàng đầu tiên (hàng index 0 hoặc 1) của từng DataFrame để biết cột nào chứa 'Mã số' và cột nào chứa 'Chỉ tiêu'.\n"
        "     * Ví dụ: Nếu hàng 0 có chữ 'Mã số' ở cột '0', thì cột '0' là cột mã số, cột '1' là cột chỉ tiêu.\n"
        "     * Ngược lại, nếu chữ 'Mã số' nằm ở cột '1', thì cột '1' là cột mã số, cột '0' là cột chỉ tiêu.\n"
        "3. ĐỐI CHIẾU NGỮ NGHĨA DÒNG:\n"
        "   - Hãy kiểm tra kỹ xem dòng đó có đúng là chỉ tiêu cần tìm không. Ví dụ: Tìm 'Lợi nhuận sau thuế' mà mã số '60' lại là 'Chi phí tài chính', bạn phải đổi sang tìm mã '200' hoặc tìm theo regex chữ 'Lợi nhuận sau thuế'.\n"
        "4. Áp dụng các mẹo sửa lỗi:\n"
        "   - Nếu lỗi là IndexError (index 0 is out of bounds), tức là mã số hoặc từ khóa không tồn tại trong DataFrame đó (ví dụ df1). Hãy thử kiểm tra DataFrame khác (ví dụ df2) hoặc dùng Regex tìm theo chữ với `.str.contains('từ_khóa', case=False, na=False)`.\n"
        "   - Luôn dùng `.str.contains()` khi tìm theo chữ, cấm dùng so sánh bằng `==` vì chữ trong bảng thường có tiền tố hoặc hậu tố số dòng (ví dụ: '13. Chi phí khác').\n"
        "   - Luôn bọc float() bên ngoài cả `.values[0]`. Cú pháp đúng: `float(df1[df1['1'].astype(str).str.strip() == '200']['3'].values[0]) / DIVISOR`. Cấm viết `float(df1[...]['3']).values[0] / 1e9` (lỗi TypeError).\n"
        "   - TUYỆT ĐỐI CẤM sử dụng các biến mẫu như CODE_COLUMN, TARGET_CODE, VAL_COLUMN, DIVISOR. Bạn phải thay thế chúng bằng tên cột thực tế (ví dụ '1', '3'), mã số thực tế (ví dụ '200') và số thực tế (ví dụ 1e9).\n"
        "5. CẤM TUYỆT ĐỐI ghi chú hoặc giải thích: Chỉ trả về duy nhất chuỗi code một dòng chạy được.\n\n"
        "ĐẦU RA HỢP LỆ:\n"
        f"float(df2[df2['1'].astype(str).str.strip() == '200']['3'].values[0]) / {divisor_str}"
    )
    
    # Tạo cảnh báo động dựa trên chỉ tiêu cần tìm
    target_metric_names = target_desc.get("target_metrics", [])
    metric_str = " hoặc ".join(target_metric_names) if target_metric_names else "Chỉ tiêu tài chính"
    
    warning_instruction = (
        f"LƯU Ý CỰC KỲ QUAN TRỌNG ĐỂ SỬA LỖI:\n"
        f"- Bạn đang tìm chỉ tiêu liên quan đến: '{metric_str}'.\n"
        f"- Hãy đối chiếu cột tên chỉ tiêu (thường là cột '0' hoặc cột '1') của từng bảng df1, df2...\n"
        f"- Bắt buộc chọn dòng có tên chỉ tiêu khớp ngữ nghĩa với '{metric_str}'.\n"
        f"- CẤM TUYỆT ĐỐI sử dụng các biến mẫu (placeholder) như CODE_COLUMN, TARGET_CODE, VAL_COLUMN. Hãy thay bằng cột thực tế như '1', '3' và mã thực tế như '200' có trong bảng.\n"
        f"- CẤM TUYỆT ĐỐI lấy các dòng có tên chỉ tiêu khác hoàn toàn (Ví dụ: câu hỏi hỏi 'Lợi nhuận sau thuế' mà mã số '60' ở bảng df2 lại có tên là 'Cộng chi phí tài chính' hoặc 'Chi phí thuế', bạn phải bỏ qua mã '60' và tìm mã khác như '200' có tên là 'Lợi nhuận sau thuế')."
    )
    
    key_error_warning = ""
    if "KeyError" in error_message:
        key_error_warning = (
            "\n[CẢNH BÁO LỖI KEYERROR]:\n"
            "- Bạn đã sử dụng tên cột không tồn tại trong DataFrame. Hãy xem kỹ GỢI Ý CỘT của từng bảng ở trên.\n"
            "- TUYỆT ĐỐI CẤM sử dụng tên cột là chữ (như 'Năm nay', 'Năm trước', 'Năm 2023', 'Năm 2024').\n"
            "- Bạn bắt buộc phải đổi sang tên cột dạng số chuỗi: '0', '1', '2', '3', '4'...\n"
        )
        
    user_input = (
        f"Câu hỏi: {target_desc['question']}\n"
        f"Biểu thức cũ bị lỗi: {failed_query}\n"
        f"Thông báo lỗi thực tế: {error_message}\n"
        f"Chỉ tiêu cần tìm: {target_desc['target_metrics']}\n"
        f"Mã số kế toán đích gợi ý: {target_codes_to_prompt}\n"
        f"Đơn vị quy đổi: {target_desc['unit']}\n"
        f"Quy định phép chia/nhân đơn vị: {unit_instruction}\n\n"
        f"{warning_instruction}"
        f"{key_error_warning}"
    )
    
    global LM_STUDIO_OFFLINE
    if LM_STUDIO_OFFLINE:
        return failed_query
        
    payload = {
        "model": MODEL_NAME,
        "system_prompt": system_prompt,
        "input": user_input
    }
    
    try:
        response = requests.post(LM_STUDIO_API_URL, json=payload, timeout=120)
        response.raise_for_status()
        data = response.json()
        
        content = ""
        if "output" in data and len(data["output"]) > 0:
            content = data["output"][0]["content"]
        elif "choices" in data:
            content = data["choices"][0]["message"]["content"]
            
        query_clean = sanitize_query(content)
        return query_clean
    except Exception as e:
        print(f"Warning: Lỗi gọi API sửa lỗi ({e}). Giữ nguyên biểu thức cũ.")
        return failed_query

class SafeEmptyFilterError(Exception):
    pass

import contextlib

@contextlib.contextmanager
def safe_pandas_execution():
    original_series_values = pd.Series.values
    original_df_values = pd.DataFrame.values
    original_iloc_getitem = pd.core.indexing._iLocIndexer.__getitem__
    original_series_get = pd.Series.get

    class SafeValues:
        def __init__(self, series, arr):
            self._series = series
            self._arr = arr
        def __getitem__(self, idx):
            if idx == 0:
                if len(self._series) > 0:
                    return self._series.iloc[0]
                else:
                    raise SafeEmptyFilterError("Kết quả lọc rỗng, chuyển sang bước dự phòng.")
            return self._arr[idx]
        def __len__(self):
            return len(self._arr)
        def __getattr__(self, name):
            return getattr(self._arr, name)

    class SafeDataFrameValues:
        def __init__(self, df, arr):
            self._df = df
            self._arr = arr
        def __getitem__(self, idx):
            if idx == 0:
                if len(self._df) > 0:
                    return self._df.iloc[0].values
                else:
                    raise SafeEmptyFilterError("Kết quả lọc rỗng, chuyển sang bước dự phòng.")
            return self._arr[idx]
        def __len__(self):
            return len(self._arr)
        def __getattr__(self, name):
            return getattr(self._arr, name)

    pd.Series.values = property(lambda self: SafeValues(self, self.to_numpy()))
    pd.DataFrame.values = property(lambda self: SafeDataFrameValues(self, self.to_numpy()))
    
    def safe_iloc_getitem(self, idx):
        if idx == 0 or (isinstance(idx, tuple) and idx[0] == 0):
            if len(self.obj) == 0:
                raise SafeEmptyFilterError("Kết quả lọc rỗng, chuyển sang bước dự phòng.")
        return original_iloc_getitem(self, idx)

    pd.core.indexing._iLocIndexer.__getitem__ = safe_iloc_getitem
    
    def safe_series_get(self, key, default=None):
        if key == 0 and len(self) > 0 and 0 not in self.index:
            return self.iloc[0]
        return original_series_get(self, key, default)
        
    pd.Series.get = safe_series_get
    
    try:
        yield
    finally:
        pd.Series.values = original_series_values
        pd.DataFrame.values = original_df_values
        pd.core.indexing._iLocIndexer.__getitem__ = original_iloc_getitem
        pd.Series.get = original_series_get

def clean_dataframe(df):
    df.columns = [str(i) for i in range(len(df.columns))]
    code_col, item_col, val_col = find_column_indices(df)
    
    garbage_values = {'-', '–', 'N/A', 'n/a', '', 'nan', 'NaN', 'null', 'None'}
    
    def clean_val(x):
        if pd.isna(x):
            return 0.0
        s = str(x).strip()
        if not s or s in garbage_values:
            return 0.0
        try:
            s_clean = s.replace(',', '')
            if s_clean.startswith('(') and s_clean.endswith(')'):
                s_clean = '-' + s_clean[1:-1]
            return float(s_clean)
        except ValueError:
            return s
            
    # Áp dụng chọn lọc theo cột
    for col in df.columns:
        if col == item_col or col == code_col:
            # Giữ nguyên kiểu chuỗi cho cột mô tả chỉ tiêu và cột mã số
            df[col] = df[col].fillna('').astype(str).str.strip()
        else:
            # Làm sạch dữ liệu số cho các cột khác (cột giá trị)
            df[col] = df[col].map(clean_val)
            
    return df

LM_STUDIO_OFFLINE = (os.environ.get("FORCE_OFFLINE", "False") == "True")

def check_lm_studio_online():
    global LM_STUDIO_OFFLINE
    if LM_STUDIO_OFFLINE:
        return False
    try:
        requests.get("http://localhost:1234/api/v1/models", timeout=0.5)
        return True
    except Exception:
        print("WARNING: Server LM Studio (localhost:1234) OFFLINE!")
        LM_STUDIO_OFFLINE = True
        return False

def run_cascade_3tier_fallback(dfs_env, retrieved_tables, target_desc, current_query=""):
    """
    CASCADE QUERY FALLBACK (THỰC THI THUẬT TOÁN 3 TẦNG):
    
    TẦNG 1: Mã Số Chuẩn (Standard Accounting Code Match)
      -> Quét mã số kế toán (10, 60, 270, 300...) qua find_row_by_code.
      -> Nếu tìm thấy ô chứa số hợp lệ -> TRẢ VỀ NGAY.
      
    TẦNG 2: String Match (Fuzzy Metric Name Match)
      -> Quét tên chỉ tiêu / hàng trùng khớp theo Fuzzy Ratio & Substring Contains.
      -> Phân định cột đầu năm vs cuối năm qua find_val_col_by_header_and_question.
      -> Nếu tìm thấy ô chứa số hợp lệ -> TRẢ VỀ NGAY.
      
    TẦNG 3: Surrounding Text / Context Regex Scanner
      -> Quét Regex trên các dòng văn bản thô (table_context + text xung quanh 120 dòng).
      -> Nếu trích xuất được số thực tế -> TRẢ VỀ NGAY.
    """
    print("   [CASCADE FALLBACK] Kích hoạt Thuật toán 3 Tầng (Tier 1 -> Tier 2 -> Tier 3)...")
    scaling = target_desc.get("scaling_factor", 1.0)
    is_percent = target_desc.get("is_percent", False)
    target_codes = target_desc.get("target_codes", [])
    target_metrics = target_desc.get("target_metrics", [])
    question = target_desc.get("question", "")
    
    # -------------------------------------------------------------
    # TẦNG 1: Mã Số Chuẩn (Standard Accounting Code Match)
    # -------------------------------------------------------------
    if target_codes:
        for idx, r in enumerate(retrieved_tables):
            var_name = f"df{idx+1}"
            if var_name in dfs_env:
                df_target = dfs_env[var_name]
                val_col = find_val_col_by_header_and_question(df_target, question)
                for code in target_codes:
                    matched_rows = find_row_by_code(df_target, code)
                    if not matched_rows.empty and val_col in matched_rows.columns:
                        for val_raw in matched_rows[val_col]:
                            if pd.notna(val_raw) and str(val_raw).strip() not in ['', '-', '–', 'N/A', 'nan']:
                                try:
                                    val_clean = str(val_raw).replace(',', '').replace('(', '-').replace(')', '').strip()
                                    val_float = float(val_clean)
                                    final_val = val_float * scaling * (100.0 if is_percent else 1.0)
                                    print(f"   [TẦNG 1 THÀNH CÔNG] Khớp Mã số '{code}' tại {var_name}: {val_float} -> Sau quy đổi: {final_val}")
                                    return final_val, f"float({final_val})"
                                except Exception:
                                    pass

    # -------------------------------------------------------------
    # TẦNG 2: String Match (Fuzzy Metric Name Match)
    # -------------------------------------------------------------
    global_best_val = None
    global_best_score = -1.0
    global_best_var = None
    
    for idx, r in enumerate(retrieved_tables):
        var_name = f"df{idx+1}"
        if var_name in dfs_env:
            df_target = dfs_env[var_name]
            code_col, item_col, default_val_col = find_column_indices(df_target)
            val_col = find_val_col_by_header_and_question(df_target, question)
            
            df_target.columns = [str(c) for c in df_target.columns]
            best_val, best_score = fallback_fuzzy_match(df_target, target_metrics, item_col, val_col, question=question)
            if best_val is not None and best_score > global_best_score:
                global_best_score = best_score
                global_best_val = best_val
                global_best_var = var_name
                
    if global_best_val is not None and global_best_score >= 0.4:
        final_val = float(global_best_val) * scaling * (100.0 if is_percent else 1.0)
        print(f"   [TẦNG 2 THÀNH CÔNG] String Match khớp {global_best_var} (Điểm: {global_best_score:.2f}): {global_best_val} -> Sau quy đổi: {final_val}")
        return final_val, f"float({final_val})"
        
    # -------------------------------------------------------------
    # TẦNG 3: Surrounding Text / Context Regex Scanner
    # -------------------------------------------------------------
    print("   [TẦNG 3 ACTIVATED] Quét Regex trên văn bản thô & Thuyết minh xung quanh Bảng...")
    for idx, r in enumerate(retrieved_tables):
        context_text = r.get("table_context", "")
        surrounding_text = ""
        try:
            from query_generator import get_surrounding_text_from_report
            surrounding_text = get_surrounding_text_from_report(r, num_lines_before=15, num_lines_after=120)
        except Exception:
            pass
            
        full_text = context_text + "\n" + surrounding_text
        
        metrics_clean = [str(m).strip().lower() for m in target_metrics]
        for metric in metrics_clean:
            if len(metric) >= 3:
                for line in full_text.splitlines():
                    line_clean = line.strip()
                    if metric in line_clean.lower():
                        # REGEX CHUẨN HÓA ĐƠN VỊ TẠI TẦNG 3:
                        # Nhận diện chữ tỷ, triệu, %, đồng đi liền sau con số
                        pattern = r'([-–]?\d+(?:[\.,]\d+)*)\s*(nghìn tỷ|ngàn tỷ|trăm tỷ|tỷ|triệu|nghìn|ngàn|%)?'
                        matches = re.findall(pattern, line_clean, re.IGNORECASE)
                        for num_str, unit_suffix in matches:
                            clean_num = num_str.replace(',', '').replace('–', '-')
                            try:
                                val_float = float(clean_num)
                                if abs(val_float) > 0:
                                    unit_mult = 1.0
                                    unit_suf_clean = unit_suffix.lower() if unit_suffix else ""
                                    if "nghìn tỷ" in unit_suf_clean or "ngàn tỷ" in unit_suf_clean:
                                        unit_mult = 1e12
                                    elif "trăm tỷ" in unit_suf_clean:
                                        unit_mult = 1e11
                                    elif "tỷ" in unit_suf_clean:
                                        unit_mult = 1e9
                                    elif "triệu" in unit_suf_clean:
                                        unit_mult = 1e6
                                    elif "nghìn" in unit_suf_clean or "ngàn" in unit_suf_clean:
                                        unit_mult = 1e3
                                        
                                    if unit_suffix:
                                        final_val = val_float * unit_mult * scaling * (100.0 if is_percent else 1.0)
                                    else:
                                        final_val = val_float * scaling * (100.0 if is_percent else 1.0)
                                        
                                    print(f"   [TẦNG 3 THÀNH CÔNG] Regex khớp dòng thô '{line_clean[:60]}...' (Đơn vị: '{unit_suffix}'): {val_float} -> Sau quy đổi: {final_val}")
                                    return final_val, f"float({final_val})"
                            except Exception:
                                pass

    print("   [CASCADE FALLBACK THẤT BẠI] Cả 3 Tầng đều không trích xuất được số. Trả về mặc định 0.0")
    return 0.0, f"float(0.0)"

def safe_get_first(series_or_df, default=0.0):
    try:
        if isinstance(series_or_df, pd.DataFrame):
            if len(series_or_df) > 0 and len(series_or_df.columns) > 1:
                series = series_or_df.iloc[:, 1]
            elif len(series_or_df) > 0:
                series = series_or_df.iloc[:, 0]
            else:
                return float(default)
        else:
            series = series_or_df
            
        clean = pd.to_numeric(series.astype(str).str.replace(r'[^\d.-]', '', regex=True), errors='coerce').dropna()
        if len(clean) > 0:
            return float(clean.iloc[0])
        return float(default)
    except Exception:
        return float(default)

def execute_and_correct_query(target_desc, retrieved_tables, initial_query, max_retries=4):
    current_query = sanitize_query(initial_query)
    
    # 1. Nạp các DataFrame vào môi trường và làm sạch
    dfs_env = {}
    for idx, r in enumerate(retrieved_tables):
        var_name = f"df{idx+1}"
        csv_full_path = os.path.join('d:/ROAD_AI', r['csv_path'])
        if os.path.exists(csv_full_path):
            try:
                df_raw = pd.read_csv(csv_full_path, comment='#')
                dfs_env[var_name] = clean_dataframe(df_raw)
            except Exception as e:
                print(f"Lỗi load DataFrame {var_name}: {e}")
                
    if not dfs_env:
        print("Lỗi: Không load được DataFrame nào trong môi trường thực thi!")
        return 0.0, current_query
        
    # Bypass LLM trực tiếp sang Cascade 3-Tier Fallback nếu nhận được tín hiệu từ Query Generator
    if current_query == "FALLBACK_FUZZY_MATCH":
        print("   [BYPASS LLM] Kích hoạt trực tiếp Thuật toán 3 Tầng (Cascade Fallback)...")
        return run_cascade_3tier_fallback(dfs_env, retrieved_tables, target_desc, current_query)
        
    # Kiểm tra trạng thái offline của LM Studio
    is_online = check_lm_studio_online()
    if not is_online:
        print("   [OFFLINE] Kích hoạt trực tiếp Thuật toán 3 Tầng (Cascade Fallback)...")
        return run_cascade_3tier_fallback(dfs_env, retrieved_tables, target_desc, current_query)
        
    # 2. Vòng lặp thực thi và tự sửa lỗi
    eval_globals = {
        "pd": pd, 
        "np": np, 
        "get_val": get_val,
        "safe_get_first": safe_get_first,
        "find_row_by_code": find_row_by_code,
        "find_val_col_by_header_and_question": find_val_col_by_header_and_question
    }
    with safe_pandas_execution():
        for attempt in range(max_retries + 1):
            print(f"-> Thử thực thi (Lần {attempt}): {current_query}")
            try:
                pred_answer = eval(current_query, eval_globals, dfs_env)
                
                if hasattr(pred_answer, 'item'):
                    pred_answer = pred_answer.item()
                elif isinstance(pred_answer, (list, np.ndarray)) and len(pred_answer) > 0:
                    pred_answer = pred_answer[0]
                    
                pred_answer = float(pred_answer)
                
                if np.isnan(pred_answer):
                    raise ValueError("Kết quả thực thi trả về là NaN (ô trống). Hãy tìm dòng khác hoặc bảng khác có số liệu đầy đủ.")
                    
                print(f"   [Thực thi THÀNH CÔNG] Đáp án: {pred_answer}")
                return pred_answer, current_query
                
            except SafeEmptyFilterError as e:
                print(f"   [Lỗi thực thi]: {e} (Chuyển ngay sang bước dự phòng)")
                break
            except Exception as e:
                tb_msg = traceback.format_exc().splitlines()[-1]
                print(f"   [Lỗi thực thi]: {tb_msg}")
                
                if attempt == max_retries:
                    print("   [Thất bại] Đã đạt giới hạn số lần sửa lỗi tối đa.")
                    break
                    
                print("   -> Đang gửi lỗi cho Qwen2.5-Coder để tự động sửa...")
                current_query = call_qwen_self_correct(target_desc, retrieved_tables, current_query, tb_msg)
                print(f"   -> Câu lệnh mới đề xuất: {current_query}")
                
    # 3. Kích hoạt Cascade 3-Tier Fallback khi mọi lần thử thực thi code bị lỗi
    return run_cascade_3tier_fallback(dfs_env, retrieved_tables, target_desc, current_query)

if __name__ == '__main__':
    # Chạy thử nghiệm toàn bộ luồng tích hợp tự sửa lỗi
    try:
        from intent_analyzer import build_target_description
        from hard_filter import apply_hard_filter
        from retriever import retrieve_relevant_tables
        from query_generator import generate_pandas_query
    except ImportError:
        print("Error: Không tìm thấy các module phụ trợ!")
        sys.exit(1)
        
    test_q = "Lợi nhuận sau thuế của CTCP Chứng khoán FPT năm 2023 là bao nhiêu tỷ đồng?"
    if len(sys.argv) > 1:
        test_q = " ".join(sys.argv[1:])
        
    print(f"Câu hỏi test: '{test_q}'\n")
    
    # 1. Phân tích ý định
    target_desc = build_target_description(test_q)
    # 2. Load metadata
    metadata_db = load_json_file('d:/ROAD_AI/metadata.json')
    # 3. Lọc cứng
    candidates = apply_hard_filter(target_desc, metadata_db)
    # 4. Truy xuất bảng
    retrieved_tables = retrieve_relevant_tables(target_desc, candidates, top_n=2)
    # 5. Sinh truy vấn ban đầu
    initial_query = generate_pandas_query(target_desc, retrieved_tables)
    
    # 6. Chạy và sửa lỗi tự động
    print("\n--- TEST VÒNG LẶP TỰ SỬA LỖI (SELF-CORRECTION TEST) ---")
    mock_failed_query = "float(df1[df1['1'] == '999999']['3'].values[0]) / 1e9"
    print(f"Cố tình chạy câu lệnh lỗi: {mock_failed_query}")
    
    answer, final_query = execute_and_correct_query(target_desc, retrieved_tables, mock_failed_query, max_retries=1)
    
    print("\n[KẾT QUẢ CUỐI CÙNG]:")
    print(f"  - Đáp án:      {answer}")
    print(f"  - Query cuối:  {final_query}")
