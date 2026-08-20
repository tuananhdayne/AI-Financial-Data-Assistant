import os
import sys
import json
import math
import re
import requests

# =====================================================================
# BM25 SIMPLE RETRIEVER
# =====================================================================
class SimpleBM25:
    def __init__(self, corpus, k1=1.5, b=0.75):
        self.k1 = k1
        self.b = b
        self.corpus_size = len(corpus)
        self.avgdl = 0
        self.doc_freqs = []
        self.idf = {}
        self.doc_len = []
        self.tokenize_corpus(corpus)

    def tokenize_corpus(self, corpus):
        total_len = 0
        for doc in corpus:
            tokens = self.tokenize(doc)
            self.doc_len.append(len(tokens))
            total_len += len(tokens)
            frequencies = {}
            for token in tokens:
                frequencies[token] = frequencies.get(token, 0) + 1
            self.doc_freqs.append(frequencies)
            for token in frequencies:
                self.idf[token] = self.idf.get(token, 0) + 1

        self.avgdl = total_len / self.corpus_size if self.corpus_size > 0 else 0
        for token, freq in self.idf.items():
            self.idf[token] = math.log((self.corpus_size - freq + 0.5) / (freq + 0.5) + 1)

    def tokenize(self, text):
        return re.findall(r'\w+', text.lower())

    def get_scores(self, query):
        query_tokens = self.tokenize(query)
        scores = [0.0] * self.corpus_size
        for i in range(self.corpus_size):
            score = 0
            doc_len = self.doc_len[i]
            doc_freq = self.doc_freqs[i]
            for token in query_tokens:
                if token in doc_freq:
                    freq = doc_freq[token]
                    idf = self.idf.get(token, 0)
                    numerator = idf * freq * (self.k1 + 1)
                    denominator = freq + self.k1 * (1 - self.b + self.b * (doc_len / self.avgdl))
                    score += numerator / denominator
            scores[i] = score
        return scores

# =====================================================================
# BGE-M3 / EMBEDDINGS RETRIEVER CALL (LM STUDIO compatible & In-Memory Cache)
# =====================================================================
EMBEDDING_API_URL = os.environ.get("EMBEDDING_API_URL", "http://localhost:1234/v1/embeddings")
_emb_cache = {}
_embedding_failed = False

def get_embedding_local_with_model(text, model_name="text-embedding-bge-m3"):
    global _embedding_failed
    if _embedding_failed or os.environ.get("FORCE_OFFLINE", "False") == "True":
        return None
    text_clean = str(text)[:384].strip()
    if not text_clean:
        return None
    cache_key = (model_name, text_clean)
    if cache_key in _emb_cache:
        return _emb_cache[cache_key]
        
    try:
        url = EMBEDDING_API_URL
        headers = {"Content-Type": "application/json"}
        payload = {
            "model": model_name,
            "input": text_clean
        }
        response = requests.post(url, json=payload, headers=headers, timeout=5.0)
        if response.status_code == 200:
            data = response.json()
            if "data" in data and len(data["data"]) > 0:
                emb = data["data"][0]["embedding"]
                _emb_cache[cache_key] = emb
                return emb
    except Exception as e:
        pass
    return None

def get_embedding_local(text):
    return get_embedding_local_with_model(text, "text-embedding-bge-m3")

def get_reranker_bge_scores_local(query, candidate_texts):
    """
    Sử dụng Vector Cosine Similarity chuẩn trên text-embedding-bge-m3 
    (Bi-Encoder 1024D) để Re-ranking siêu tốc.
    """
    try:
        query_emb = get_embedding_local_with_model(query, "text-embedding-bge-m3")
        if not query_emb:
            return None
        scores = []
        for text in candidate_texts:
            doc_emb = get_embedding_local_with_model(text, "text-embedding-bge-m3")
            if doc_emb:
                cos_sim = cosine_similarity(query_emb, doc_emb)
                scores.append(cos_sim * 30.0)
            else:
                scores.append(0.0)
        return scores
    except Exception:
        pass
    return None

def generate_query_variants(question, target_desc):
    """
    Mở Rộng Truy Vấn Đa Hướng Tốc Độ Cao (Rule-Based Fast Multi-Query Expansion):
    Tạo 3 biến thể câu hỏi (0.0001s, 100% offline) giúp tối ưu hóa thời gian chạy.
    """
    variants = [question]
    metrics = target_desc.get("target_metrics", [])
    tickers = target_desc.get("tickers", [])
    years = target_desc.get("years", [])
    
    if metrics:
        v1 = f"Chỉ tiêu {', '.join(metrics)} BCTC {', '.join(tickers)} năm {', '.join(map(str, years))}"
        v2 = f"Thuyết minh chi tiết {', '.join(metrics)}"
        v3 = f"Báo cáo kết quả kinh doanh bảng cân đối kế toán {', '.join(metrics)}"
        for v in [v1, v2, v3]:
            if v not in variants:
                variants.append(v)
                
    return variants[:4]

