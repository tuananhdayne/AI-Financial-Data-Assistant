import json
import os
import shutil
import zipfile
import re

def convert_single_file(name):
    input_json = f'd:/ROAD_AI/submission_{name}_1indexed.json'
    output_json = f'd:/ROAD_AI/submission_{name}_startline.json'
    output_zip = f'd:/ROAD_AI/submission_{name}_startline.zip'
    metadata_path = 'd:/ROAD_AI/metadata.json'
    temp_dir = f'd:/ROAD_AI/temp_startline_{name}'
    
    if not os.path.exists(input_json):
        print(f"File {input_json} does not exist!")
        return
        
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)
    os.makedirs(temp_dir, exist_ok=True)
    
    # Build lookup map: (report_id, table_index) -> start_line
    with open(metadata_path, 'r', encoding='utf-8') as f:
        metadata_db = json.load(f)
    metadata_map = {}
    for item in metadata_db:
        rep_id = item['report_id']
        tbl_idx = item['table_index']
        metadata_map[(rep_id, tbl_idx)] = item['start_line']
        
    print(f"Reading from {input_json}...")
    with open(input_json, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    new_data = []
    
    for item in data:
        new_item = item.copy()
        
        # Convert relevant_tables to start_line (1-based index from metadata)
        new_tables = []
        for tbl in item.get("relevant_tables", []):
            if "|" in tbl:
                doc_id, tbl_idx_str = tbl.split("|")
                try:
                    tbl_idx = int(tbl_idx_str)
                    start_line = metadata_map.get((doc_id, tbl_idx))
                    if start_line is not None:
                        new_tables.append(f"{doc_id}|{start_line}")
                    else:
                        new_tables.append(tbl)
                except ValueError:
                    new_tables.append(tbl)
            else:
                new_tables.append(tbl)
        new_item["relevant_tables"] = new_tables
        
        # Copy the CSV files to temp directory (evidence remains unchanged)
        for ev in item.get("evidence", []):
            csv_path = ev["csv_path"]
            csv_base = os.path.basename(csv_path)
            src_file = os.path.join('d:/ROAD_AI/data', csv_base)
            dest_file = os.path.join(temp_dir, csv_base)
            if os.path.exists(src_file):
                shutil.copy2(src_file, dest_file)
                
        new_data.append(new_item)
        
    # Write the startline JSON
    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump(new_data, f, ensure_ascii=False, indent=2)
        
    # Zip them up
    if os.path.exists(output_zip):
        os.remove(output_zip)
        
    print(f"Zipping {output_zip}...")
    with zipfile.ZipFile(output_zip, 'w', zipfile.ZIP_DEFLATED) as z:
        z.write(output_json, 'submission.json')
        for root, dirs, files in os.walk(temp_dir):
            for file in files:
                file_path = os.path.join(root, file)
                z.write(file_path, f"data/{file}")
                
    shutil.rmtree(temp_dir)
    print(f"Done! {output_zip} created successfully.")

if __name__ == '__main__':
    for name in ['hybrid_rag', 'llm_only', 'bm25_only']:
        convert_single_file(name)
