import json
import os
import shutil
import zipfile
import re

def shift_zip():
    submission_path = 'd:/ROAD_AI/submission.json'
    temp_dir = 'd:/ROAD_AI/temp_submission_data'
    
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)
    os.makedirs(temp_dir, exist_ok=True)
    
    # Read the original submission.json
    with open(submission_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    new_data = []
    
    for item in data:
        new_item = item.copy()
        
        # 1. Shift relevant_tables
        new_tables = []
        for tbl in item.get("relevant_tables", []):
            if "|" in tbl:
                doc_id, tbl_idx = tbl.split("|")
                # Shift to 0-indexed
                new_idx = str(int(tbl_idx) - 1)
                new_tables.append(f"{doc_id}|{new_idx}")
            else:
                new_tables.append(tbl)
        new_item["relevant_tables"] = new_tables
        
        # 2. Shift evidence
        new_evidence = []
        for ev in item.get("evidence", []):
            var_name = ev["variable"]
            csv_path = ev["csv_path"]
            
            # Find the number in the csv filename
            match = re.search(r'_table_(\d+)\.csv$', csv_path)
            if match:
                old_idx = int(match.group(1))
                new_idx = old_idx - 1
                new_path = csv_path.replace(f"_table_{old_idx}.csv", f"_table_{new_idx}.csv")
                new_evidence.append({
                    "variable": var_name,
                    "csv_path": new_path
                })
                
                # We need to copy from original data/ to temp_submission_data/ as table_{new_idx}.csv
                src_file = os.path.join('d:/ROAD_AI', csv_path)
                dest_filename = os.path.basename(new_path)
                dest_file = os.path.join(temp_dir, dest_filename)
                
                if os.path.exists(src_file):
                    shutil.copy2(src_file, dest_file)
            else:
                new_evidence.append(ev)
                
        new_item["evidence"] = new_evidence
        new_data.append(new_item)
        
    # Write the modified submission.json
    modified_json_path = 'd:/ROAD_AI/submission_shifted.json'
    with open(modified_json_path, 'w', encoding='utf-8') as f:
        json.dump(new_data, f, ensure_ascii=False, indent=2)
        
    # Zip them up
    zip_path = 'd:/ROAD_AI/submission_shifted.zip'
    if os.path.exists(zip_path):
        os.remove(zip_path)
        
    print("Zipping files...")
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as z:
        # Add submission.json as submission.json
        z.write(modified_json_path, 'submission.json')
        # Add all files in temp_submission_data as data/filename
        for root, dirs, files in os.walk(temp_dir):
            for file in files:
                file_path = os.path.join(root, file)
                z.write(file_path, f"data/{file}")
                
    # Clean up
    shutil.rmtree(temp_dir)
    print("Done! submission_shifted.zip created successfully.")

if __name__ == '__main__':
    shift_zip()