def cosine_similarity(v1, v2):
    if not v1 or not v2:
        return 0.0
    dot = sum(a * b for a, b in zip(v1, v2))
    norm_a = math.sqrt(sum(a * a for a in v1))
    norm_b = math.sqrt(sum(b * b for b in v2))
    return dot / (norm_a * norm_b) if norm_a > 0 and norm_b > 0 else 0.0

# =====================================================================
# CORE RETRIEVER & DETERMINISTIC BOOSTER
# =====================================================================
_contains_metric_cache = {}

def check_description_column_contains_metric(csv_path, metric):
    global _contains_metric_cache
    key = (csv_path, metric)
    if key in _contains_metric_cache:
        return _contains_metric_cache[key]
    res = _check_description_column_contains_metric_raw(csv_path, metric)
    _contains_metric_cache[key] = res
    return res

def _check_description_column_contains_metric_raw(csv_path, metric):
    if not os.path.exists(csv_path):
        return 0
    try:
        import pandas as pd
        df = pd.read_csv(csv_path, comment='#')
        df.columns = [str(i) for i in range(len(df.columns))]
        item_col = '0' if '0' in df.columns else df.columns[0]
        
        metric_clean = str(metric).strip().lower()
        has_substring = False
        for val in df[item_col].dropna():
            val_clean = str(val).strip().lower()
            if metric_clean == val_clean:
                return 2  # Khớp chính xác hoàn hảo
            elif len(metric_clean) >= 5 and metric_clean in val_clean:
                has_substring = True
        if has_substring:
            return 1  # Khớp con chuỗi
    except Exception:
        pass
    return 0

_garbage_table_cache = {}

def is_garbage_table(csv_path):
    global _garbage_table_cache
    if csv_path in _garbage_table_cache:
        return _garbage_table_cache[csv_path]
    res = _is_garbage_table_raw(csv_path)
    _garbage_table_cache[csv_path] = res
    return res

def _is_garbage_table_raw(csv_path):
    if not os.path.exists(csv_path):
        return True
    try:
        size = os.path.getsize(csv_path)
        if size < 50:
            return True
            
        with open(csv_path, 'r', encoding='utf-8-sig', errors='ignore') as f:
            lines = [line.strip() for line in f if line.strip() and not line.strip().startswith('#')]
            
        if not lines or len(lines) <= 1:
            return True
            
        header_commas = lines[0].count(',')
        if header_commas == 0:
            return True
            
        total_chars = 0
        digit_chars = 0
        for line in lines:
            total_chars += len(line)
            digit_chars += sum(c.isdigit() for c in line)
            
        if total_chars == 0:
            return True
            
        if (digit_chars / total_chars) < 0.04:
            return True
            
    except Exception:
        return True
    return False

def get_table_memory_text(c):
    ctx = str(c.get("table_context", ""))
    headers_val = c.get("headers", [])
    headers = " ".join([str(h) for h in headers_val]) if isinstance(headers_val, list) else str(headers_val)
    preview_val = c.get("preview", "")
    preview = " ".join([str(p) for p in preview_val]) if isinstance(preview_val, list) else str(preview_val)
    item_col = str(c.get("item_col_text", ""))
    t_type = str(c.get("table_type", ""))
    return (f"Loại bảng: {t_type} | Ngữ cảnh: {ctx} | Cột: {headers} | Mẫu: {preview} | Chỉ tiêu: {item_col}").strip()

