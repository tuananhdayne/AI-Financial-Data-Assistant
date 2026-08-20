import re
import json
import requests
import sys
import os

# Configure standard output to UTF-8
sys.stdout.reconfigure(encoding='utf-8')

# API Config
LM_STUDIO_API_URL = "http://localhost:1234/api/v1/chat"
MODEL_NAME = "qwen2.5-7b-instruct"

# Cờ báo hiệu lỗi LLM để tự động chuyển sang chế độ offline siêu nhanh
LLM_FAILED = (os.environ.get("FORCE_OFFLINE", "False") == "True")

def load_json_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def extract_metadata_deterministic(question_text, synonyms):
    question_lower = question_text.lower().replace('–', '-').replace('—', '-')
    
    # 1. Exhaustive Multi-Ticker Scanner (Quét cạn tất cả mã cổ phiếu xuất hiện)
    detected_tickers = set()
    
    # 1a. Direct Uppercase 3-letter matching against known stock list
    raw_uppercase_tickers = re.findall(r'\b([A-Z]{3})\b', question_text)
    all_known_tickers = set(synonyms.keys())
    for t in raw_uppercase_tickers:
        if t in all_known_tickers:
            detected_tickers.add(t)
            
    # 1b. Dictionary & Brand / Subsidiary synonym matching
    detected_matches = []
    for ticker, syns in synonyms.items():
        for syn in syns:
            syn_clean = syn.lower().strip()
            if not syn_clean:
                continue
            pos = 0
            while True:
                idx = question_lower.find(syn_clean, pos)
                if idx == -1:
                    break
                start_idx = idx
                end_idx = start_idx + len(syn_clean)
                is_boundary = True
                if start_idx > 0 and question_lower[start_idx-1].isalnum():
                    is_boundary = False
                if end_idx < len(question_lower) and question_lower[end_idx].isalnum():
                    is_boundary = False
                if is_boundary:
                    detected_matches.append({
                        "ticker": ticker,
                        "syn": syn_clean,
                        "start": start_idx,
                        "end": end_idx
                    })
                    break
                pos = idx + 1
                
    # Filter out nested sub-string overlaps (e.g. 'nam á' inside 'đông nam á')
    for m in detected_matches:
        is_sub = False
        for other in detected_matches:
            if other != m:
                if other["start"] <= m["start"] and m["end"] <= other["end"] and len(other["syn"]) > len(m["syn"]):
                    is_sub = True
                    break
        if not is_sub:
            detected_tickers.add(m["ticker"])
            
    # 1c. Securities Arm & Subsidiary Priority Resolver
    securities_keywords = ['chứng khoán', 'ctck', 'chứng khoán fpt', 'chứng khoán mb', 'chứng khoán vietcap', 'chứng khoán bản việt']
    has_securities_context = any(kw in question_lower for kw in securities_keywords)
    
    securities_map = {
        'FTS': ['FPT'],
        'MBS': ['MBB'],
        'CTS': ['CTG'],
        'BSI': ['BID'],
        'VCI': ['VCI']
    }
    
    final_tickers = list(detected_tickers)
    if has_securities_context:
        for sec_ticker, parents in securities_map.items():
            if sec_ticker in final_tickers:
                # Place sec_ticker at position 0, remove parent tickers
                final_tickers = [t for t in final_tickers if t not in parents]
                final_tickers.remove(sec_ticker)
                final_tickers.insert(0, sec_ticker)
                
    ticker_result = final_tickers if len(final_tickers) > 0 else None
                    
    # 2. Temporal Range Expander (Mở rộng toàn bộ mảng năm: khoảng giai đoạn, danh sách năm, so sánh năm)
    years_found = set()
    
    # 2a. Range regex: "2020-2023", "2020 đến 2023", "giai đoạn 2020 - 2023"
    range_matches = re.findall(r'\b(20\d{2})\s*(?:[-–—]|đến|sang|tới)\s*(20\d{2})\b', question_text)
    for y1, y2 in range_matches:
        sy, ey = int(y1), int(y2)
        if sy <= ey and (ey - sy) <= 10:
            for y in range(sy, ey + 1):
                years_found.add(y)
        elif ey < sy and (sy - ey) <= 10:
            for y in range(ey, sy + 1):
                years_found.add(y)
                
    # 2b. Collect all individual 4-digit years matching 2015-2025
    all_years = [int(y) for y in re.findall(r'\b(20\d{2})\b', question_text)]
    for y in all_years:
        years_found.add(y)
        
    if len(years_found) > 1:
        year = sorted(list(years_found))
    elif len(years_found) == 1:
        year = list(years_found)[0]
    else:
        year = None
    
    # 3. Extended Separate Scope Map (Mở rộng nhận diện BCTC Riêng / Công ty mẹ)
    separate_keywords = [
        'công ty mẹ', 'cty mẹ', 'ngân hàng mẹ', 'bctc riêng', 'báo cáo riêng', 'riêng lẻ', 'đơn lẻ',
        'bctc công ty mẹ', 'báo cáo tài chính riêng', 'báo cáo tài chính công ty mẹ', 'bc riêng', 'bc riêng lẻ',
        'thù lao hđqt', 'thù lao ban tổng giám đốc', 'thù lao hội đồng quản trị', 'lương ban kiểm soát',
        'thu nhập ban tổng giám đốc', 'đầu tư vào công ty con', 'góp vốn vào công ty con', 'phải thu nội bộ',
        'dự phòng đầu tư tài chính'
    ]
    is_separate = any(keyword in question_lower for keyword in separate_keywords)
    report_type = 'separate' if is_separate else 'consolidated'
    
    # 4. Unit & Percent Check
    unit = 'đồng'
    if 'nghìn tỷ' in question_lower or 'nghìn tỉ' in question_lower:
        unit = 'nghìn tỷ đồng'
    elif 'trăm tỷ' in question_lower or 'trăm tỉ' in question_lower:
        unit = 'trăm tỷ đồng'
    elif 'tỷ đồng' in question_lower or 'tỉ đồng' in question_lower:
        unit = 'tỷ đồng'
    elif 'trăm triệu' in question_lower:
        unit = 'trăm triệu đồng'
    elif 'triệu đồng' in question_lower:
        unit = 'triệu đồng'
    elif 'nghìn đồng' in question_lower:
        unit = 'nghìn đồng'
        
    is_percent = '%' in question_lower or 'phần trăm' in question_lower
    
    return {
        "ticker": ticker_result,
        "year": year,
        "report_type": report_type,
        "unit": unit,
        "is_percent": is_percent
    }

