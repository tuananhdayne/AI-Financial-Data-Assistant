import os
import re
import sys
import json
import glob
import pandas as pd
from bs4 import BeautifulSoup
from concurrent.futures import ProcessPoolExecutor, as_completed

def clean_numeric_string(val):
    if not val:
        return val
    val = val.strip()
    
    # Handle percentage
    has_percent = False
    if val.endswith('%'):
        has_percent = True
        val = val[:-1].strip()
        
    if val in ('-', '–', '—', ''):
        return '0'
        
    # Check if it matches a numeric pattern (only digits, dots, commas, negative signs, parens)
    match = re.match(r'^\s*\(?\s*-?\s*[\d.,]+\s*\)?\s*$', val)
    if not match:
        if has_percent:
            return val + '%'
        return val
        
    is_negative = False
    if (val.startswith('(') and val.endswith(')')) or val.startswith('-'):
        is_negative = True
        val = val.strip('()').strip('-').strip()
        
    # Clean up thousand separators
    dot_count = val.count('.')
    comma_count = val.count(',')
    
    clean_val = val
    if dot_count > 0 and comma_count > 0:
        if val.find('.') > val.find(','):
            # Comma is thousands, dot is decimal (English)
            clean_val = val.replace(',', '')
        else:
            # Dot is thousands, comma is decimal (Vietnamese)
            clean_val = val.replace('.', '').replace(',', '.')
    elif dot_count > 1:
        clean_val = val.replace('.', '')
    elif comma_count > 1:
        clean_val = val.replace(',', '')
    elif dot_count == 1:
        parts = val.split('.')
        if len(parts[1]) == 3 and parts[1].isdigit():
            clean_val = val.replace('.', '')
        else:
            clean_val = val
    elif comma_count == 1:
        parts = val.split(',')
        if len(parts[1]) == 3 and parts[1].isdigit():
            clean_val = val.replace(',', '')
        else:
            clean_val = val.replace(',', '.')
            
    clean_val = clean_val.replace(' ', '')
    
    if is_negative:
        return '-' + clean_val
    return clean_val

def extract_note_title(context):
    if not context:
        return "Thuyết minh chi tiết"
    lines = [line.strip() for line in context.split('\n') if line.strip()]
    patterns = [
        r'\b(?:Thuyết minh|Thuyêt minh)\s*(?:báo cáo tài chính|bctc)?\s*\d+',
        r'^\s*(?:[IVXLCDM]+\.|\d+\.\d*)\s*[a-zA-ZÀ-ỹ]',
        r'\b(?:bảng cân đối kế toán|báo cáo kết quả kinh doanh|báo cáo lưu chuyển tiền tệ)\b',
        r'\b(?:nợ phải trả|vốn chủ sở hữu|tài sản ngắn hạn|tài sản dài hạn|doanh thu|chi phí)\b',
    ]
    for line in reversed(lines):
        line_lower = line.lower()
        if any(k in line_lower for k in ['trang ', 'công ty', 'tập đoàn', 'kết thúc ngày', 'năm tài chính', 'năm kết thúc']):
            continue
        for pat in patterns:
            if re.search(pat, line, re.IGNORECASE):
                return line
    if lines:
        for line in reversed(lines):
            if len(line.strip()) > 3 and not any(k in line.lower() for k in ['trang ', 'công ty', 'tập đoàn']):
                return line
        return lines[-1]
    return "Thuyết minh chi tiết"