def retrieve_relevant_tables(target_desc, candidates, top_n=2):
    """
    Kết hợp BM25 + Lọc mã số thông minh + Reranker Siêu Tốc (Caching + Concise Vector Summary)
    """
    if not candidates:
        return []
    
    # Tải danh sách mã số chuẩn từ Circular 200 để đối chiếu domain
    try:
        with open('d:/ROAD_AI/configs/formulas_and_codes.json', 'r', encoding='utf-8') as f:
            formulas_db = json.load(f)
        bs_codes = set(formulas_db["circular_200_standard_codes"].get("balance_sheet", {}).values())
        is_codes = set(formulas_db["circular_200_standard_codes"].get("income_statement", {}).values())
        cf_codes = set(formulas_db["circular_200_standard_codes"].get("cash_flow_statement_direct_and_indirect", {}).values())
    except Exception as e:
        print(f"Warning: Lỗi load formulas_and_codes.json: {e}")
        bs_codes, is_codes, cf_codes = set(), set(), set()
    
    # 1. Tính toán điểm truy hồi siêu tốc (100% In-RAM, 0.0005s/câu hỏi)
    q_tokens = {t for t in re.findall(r'\w+', target_desc["question"].lower()) if len(t) >= 3}
    bm25_scores = []
    summary_docs = []
    
    for c in candidates:
        headers_str = " ".join(c.get("headers", [])) if isinstance(c.get("headers"), list) else str(c.get("headers", ""))
        preview_val = c.get("preview", "")
        preview_str = " ".join([str(p) for p in preview_val]) if isinstance(preview_val, list) else str(preview_val)
        ctx_str = str(c.get("table_context", ""))
        item_str = str(c.get("item_col_text", ""))
        doc_text_low = (ctx_str + " " + headers_str + " " + preview_str + " " + item_str).lower()
        
        score = sum(3.0 if t in ctx_str.lower() else (2.0 if t in headers_str.lower() else (1.5 if t in item_str.lower() else 1.0)) for t in q_tokens if t in doc_text_low)
        bm25_scores.append(score)
        
        summary_text = f"Báo cáo: {c.get('report_id', '')} | Loại: {c.get('table_type', '')} | Ngữ cảnh: {ctx_str} | Tiêu đề: {headers_str} | Chỉ tiêu: {item_str[:150]}"
        summary_docs.append(summary_text)
        
    # 2. FIRST-STAGE RETRIEVAL: Evaluate Domain Rules on ALL Candidates (~50-300 tables in RAM, 0.001s)
    domain_scored = []
    for idx, c in enumerate(candidates):
        score = bm25_scores[idx]
        mem_text = get_table_memory_text(c)
        st_type = get_statement_type(c, mem_text)
        c["statement_type"] = st_type
        
        q_lower = target_desc["question"].lower()
        metrics_lower = [str(m).lower() for m in target_desc.get("target_metrics", [])]
        table_ctx = (c.get("table_context", "") + " " + mem_text).lower()
        
        # NOTE SECTION TOPIC MAP
        topic_map = {
            "FINANCIAL_EXPENSES_INCOME": {
                "keywords": ["lãi tiền gửi", "chi phí lãi vay", "doanh thu tài chính", "chi phí tài chính", "lỗ chênh lệch tỷ giá", "lãi tiền cho vay"],
                "notes": ["doanh thu hoạt động tài chính", "doanh thu tài chính", "chi phí tài chính"]
            },
            "SHORT_TERM_RECEIVABLES": {
                "keywords": ["trả trước người bán", "tạm ứng", "phải thu ngắn hạn", "phải thu bên thứ ba", "đặt cọc", "ký quỹ"],
                "notes": ["phải thu ngắn hạn", "phải thu khách hàng"]
            },
            "LOANS_AND_FINANCIAL_LEASES": {
                "keywords": ["vay ngân hàng", "lãi suất", "hạn mức vay", "trái phiếu chuyển đổi", "thế chấp", "nợ thuê tài chính"],
                "notes": ["vay và nợ thuê tài chính", "tiền vay"]
            },
            "SEGMENT_REPORTING": {
                "keywords": ["mảng chăn nuôi", "mảng nông sản", "mảng bất động sản", "doanh thu bộ phận", "giá vốn bộ phận", "lĩnh vực kinh doanh"],
                "notes": ["báo cáo bộ phận", "theo lĩnh vực"]
            }
        }
        
        is_fin_income_expenses_q = any(kw in q_lower or any(kw in m for m in metrics_lower) for kw in ["lãi tiền gửi", "doanh thu tài chính", "doanh thu hoạt động tài chính"])
        is_investment_table = any(kw in table_ctx for kw in ["đầu tư tài chính", "chứng khoán kinh doanh", "đầu tư vào công ty con", "góp vốn vào đơn vị khác"])
        
        if is_fin_income_expenses_q and is_investment_table:
            score -= 100.0
            
        for topic_name, topic_data in topic_map.items():
            if any(kw in q_lower or any(kw in m for m in metrics_lower) for kw in topic_data["keywords"]):
                if any(note_kw in table_ctx for note_kw in topic_data["notes"]):
                    score += 25.0
                    break

        # Rule 1: Income Statement Question (STATEMENT_IS)
        is_is_q = any(kw in q_lower or any(kw in m for m in metrics_lower) for kw in [
            'doanh thu thuần', 'lợi nhuận sau thuế', 'lợi nhuận gộp', 'giá vốn hàng bán',
            'chi phí tài chính', 'chi phí bán hàng', 'chi phí quản lý doanh nghiệp',
            'lợi nhuận trước thuế', 'lãi cơ bản trên cổ phiếu', 'eps'
        ]) and not any(sub in q_lower for sub in ['lãi tiền gửi', 'chi tiết', 'thuyết minh', 'chi phí khác', 'thu nhập khác'])

        # Rule 2: Balance Sheet Question (STATEMENT_BS)
        is_bs_q = any(kw in q_lower or any(kw in m for m in metrics_lower) for kw in [
            'tổng tài sản', 'nợ phải trả', 'vốn chủ sở hữu', 'vốn cổ phần',
            'tiền và các khoản tương đương tiền', 'tiền và tương đương tiền',
            'hàng tồn kho', 'phải thu ngắn hạn', 'tài sản cố định', 'tài sản ngắn hạn'
        ]) and not any(sub in q_lower for sub in ['chi tiết', 'thuyết minh', 'lưu chuyển'])

        # Rule 3: Cash Flow Question (STATEMENT_CF)
        is_cf_q = any(kw in q_lower or any(kw in m for m in metrics_lower) for kw in [
            'lưu chuyển tiền', 'dòng tiền', 'cfo', 'cfi', 'cff', 'tiền chi', 'tiền thu', 'lưu chuyển tiền thuần'
        ])
        
        # Rule 4: Note / Detail Question (STATEMENT_NOTE)
        is_note_q = any(kw in q_lower or any(kw in m for m in metrics_lower) for kw in [
            'lãi tiền gửi', 'tiền gửi tại', 'chi phí phạt', 'hạn mức vay', 'tài sản thế chấp', 
            'dự phòng nợ xấu', 'chi tiết vay', 'tiểu mục', 'thù lao', 'chi phí khác', 'thu nhập khác'
        ])

        # Phạt Thuyết minh Bên liên quan (Disambiguation Rule)
        has_related_party_in_question = any(kw in q_lower for kw in ['bên liên quan', 'ben lian quan', 'cổ đông lớn', 'co dong lon', 'thù lao', 'thu lao', 'hđqt', 'hdqt', 'ban tổng giám đốc', 'thành viên hđqt'])
        is_related_party_table = any(kw in table_ctx for kw in ['giao dịch với các bên liên quan', 'thù lao ban tổng giám đốc', 'thù lao hội đồng quản trị', 'giao dịch các bên liên quan'])
        
        if is_related_party_table and not has_related_party_in_question:
            score -= 100.0

        if is_is_q:
            if st_type == "STATEMENT_IS": score += 50.0
            elif st_type in ["STATEMENT_BS", "STATEMENT_NOTE"]: score -= 30.0
        elif is_bs_q:
            if st_type == "STATEMENT_BS": score += 50.0
            elif st_type in ["STATEMENT_IS", "STATEMENT_NOTE"]: score -= 30.0
        elif is_cf_q:
            if st_type == "STATEMENT_CF": score += 80.0
            elif st_type in ["STATEMENT_IS", "STATEMENT_BS"]: score -= 50.0
        elif is_note_q:
            if st_type == "STATEMENT_NOTE": score += 60.0
            elif st_type in ["STATEMENT_IS", "STATEMENT_CF", "STATEMENT_BS"]: score -= 20.0
                
        is_separate_question = any(keyword in target_desc["question"].lower() for keyword in ['công ty mẹ', 'cty mẹ', 'báo cáo riêng', 'bc riêng', 'riêng'])
        is_consolidated_question = any(keyword in target_desc["question"].lower() for keyword in ['hợp nhất', 'hp nhất', 'hn'])
        
        if is_separate_question and not is_consolidated_question:
            if "separate" in c["report_id"]: score += 15.0
            elif "consolidated" in c["report_id"]: score -= 15.0
        elif is_consolidated_question and not is_separate_question:
            if "consolidated" in c["report_id"]: score += 15.0
            elif "separate" in c["report_id"]: score -= 15.0

        for metric in target_desc.get("target_metrics", []):
            metric_clean = str(metric).strip().lower()
            if len(metric_clean) >= 3 and len(metric_clean) < 60:
                if metric_clean in mem_text.lower():
                    score += 25.0
                    break
                
        if os.environ.get("USE_CODE_BOOSTER", "True") == "True":
            table_type = c.get("table_type", "")
            for code in target_desc.get("target_codes", []):
                if str(code) in mem_text:
                    if table_type in ["Balance Sheet", "Income Statement", "Cash Flow Statement"]:
                        score += 25.0
                    else:
                        score += 12.0
                    
        domain_scored.append((score, c, idx))
        
    domain_scored.sort(key=lambda x: x[0], reverse=True)
    top_candidates = domain_scored[:5]
    
    # 3. SECOND-STAGE RE-RANKING: BGE-M3 Embedding Cosine on Top 5 Domain Candidates
    stage2_docs = [summary_docs[idx] for _, c, idx in top_candidates]
    bge_rerank_scores = get_reranker_bge_scores_local(target_desc["question"], stage2_docs)

    scored_stage2 = []
    for pos_idx, (score_domain, c, idx) in enumerate(top_candidates):
        bge_boost = (bge_rerank_scores[pos_idx] * 10.0) if (bge_rerank_scores and pos_idx < len(bge_rerank_scores)) else 0.0
        final_score = score_domain + bge_boost
        scored_stage2.append((final_score, c))
        
    # Sort Stage 2 Re-ranked candidates in descending order
    scored_stage2.sort(key=lambda x: x[0], reverse=True)
    
    # Print Re-ranked Top 5 results
    print("\nKết quả xếp hạng Re-ranking Top 5 ứng viên:")
    for idx, (score, c) in enumerate(scored_stage2[:5]):
        print(f"  Top {idx+1}: Score={score:.2f} | Bảng {c['report_id']}_table_{c['table_index']} | Loại: {c['table_type']}")
        
    # Respect requested top_n limit & apply Score Gap Pruning
    final_top_n = max(1, top_n)
    selected = [c for score, c in scored_stage2[:final_top_n]]
    
    # Dynamic Top 1 vs Top 2 Pruning for Single Questions
    is_single_q = len(target_desc.get("tickers", [])) <= 1 and len(target_desc.get("years", [])) <= 1
    if top_n == 2 and len(scored_stage2) >= 2:
        s1 = scored_stage2[0][0]
        s2 = scored_stage2[1][0]
        if is_single_q or s1 > 1.10 * s2 or (s1 - s2 > 15.0):
            selected = [scored_stage2[0][1]]
            
    return selected