def call_local_llm_intent(question_text):
    global LLM_FAILED
    if LLM_FAILED or os.environ.get("FORCE_OFFLINE", "False") == "True":
        return fallback_heuristics(question_text)
        
    system_prompt = (
        "Bạn là một Chuyên gia Phân tích Tài chính & Kế toán Cao cấp chuyên về Báo cáo Tài chính Việt Nam (Chuẩn Thông tư 200/2014/TT-BTC & Thông tư 49/2014/TT-NHNN).\n\n"
        "=== HỆ THỐNG TRI THỨC KẾ TOÁN & CẤU TRÚC BCTC ===\n"
        "1. BẢNG CÂN ĐỐI KẾ TOÁN (B 01 - Balance Sheet):\n"
        "   - Tài sản: Tiền & tương đương tiền (Mã 110), Phải thu ngắn hạn (Mã 130), Hàng tồn kho (Mã 140), Tài sản cố định (Mã 220), TỔNG TÀI SẢN (Mã 270).\n"
        "   - Nguồn vốn: Nợ phải trả (Mã 300), Nợ ngắn hạn (Mã 310), Nợ dài hạn (Mã 330), VỐN CHỦ SỞ HỮU (Mã 400), Vốn góp chủ sở hữu/Vốn điều lệ (Mã 411).\n\n"
        "2. BÁO CÁO KẾT QUẢ KINH DOANH (B 02 - Income Statement):\n"
        "   - Doanh thu thuần (Mã 10), Giá vốn hàng bán (Mã 11), Lợi nhuận gộp (Mã 20).\n"
        "   - Doanh thu hoạt động tài chính (Mã 21), Chi phí tài chính (Mã 22 - Chi phí lãi vay Mã 23).\n"
        "   - Chi phí bán hàng (Mã 25), Chi phí quản lý doanh nghiệp (Mã 26).\n"
        "   - Lợi nhuận thuần từ HĐKD (Mã 30), Lợi nhuận trước thuế (Mã 50), LỢI NHUẬN SAU THUẾ (Mã 60), EPS (Mã 70).\n\n"
        "3. BÁO CÁO LƯU CHUYỂN TIỀN TỆ (B 03 - Cash Flow Statement):\n"
        "   - Dòng tiền từ hoạt động kinh doanh (CFO - Mã 20), Dòng tiền từ HĐ đầu tư (CFI - Mã 30), Dòng tiền từ HĐ tài chính (CFF - Mã 40).\n\n"
        "4. BẢN THUYẾT MINH BCTC (B 09 - Notes):\n"
        "   - Lãi tiền gửi / Thu nhập tài chính $\\rightarrow$ Thuyết minh Doanh thu tài chính.\n"
        "   - Chi phí lãi vay / Lỗ tỷ giá $\\rightarrow$ Thuyết minh Chi phí tài chính.\n"
        "   - Chi tiết nợ xấu / Chi phí phạt / Thù lao HĐQT $\\rightarrow$ Thuyết minh chi tiết tương ứng.\n\n"
        "=== CÁC CÔNG THỨC TÀI CHÍNH PHÁI SINH ===\n"
        "Các công thức chuẩn: ['ROE', 'ROA', 'Biên Lợi nhuận gộp', 'Biên Lợi nhuận ròng', 'D/E Ratio', 'Hệ số thanh toán hiện hành', 'Hệ số thanh toán nhanh', 'Hệ số khả năng thanh toán lãi vay', 'Hệ số dòng tiền hoạt động trên nợ ngắn hạn', 'Số ngày tồn kho', 'Tỷ số dồn tích', 'CFO Margin (Biên dòng tiền)', 'Vốn lưu động thuần (NWC)', 'Vòng quay Tổng tài sản', 'SG&A Intensity', 'Tỷ lệ Nợ nần (Debt Ratio)', 'Hệ số Chuyển đổi Lợi nhuận'].\n\n"
        "Nhiệm vụ của bạn: Phân tích câu hỏi tài chính và trả về chuỗi JSON duy nhất chứa:\n"
        "1. 'target_metrics': Danh sách chuẩn các chỉ tiêu tài chính cần tìm trong bảng.\n"
        "2. 'formula': Tên công thức tài chính nếu câu hỏi hỏi về tỷ số phái sinh phức tạp (hoặc null nếu là câu hỏi tra cứu thông thường).\n\n"
        "BẮT BUỘC TRẢ VỀ JSON DUY NHẤT VỚI CẤU TRÚC:\n"
        "{\n"
        "  \"target_metrics\": [\"...\"],\n"
        "  \"formula\": \"...\" hoặc null\n"
        "}"
    )
    
    # Thử gọi qua OpenAI-compatible completions trước
    success = False
    content = ""
    try:
        openai_url = "http://localhost:1234/v1/chat/completions"
        openai_payload = {
            "model": MODEL_NAME,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question_text}
            ],
            "temperature": 0.0,
            "max_tokens": 128
        }
        response = requests.post(openai_url, json=openai_payload, timeout=8.0)
        if response.status_code == 200:
            data = response.json()
            if "choices" in data and len(data["choices"]) > 0:
                content = data["choices"][0]["message"]["content"]
                success = True
    except Exception:
        pass

    # Thử gọi qua cổng api/v1/chat
    if not success:
        payload = {
            "model": MODEL_NAME,
            "system_prompt": system_prompt,
            "input": question_text,
            "max_tokens": 128
        }
        try:
            response = requests.post(LM_STUDIO_API_URL, json=payload, timeout=8.0)
            if response.status_code == 200:
                data = response.json()
                if "output" in data and len(data["output"]) > 0:
                    content = data["output"][0]["content"]
                    success = True
        except Exception:
            pass

    if not success:
        return fallback_heuristics(question_text)
        
    try:
        # Extract JSON substring between the first '{' and last '}'
        start_idx = content.find('{')
        end_idx = content.rfind('}')
        if start_idx != -1 and end_idx != -1:
            json_str = content[start_idx:end_idx+1]
        else:
            json_str = content
            
        # Clean any remaining markdown tags or comments
        json_clean = re.sub(r'//.*', '', json_str)  # Remove single line comments
        return json.loads(json_clean)
    except Exception as e:
        print(f"Warning: Lỗi phân tích cú pháp JSON phản hồi từ LLM ({e}). Sử dụng cơ chế fallback...")
        return fallback_heuristics(question_text)