def parse_html_table_original(table_html):
    soup = BeautifulSoup(table_html, 'html.parser')
    table = soup.find('table')
    if not table:
        return None
        
    rows = table.find_all('tr')
    if not rows:
        return None
        
    grid = {}
    for r_idx, row in enumerate(rows):
        c_idx = 0
        cells = row.find_all(['td', 'th'])
        for cell in cells:
            while (r_idx, c_idx) in grid:
                c_idx += 1
                
            rowspan = int(cell.get('rowspan', 1))
            colspan = int(cell.get('colspan', 1))
            cell_text = cell.get_text().strip()
            
            # Ô gộp (colspan) chỉ giữ lại chữ ở cột đầu tiên, các cột sau để trống ""
            for r_offset in range(rowspan):
                for c_offset in range(colspan):
                    if r_offset == 0 and c_offset == 0:
                        grid[(r_idx + r_offset, c_idx + c_offset)] = cell_text
                    else:
                        grid[(r_idx + r_offset, c_idx + c_offset)] = ""
                        
            c_idx += colspan
            
    if not grid:
        return None
        
    max_r = max(coord[0] for coord in grid.keys()) + 1
    max_c = max(coord[1] for coord in grid.keys()) + 1
    
    table_data = []
    for r in range(max_r):
        row_data = []
        for c in range(max_c):
            raw_text = grid.get((r, c), '')
            row_data.append(clean_numeric_string(raw_text))
        table_data.append(row_data)
        
    return pd.DataFrame(table_data)

def classify_table(context, df):
    ctx = context.upper() if context else ''
    
    first_row_text = ''
    if df is not None and not df.empty:
        first_row_text = ' '.join([str(val) for val in df.iloc[0].values if val]).upper()
        
    combined_text = ctx + ' ' + first_row_text
    
    if 'CÂN ĐỐI KẾ TOÁN' in combined_text:
        return 'Balance Sheet'
    elif 'KẾT QUẢ' in combined_text and 'KINH DOANH' in combined_text:
        return 'Income Statement'
    elif 'LƯU CHUYỂN TIỀN TỆ' in combined_text or 'LƯU CHUYỂN TIỀN' in combined_text:
        return 'Cash Flow Statement'
    elif 'THUYẾT MINH' in combined_text or 'THUYÊT MINH' in combined_text:
        return 'Notes'
    else:
        return 'Other/Details'