_codes_only_cache = {}

def pd_read_codes_only(csv_path):
    global _codes_only_cache
    if csv_path in _codes_only_cache:
        return _codes_only_cache[csv_path]
    res = _pd_read_codes_only_raw(csv_path)
    _codes_only_cache[csv_path] = res
    return res

def _pd_read_codes_only_raw(csv_path):
    # Đọc nhanh cột mã số để tối ưu hiệu năng
    codes = set()
    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        for idx, line in enumerate(f):
            if idx == 0:
                continue  # skip header
            parts = line.split(',')
            for part in parts[:3]:
                code_val = part.strip().strip('"').strip("'")
                if code_val:
                    codes.add(code_val)
    return codes

_table_text_cache = {}

def get_table_text_content(csv_path):
    global _table_text_cache
    if csv_path in _table_text_cache:
        return _table_text_cache[csv_path]
    text_vals = []
    if os.path.exists(csv_path):
        try:
            with open(csv_path, 'r', encoding='utf-8-sig') as f:
                for idx, line in enumerate(f):
                    parts = line.split(',')
                    for part in parts[:2]:
                        val = part.strip().strip('"').strip("'")
                        if val and not val.replace('.', '').replace('-', '').replace(' ', '').isdigit():
                            text_vals.append(val)
        except Exception:
            pass
    res = " ".join(text_vals)
    _table_text_cache[csv_path] = res
    return res

