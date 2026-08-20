import json
import os
import shutil
import zipfile
import re

def unshift_single_file(name):
    input_json = f'd:/ROAD_AI/submission_{name}.json'
    output_json = f'd:/ROAD_AI/submission_{name}_1indexed.json'
    output_zip = f'd:/ROAD_AI/submission_{name}_1indexed.zip'
    temp_dir = f'd:/ROAD_AI/temp_unshift_{name}'
    
    if not os.path.exists(input_json):
        print(f"File {input_json} does not exist. Skipping.")
        return
        
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)
    os.makedirs(temp_dir, exist_ok=True)
    
    print(f"Reading from {input_json}...")
    with open(input_json, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    new_data = []
    
    for item in data:
        new_item = item.copy()
        
        # 1. Unshift relevant_tables (add 1)
        new_tables = []
        for tbl in item.get("relevant_tables", []):
            if "|" in tbl:
                doc_id, tbl_idx = tbl.split("|")
                new_idx = str(int(tbl_idx) + 1)
                new_tables.append(f"{doc_id}|{new_idx}")
            else:
                new_tables.append(tbl)
        new_item["relevant_tables"] = new_tables
        
        # 2. Unshift evidence (add 1)
        new_evidence = []
        for ev in item.get("evidence", []):
            var_name = ev["variable"]
            csv_path = ev["csv_path"]
            
            match = re.search(r'_table_(\d+)\.csv$', csv_path)
            if match:
                old_idx = int(match.group(1))
                new_idx = old_idx + 1
                new_path = csv_path.replace(f"_table_{old_idx}.csv", f"_table_{new_idx}.csv")
                new_evidence.append({
                    "variable": var_name,
                    "csv_path": new_path
                })
                
                # Copy from original flat data/ to temp folder
                csv_base = os.path.basename(new_path)
                src_file = os.path.join('d:/ROAD_AI/data', csv_base)
                dest_file = os.path.join(temp_dir, csv_base)
                
                if os.path.exists(src_file):
                    shutil.copy2(src_file, dest_file)
            else:
                new_evidence.append(ev)
                
        new_item["evidence"] = new_evidence
        new_data.append(new_item)
        
    # Write the unshifted JSON
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
        unshift_single_file(name)