def process_single_file(file_path, output_dir, ticker_to_name):
    base_name = os.path.basename(file_path)
    report_id = base_name.replace('_extracted.txt', '').replace('.txt', '')
    
    parts = file_path.replace('\\', '/').split('/')
    ticker = None
    year = None
    for idx, part in enumerate(parts):
        if part == 'financial_statements' and idx + 2 < len(parts):
            ticker = parts[idx + 1]
            year = parts[idx + 2]
            break
            
    company_name = ticker_to_name.get(ticker, '')
            
    try:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
    except Exception as e:
        return [], f'Error reading {file_path}: {str(e)}'
        
    matches = list(re.finditer(r'<table.*?>.*?</table>', content, re.DOTALL | re.IGNORECASE))
    if not matches:
        return [], None
        
    lines = content.split('\n')
    
    page_markers = []
    for idx, line in enumerate(lines):
        m = re.match(r'=====\s*PAGE\s+(\d+)\s*=====', line, re.IGNORECASE)
        if m:
            page_markers.append((idx + 1, int(m.group(1))))
            
    def get_page_number(line_num):
        current_page = 1
        for start_line, page_val in page_markers:
            if line_num >= start_line:
                current_page = page_val
            else:
                break
        return current_page

    metadata_list = []
    errors = []
    
    prev_df = None
    prev_title = "Thuyết minh chi tiết"
    prev_table_end = 0
    prev_context = ""
    prev_start_line = None
    
    for t_idx, match in enumerate(matches):
        table_num = t_idx + 1
        table_html = match.group(0)
        char_offset = match.start()
        start_line = content[:char_offset].count('\n') + 1
        
        # Extract context: 15 lines before the table start
        pre_content = content[:char_offset].strip()
        pre_lines = pre_content.split('\n')
        context_lines = pre_lines[-15:] if len(pre_lines) >= 15 else pre_lines
        table_context = '\n'.join(context_lines).strip()
            
        page_num = get_page_number(start_line)
        
        try:
            df = parse_html_table_original(table_html)
        except Exception as e:
            errors.append(f'Error parsing table {table_num} in {report_id}: {str(e)}')
            continue
            
        if df is None or df.empty:
            df = pd.DataFrame([["Bảng rác / Header trang", ""]], columns=["0", "1"])
            
        # Detect continuation table
        is_continuation = False
        parent_start_line = None
        if t_idx > 0 and prev_df is not None:
            between_text = content[prev_table_end:char_offset].strip()
            
            has_page = any(k in between_text.upper() for k in ["PAGE", "TRANG"])
            has_new_title = False
            if re.search(r'\b(?:Thuyết minh|Thuyêt minh)\s*(?:báo cáo tài chính|bctc)?\s*\d+', between_text, re.IGNORECASE) or \
               re.search(r'^\s*(?:[IVXLCDM]+\.|\d+\.\d*)\s*[a-zA-ZÀ-ỹ]', between_text, re.MULTILINE) or \
               any(k in between_text.lower() for k in ['bảng cân đối', 'báo cáo kết quả', 'báo cáo lưu chuyển']):
                has_new_title = True
                
            cols_match = (len(df.columns) == len(prev_df.columns))
            
            if cols_match and has_page and not has_new_title:
                is_continuation = True
                parent_start_line = prev_start_line if prev_start_line is not None else start_line
                
        if is_continuation:
            title = prev_title
            table_context = prev_context
            if not df.empty and not prev_df.empty:
                first_row_current = [str(val).strip().lower() for val in df.iloc[0].values]
                first_row_prev = [str(val).strip().lower() for val in prev_df.iloc[0].values]
                match_count = sum(1 for a, b in zip(first_row_current, first_row_prev) if a == b)
                if match_count / len(first_row_prev) < 0.8:
                    header_row = prev_df.iloc[0:1]
                    df = pd.concat([header_row, df], ignore_index=True)
        else:
            title = extract_note_title(table_context)
            prev_start_line = start_line
            
        # Update prev variables
        prev_df = df
        prev_title = title
        prev_context = table_context
        prev_table_end = char_offset + len(table_html)
            
        csv_filename = f'{report_id}_table_{table_num}.csv'
        csv_path = os.path.join(output_dir, csv_filename)
        try:
            # Prepend comment row with Sig BOM
            csv_data = f"# {title}\n" + df.to_csv(index=False)
            with open(csv_path, 'w', encoding='utf-8-sig') as f_csv:
                f_csv.write(csv_data)
        except Exception as e:
            errors.append(f'Error saving CSV {csv_filename}: {str(e)}')
            continue
            
        preview_rows = []
        for r_idx, row in df.head(3).iterrows():
            row_vals = [str(val)[:30] for val in row.values[:4]]
            preview_rows.append(' | '.join(row_vals))
        preview_text = '\n'.join(preview_rows)
        
        # Determine table type
        table_type = classify_table(table_context, df)
        
        # Get the first row as the table headers
        table_headers = [str(val) for val in df.iloc[0].values if val is not None]
        
        # Extract full item column (column 0) text and exact_metric_labels
        item_col_texts = []
        exact_metric_labels = []
        if not df.empty:
            for val in df.iloc[:, 0].dropna():
                val_str = str(val).strip()
                if val_str and not val_str.replace('.', '').replace('-', '').isdigit():
                    item_col_texts.append(val_str)
                    exact_metric_labels.append(val_str.upper())
        item_col_str = " ".join(item_col_texts)
        
        # Extract accounting codes set (column 1 or column 0)
        account_codes_set = []
        min_code = None
        max_code = None
        if not df.empty:
            for col_idx in range(min(len(df.columns), 3)):
                for val in df.iloc[:, col_idx].dropna():
                    clean_code = str(val).replace('.', '').strip()
                    if clean_code.isdigit() and 1 <= len(clean_code) <= 4:
                        if clean_code not in account_codes_set:
                            account_codes_set.append(clean_code)
                        c_num = int(clean_code)
                        if min_code is None or c_num < min_code:
                            min_code = c_num
                        if max_code is None or c_num > max_code:
                            max_code = c_num
        
        metadata = {
            'report_id': report_id,
            'table_index': table_num,
            'start_line': start_line,
            'parent_table_start_line': parent_start_line,
            'page_number': page_num,
            'csv_path': f'data/{csv_filename}',
            'ticker': ticker,
            'company_name': company_name,
            'year': int(year) if year and year.isdigit() else None,
            'table_context': table_context,
            'table_type': table_type,
            'headers': table_headers,
            'preview': preview_text,
            'item_col_text': item_col_str,
            'account_codes_set': account_codes_set,
            'exact_metric_labels': exact_metric_labels,
            'table_scope_summary': {
                'min_code': min_code,
                'max_code': max_code,
                'first_label': exact_metric_labels[0] if exact_metric_labels else "",
                'last_label': exact_metric_labels[-1] if exact_metric_labels else ""
            }
        }
        metadata_list.append(metadata)
            
    return metadata_list, errors