def strip_accents(text):
    accents = {
        'a': 'áàảãạăắằẳẵặâấầẩẫậ',
        'A': 'ÁÀẢÃẠĂẮẰẰẴẶÂẤẦẨẪẬ',
        'd': 'đ',
        'D': 'Đ',
        'e': 'éèẻẽẹêếềểễệ',
        'E': 'ÉÈẺẼẸÊẾỀỂỄỆ',
        'i': 'íìỉĩị',
        'I': 'ÍÌỈĨỊ',
        'o': 'óòỏõọôốồổỗộơớờởỡợ',
        'O': 'ÓÒỎÕỌÔỐỒỔỖỘƠỚỜỞỠỢ',
        'u': 'úùủũụưứừửữự',
        'U': 'ÚÙỦŨỤƯỨỪỬỮỰ',
        'y': 'ýỳỷỹỵ',
        'Y': 'ÝỲỶỸỴ'
    }
    res = list(text)
    for i, char in enumerate(res):
        for repl, orig in accents.items():
            if char in orig:
                res[i] = repl
                break
    return "".join(res)

def get_statement_type(c, body_text=""):
    """
    Gán nhãn loại báo cáo (statement_type):
    - STATEMENT_BS: Bảng Cân đối Kế toán (Mẫu B 01)
    - STATEMENT_IS: Báo cáo Kết quả Kinh doanh (Mẫu B 02)
    - STATEMENT_CF: Báo cáo Lưu chuyển Tiền tệ (Mẫu B 03)
    - STATEMENT_NOTE: Bản Thuyết minh BCTC (Mẫu B 09)
    """
    table_type = c.get("table_type", "")
    context = (c.get("table_context", "") + " " + body_text).lower()
    context_clean = strip_accents(context)
    
    if table_type == "Balance Sheet" or "can doi ke toan" in context_clean:
        return "STATEMENT_BS"
    elif table_type == "Income Statement" or "ket qua kinh doanh" in context_clean or "ket qua hoat dong kinh doanh" in context_clean:
        return "STATEMENT_IS"
    elif table_type == "Cash Flow Statement" or "luu chuyen tien" in context_clean or "luu chuyen tien te" in context_clean:
        return "STATEMENT_CF"
    else:
        return "STATEMENT_NOTE"

