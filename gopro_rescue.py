import re
import requests
import os
import zipfile
import time
from tqdm import tqdm

# Constants
COMPLETED_LOG = "completed_ids.txt"
OUTPUT_FOLDER = "GoPro_Library_Recovered"
TEMP_ZIP = "gopro_temp_batch.zip"

def extract_ids(har_filename):
    print(f"\n--- STEP 1: Scanning {har_filename} ---")
    try:
        with open(har_filename, 'r', encoding='utf-8', errors='ignore') as file:
            content = file.read()
            
        pattern = r'\\"id\\":\\"([a-zA-Z0-9]{13})\\"'
        found_ids = list(set(re.findall(pattern, content)))
        
        if not found_ids:
            print("❌ No IDs found. Make sure you scrolled to the bottom of your media library before saving the HAR file.")
            return None
            
        print(f"✅ Success! Found {len(found_ids)} unique video IDs.")
        return found_ids
    except FileNotFoundError:
        print(f"❌ Error: Could not find '{har_filename}'. Make sure it's in the same folder as this script.")
        return None

def get_completed_ids():
    """Reads the ledger to see which videos have already been successfully extracted."""
    if not os.path.exists(COMPLETED_LOG):
        return set()
    with open(COMPLETED_LOG, 'r') as f:
        content = f.read()
    return set(vid_id.strip() for vid_id in content.split(',') if vid_id.strip())

def log_completed_ids(batch_ids):
    """Writes successfully extracted IDs to the ledger."""
    with open(COMPLETED_LOG, 'a') as f:
        f.write(",".join(batch_ids) + ",")

def process_pipeline(all_ids, batch_size=5):
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)
    
    # Check the ledger and filter out videos we already have
    completed_ids = get_completed_ids()
    pending_ids = [vid for vid in all_ids if vid not in completed_ids]
    
    if not pending_ids:
        print(f"\n🎉 All {len(all_ids)} videos have already been successfully downloaded and extracted!")
        return

    print(f"\n--- STEP 2: Processing Pipeline ({len(pending_ids)} files remaining) ---")
    
    # Group the remaining IDs into batches
    pending_batches = [pending_ids[i:i + batch_size] for i in range(0, len(pending_ids), batch_size)]
    pass_number = 1
    
    while pending_batches:
        failed_batches = []
        
        if pass_number > 1:
            print(f"\n🔄 --- RETRY PASS {pass_number}: Attempting {len(pending_batches)} failed batches ---")
            
        for i, batch in enumerate(pending_batches):
            batch_str = ",".join(batch)
            url = f"https://api.gopro.com/media/x/zip/source?ids={batch_str}"
            
            print(f"\n📥 Processing Batch {i + 1} of {len(pending_batches)} (Contains {len(batch)} files)...")
            
            try:
                # 1. DOWNLOAD
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                }
                with requests.get(url, headers=headers, stream=True) as response:
                with requests.get(url, stream=True) as response:
                    response.raise_for_status() 
                    total_size = int(response.headers.get('content-length', 0))
                    
                    with open(TEMP_ZIP, 'wb') as file, tqdm(
                        desc="Downloading", total=total_size, unit='iB',
                        unit_scale=True, unit_divisor=1024,
                    ) as progress_bar:
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk: 
                                file.write(chunk)
                                progress_bar.update(len(chunk))
                                
                # 2. INTEGRITY CHECK
                try:
                    with zipfile.ZipFile(TEMP_ZIP) as zf:
                        pass 
                except (zipfile.BadZipFile, Exception):
                    print(f"⚠️ Corruption detected in download. Deleting and queuing for retry...")
                    os.remove(TEMP_ZIP)
                    failed_batches.append(batch)
                    continue
                    
                # 3. EXTRACTION
                print(f"📦 Extracting batch to '{OUTPUT_FOLDER}'...")
                with zipfile.ZipFile(TEMP_ZIP, 'r') as zip_ref:
                    zip_ref.extractall(OUTPUT_FOLDER)
                    
                # 4. CLEANUP & LOGGING
                os.remove(TEMP_ZIP)
                log_completed_ids(batch)
                print(f"✅ Batch securely extracted and logged to ledger.")
                
            except Exception as e:
                print(f"❌ Error during processing: {e}")
                if os.path.exists(TEMP_ZIP):
                    os.remove(TEMP_ZIP)
                failed_batches.append(batch)
                time.sleep(2) # Brief pause so we don't spam the server on a failure
                
        # Update the list for the next loop. If empty, the while loop ends!
        pending_batches = failed_batches
        pass_number += 1
        
        if pending_batches:
            print("\n⏳ Waiting 5 seconds before retrying failed batches...")
            time.sleep(5)

    print(f"\n🎉 ALL DONE! Check the '{OUTPUT_FOLDER}' folder for your videos.")

if __name__ == "__main__":
    print("========================================")
    print("      GoPro Cloud Rescue Utility        ")
    print("========================================")
    
    har_input = input("Enter the name of your HAR file (Press Enter for default 'gopro.com.har'): ").strip()
    if har_input == "":
        har_input = "gopro.com.har"
        
    ids = extract_ids(har_input)
    
    if ids:
        proceed = input("\nReady to start downloading? (y/n): ").strip().lower()
        if proceed == 'y':
            process_pipeline(ids)
        else:
            print("Download cancelled.")
            
    input("\nPress Enter to exit...")