def fallback_heuristics(question_text):
    # Simple rule-based fallback
    q_low = question_text.lower()
    target_metrics = []
    formula = None
    
    if 'roe' in q_low or ('lợi nhuận sau thuế' in q_low and 'vốn chủ' in q_low):
        target_metrics = ["Lợi nhuận sau thuế", "Vốn chủ sở hữu"]
        formula = "ROE (Return on Equity)"
    elif 'roa' in q_low or ('lợi nhuận sau thuế' in q_low and 'tổng tài sản' in q_low):
        target_metrics = ["Lợi nhuận sau thuế", "Tổng tài sản"]
        formula = "ROA (Return on Assets)"
    elif 'biên lợi nhuận gộp' in q_low or 'biên ln gộp' in q_low:
        target_metrics = ["Lợi nhuận gộp", "Doanh thu thuần"]
        formula = "Biên Lợi nhuận gộp (Gross Profit Margin)"
    elif 'cfo margin' in q_low or 'biên dòng tiền' in q_low:
        target_metrics = ["Lưu chuyển tiền thuần từ hoạt động kinh doanh", "Doanh thu thuần"]
        formula = "CFO Margin (Biên dòng tiền)"
    elif 'nwc' in q_low or 'vốn lưu động thuần' in q_low:
        target_metrics = ["Tài sản ngắn hạn", "Nợ ngắn hạn"]
        formula = "Vốn lưu động thuần (NWC)"
    elif 'vòng quay tổng tài sản' in q_low:
        target_metrics = ["Doanh thu thuần", "Tổng tài sản"]
        formula = "Vòng quay Tổng tài sản"
    elif 'sg&a' in q_low or 'chi phí bán hàng và qldn' in q_low:
        target_metrics = ["Chi phí bán hàng", "Chi phí quản lý doanh nghiệp", "Doanh thu thuần"]
        formula = "SG&A Intensity"
    elif 'tỷ lệ nợ' in q_low or 'tỷ số nợ' in q_low or 'debt ratio' in q_low:
        target_metrics = ["Tổng nợ phải trả", "Tổng tài sản"]
        formula = "Tỷ lệ Nợ nần (Debt Ratio)"
    elif 'chuyển đổi lợi nhuận' in q_low:
        target_metrics = ["Lưu chuyển tiền thuần từ hoạt động kinh doanh", "Lợi nhuận sau thuế"]
        formula = "Hệ số Chuyển đổi Lợi nhuận"
    elif 'lãi tiền gửi' in q_low:
        target_metrics = ["Lãi tiền gửi"]
    elif 'lợi nhuận sau thuế' in q_low:
        target_metrics = ["Lợi nhuận sau thuế"]
    elif 'chi phí khác' in q_low:
        target_metrics = ["Chi phí khác"]
    else:
        target_metrics = [question_text]
        
    return {
        "target_metrics": target_metrics,
        "formula": formula
    }