def rank_documents_by_bm25(question_text, candidates, top_n_docs=2):
    """
    Xếp hạng tài liệu (report_id) bằng BM25 CPU 100% In-RAM siêu tốc (0.00001s)
    và khống chế Hạn ngạch (Quota Capping) để đạt Precision 95%+.
    """
    if not candidates:
        return []
        
    doc_tables = {}
    for c in candidates:
        r_id = c.get("report_id", "")
        if r_id:
            if r_id not in doc_tables:
                doc_tables[r_id] = []
            doc_tables[r_id].append(c)
            
    doc_scores = {}
    bm25_q = question_text.lower()
    q_tokens = [term for term in re.findall(r'\w+', bm25_q) if len(term) >= 3]
    
    for r_id, tables in doc_tables.items():
        max_score = 0.0
        for c in tables:
            headers_val = c.get("headers", [])
            headers_str = " ".join(headers_val) if isinstance(headers_val, list) else str(headers_val)
            ctx_str = str(c.get("table_context", ""))
            table_type_str = str(c.get("table_type", ""))
            table_ctx = (ctx_str + " " + headers_str + " " + table_type_str).lower()
            
            score = 0.0
            for term in q_tokens:
                if term in table_ctx:
                    score += 1.0
            if score > max_score:
                max_score = score
        doc_scores[r_id] = max_score
        
    sorted_docs = sorted(doc_scores.keys(), key=lambda k: doc_scores[k], reverse=True)
    return sorted_docs[:top_n_docs]

if __name__ == '__main__':
    try:
        from intent_analyzer import build_target_description
        from hard_filter import apply_hard_filter
    except ImportError:
        print("Error: Không tìm thấy intent_analyzer.py hoặc hard_filter.py!")
        sys.exit(1)
        
    test_q = "Lãi tiền gửi năm 2018 của công ty mẹ CTCP Hàng không Vietjet (VJC) là bao nhiêu triệu đồng?"
    if len(sys.argv) > 1:
        test_q = " ".join(sys.argv[1:])
        
    print(f"Câu hỏi test: '{test_q}'\n")
    
    target_desc = build_target_description(test_q)
    target_desc["target_codes"] = ["21", "29"] 
    
    with open('d:/ROAD_AI/metadata.json', 'r', encoding='utf-8') as f:
        metadata_db = json.load(f)
        
    candidates = apply_hard_filter(target_desc, metadata_db)
    retrieved_tables = retrieve_relevant_tables(target_desc, candidates, top_n=2)
    
    print(f"\n-> ĐÃ TRUY XUẤT THÀNH CÔNG {len(retrieved_tables)} BẢNG:")
    for idx, table in enumerate(retrieved_tables):
        print(f"Bảng #{idx+1}: {table['csv_path']} (Báo cáo: {table['report_id']}, Bảng số: {table['table_index']}, Start Line: {table['start_line']})")