def main():
    data_dir = 'd:/ROAD_AI/data'
    os.makedirs(data_dir, exist_ok=True)
    
    # Load code_stock.csv to build mapping ticker -> company name
    ticker_to_name = {}
    code_stock_path = 'd:/ROAD_AI/code_stock.csv'
    if os.path.exists(code_stock_path):
        try:
            # UTF-8 with BOM might have been saved
            df_stock = pd.read_csv(code_stock_path, encoding='utf-8-sig')
            for _, row in df_stock.iterrows():
                ticker = str(row.iloc[0]).strip()
                name = str(row.iloc[1]).strip()
                ticker_to_name[ticker] = name
        except Exception as e:
            print(f'Warning: failed to load code_stock.csv: {e}')
            
    input_dir = 'd:/ROAD_AI/financial_statements'
    txt_files = glob.glob(os.path.join(input_dir, '*/*/*/*.txt'))
    print(f'Found {len(txt_files)} text reports to process.')
    
    all_metadata = []
    all_errors = []
    
    processed_count = 0
    total_files = len(txt_files)
    
    print(f'Starting extraction using ProcessPoolExecutor...')
    with ProcessPoolExecutor() as executor:
        # Submit tasks passing ticker_to_name mapping
        futures = {executor.submit(process_single_file, f_path, data_dir, ticker_to_name): f_path for f_path in txt_files}
        
        for future in as_completed(futures):
            f_path = futures[future]
            processed_count += 1
            
            try:
                metadata_list, errors = future.result()
                if metadata_list:
                    all_metadata.extend(metadata_list)
                if errors:
                    all_errors.extend(errors)
            except Exception as e:
                all_errors.append(f'Exception in process for {f_path}: {str(e)}')
                
            if processed_count % 50 == 0 or processed_count == total_files:
                print(f'Processed {processed_count}/{total_files} files ({(processed_count/total_files)*100:.1f}%) - Extracted {len(all_metadata)} tables.')
                sys.stdout.flush()
                
    metadata_json_path = 'd:/ROAD_AI/metadata.json'
    print(f'Saving metadata for {len(all_metadata)} tables to {metadata_json_path}...')
    with open(metadata_json_path, 'w', encoding='utf-8') as f:
        json.dump(all_metadata, f, ensure_ascii=False, indent=2)
        
    if all_errors:
        error_log_path = 'd:/ROAD_AI/errors.log'
        print(f'Logging {len(all_errors)} errors to {error_log_path}...')
        with open(error_log_path, 'w', encoding='utf-8') as f:
            for err in all_errors:
                f.write(err + '\n')
                
    print('Data extraction completed successfully!')

if __name__ == '__main__':
    main()