def build_target_description(question_text):
    # Load metadata assets
    synonyms = load_json_file('d:/ROAD_AI/configs/synonyms.json')
    formulas_db = load_json_file('d:/ROAD_AI/configs/formulas_and_codes.json')
    
    # 1. Deterministic metadata extraction
    meta = extract_metadata_deterministic(question_text, synonyms)
    
    # 2. LLM Intent & Formula Analysis
    llm_intent = call_local_llm_intent(question_text)
    
    # Merge
    target_desc = {
        "question": question_text,
        "ticker": meta["ticker"],
        "year": meta["year"],
        "report_type": meta["report_type"],
        "unit": meta["unit"],
        "is_percent": meta["is_percent"],
        "target_metrics": llm_intent.get("target_metrics", []),
        "formula_applied": llm_intent.get("formula", None),
        "target_codes": []
    }
    
    # 3. Match codes from Circular 200 Database
    formula_name = target_desc["formula_applied"]
    
    # If the LLM returned a shorthand formula name, try to match it with formulas_db keys
    matched_formula = None
    if formula_name:
        for f_key in formulas_db["financial_formula_templates"].keys():
            if formula_name.upper() in f_key.upper() or f_key.upper() in formula_name.upper():
                matched_formula = f_key
                break
                
    if matched_formula:
        target_desc["formula_applied"] = matched_formula
        target_desc["formula_details"] = formulas_db["financial_formula_templates"][matched_formula]
        # Auto populate target codes based on standard codes for formula
        if "ROE" in matched_formula:
            target_desc["target_codes"] = ["60", "61", "400", "30"]
        elif "ROA" in matched_formula:
            target_desc["target_codes"] = ["60", "270", "30"]
        elif "gộp" in matched_formula.lower():
            target_desc["target_codes"] = ["20", "10"]
        elif "ròng" in matched_formula.lower():
            target_desc["target_codes"] = ["60", "10", "30"]
        elif "nợ / vốn" in matched_formula.lower() or "d/e" in matched_formula.lower():
            target_desc["target_codes"] = ["300", "400", "60"]
        elif "thanh toán hiện hành" in matched_formula.lower() or "current ratio" in matched_formula.lower():
            target_desc["target_codes"] = ["100", "310"]
        elif "thanh toán nhanh" in matched_formula.lower() or "quick ratio" in matched_formula.lower():
            target_desc["target_codes"] = ["100", "140", "310"]
        elif "lãi vay" in matched_formula.lower() or "interest coverage" in matched_formula.lower():
            target_desc["target_codes"] = ["50", "23", "22"]
        elif "dòng tiền" in matched_formula.lower() and "nợ ngắn hạn" in matched_formula.lower():
            target_desc["target_codes"] = ["20", "310"]
        elif "ngày tồn kho" in matched_formula.lower() or "dio" in matched_formula.lower():
            target_desc["target_codes"] = ["11", "140"]
        elif "dồn tích" in matched_formula.lower() or "accrual" in matched_formula.lower():
            target_desc["target_codes"] = ["60", "20", "30", "270"]
        elif "tăng trưởng" in matched_formula.lower() and "doanh thu thuần" in matched_formula.lower():
            target_desc["target_codes"] = ["10"]
        elif "cfo margin" in matched_formula.lower() or "biên dòng tiền" in matched_formula.lower():
            target_desc["target_codes"] = ["20", "10"]
        elif "vốn lưu động thuần" in matched_formula.lower() or "nwc" in matched_formula.lower():
            target_desc["target_codes"] = ["100", "310"]
        elif "vòng quay tổng tài sản" in matched_formula.lower():
            target_desc["target_codes"] = ["10", "270"]
        elif "sg&a" in matched_formula.lower():
            target_desc["target_codes"] = ["25", "26", "10"]
        elif "nợ nần" in matched_formula.lower() or "debt ratio" in matched_formula.lower():
            target_desc["target_codes"] = ["300", "270"]
        elif "chuyển đổi lợi nhuận" in matched_formula.lower():
            target_desc["target_codes"] = ["20", "60", "30"]
    else:
        # Simple lookup: match target metrics to Circular 200 standard codes
        custom_syns = formulas_db["circular_200_standard_codes"].get("custom_metric_synonyms", {})
        
        for metric in target_desc["target_metrics"]:
            matched_code = None
            metric_lower = metric.lower()
            
            # 1. Check custom synonyms first
            for syn_name, syn_code in custom_syns.items():
                if metric_lower == syn_name.lower() or syn_name.lower() in metric_lower:
                    matched_code = syn_code
                    break
                    
            if matched_code:
                if isinstance(matched_code, list):
                    target_desc["target_codes"].extend([str(c) for c in matched_code])
                else:
                    target_desc["target_codes"].append(str(matched_code))
                continue
                
            # 2. Domain-aware routing (prioritize sheet based on keywords)
            is_income_metric = any(kw in metric_lower for kw in ["doanh thu", "lợi nhuận", "chi phí", "giá vốn", "lãi"]) and not any(kw in metric_lower for kw in ["nợ", "vốn chủ", "tài sản"])
            is_balance_metric = any(kw in metric_lower for kw in ["tài sản", "nợ", "vốn", "quỹ", "tiền"])
            
            sections_order = []
            if is_income_metric:
                sections_order = ["income_statement", "balance_sheet", "cash_flow_statement_direct_and_indirect"]
            elif is_balance_metric:
                sections_order = ["balance_sheet", "income_statement", "cash_flow_statement_direct_and_indirect"]
            else:
                sections_order = ["balance_sheet", "income_statement", "cash_flow_statement_direct_and_indirect"]
                
            for section in sections_order:
                section_db = formulas_db["circular_200_standard_codes"].get(section, {})
                for std_name, std_code in section_db.items():
                    # Check exact or strong substring matching
                    if metric_lower == std_name.lower() or std_name.lower() in metric_lower or (len(metric_lower) > 5 and metric_lower in std_name.lower()):
                        matched_code = std_code
                        break
                if matched_code:
                    break
                    
            if matched_code:
                target_desc["target_codes"].append(matched_code)
                
    # 4. Determine unit scaling factor
    scaling_factor = 1.0
    unit_lower = meta["unit"].lower()
    if "nghìn tỷ" in unit_lower or "nghìn tỉ" in unit_lower:
        scaling_factor = 1e-12
    elif "trăm tỷ" in unit_lower or "trăm tỉ" in unit_lower:
        scaling_factor = 1e-11
    elif "tỷ" in unit_lower or "tỉ" in unit_lower:
        scaling_factor = 1e-9
    elif "trăm triệu" in unit_lower:
        scaling_factor = 1e-8
    elif "triệu đồng" in unit_lower:
        scaling_factor = 1e-6
    elif "nghìn đồng" in unit_lower:
        scaling_factor = 1e-3
        
    target_desc["scaling_factor"] = scaling_factor
    
    return target_desc

if __name__ == '__main__':
    # Test Question
    test_q = "Lãi tiền gửi năm 2018 của công ty mẹ CTCP Hàng không Vietjet (VJC) là bao nhiêu triệu đồng?"
    if len(sys.argv) > 1:
        test_q = " ".join(sys.argv[1:])
        
    print(f"Câu hỏi đầu vào: '{test_q}'\n")
    print("Đang xử lý BƯỚC 1 (Intent Analysis)...")
    result = build_target_description(test_q)
    print("\nKết quả BẢN MÔ TẢ BẢNG MỤC TIÊU + Đơn vị quy đổi:")
    print(json.dumps(result, ensure_ascii=False, indent=2))
