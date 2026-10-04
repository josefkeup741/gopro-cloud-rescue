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
TOKEN_FILE = "Cookie.txt"

def load_auth_token():
    """Reads the GoPro auth token from the AUTH_TOKEN env var, Cookie.txt, or a prompt."""
    token = os.environ.get("AUTH_TOKEN", "").strip()
    if not token and os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, 'r', encoding='utf-8', errors='ignore') as file:
            content = file.read().strip()
        # The file may hold the whole browser cookie string or just the token itself
        match = re.search(r'gp_access_token=([^;\s]+)', content)
        token = match.group(1) if match else content
    if not token:
        token = input("Paste your GoPro auth token (the value of the 'gp_access_token' cookie): ").strip()
    return token

def api_headers(auth_token):
    return {
        "Accept": "application/vnd.gopro.jk.media+json; version=2.0.0",
        "Authorization": f"Bearer {auth_token}",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

def validate_auth_token(auth_token):
    """Checks the token with GoPro up front, so an expired one fails before any download starts."""
    response = requests.get("https://api.gopro.com/media/user", headers=api_headers(auth_token))
    if response.status_code != 200:
        print(f"❌ GoPro rejected your auth token (HTTP {response.status_code}). Log in to gopro.com again and copy a fresh 'gp_access_token'.")
        return False
    print("✅ Auth token accepted by GoPro.")
    return True

def extract_ids(har_filename):
    print(f"\n--- STEP 1: Scanning {har_filename} ---")
    try:
        with open(har_filename, 'r', encoding='utf-8', errors='ignore') as file:
            content = file.read()
            
        # Older media use 13-character IDs; media uploaded since late 2025 use 24-character hex IDs
        pattern = r'\\"id\\":\\"([a-zA-Z0-9]{13}|[0-9a-f]{24})\\"'
        found_ids = list(set(re.findall(pattern, content)))
        
        if not found_ids:
            print("❌ No IDs found. Make sure you scrolled to the bottom of your media library before saving the HAR file.")
            return None
            
        print(f"✅ Success! Found {len(found_ids)} unique video IDs.")
        return found_ids
    except FileNotFoundError:
        print(f"❌ Error: Could not find '{har_filename}'. Make sure it's in the same folder as this script.")
        return None

def fetch_ids_from_api(auth_token):
    """Pages through your GoPro media library and returns every media ID, so no HAR file is needed."""
    print("\n--- STEP 1: Fetching your media list from GoPro ---")
    found_ids = []
    page = 1
    total_pages = 1

    while page <= total_pages:
        params = {"per_page": 100, "page": page, "fields": "id"}
        response = requests.get("https://api.gopro.com/media/search", params=params, headers=api_headers(auth_token))
        if response.status_code != 200:
            print(f"❌ Failed to fetch page {page} of your media list (HTTP {response.status_code}).")
            return None

        content = response.json()
        total_pages = content.get("_pages", {}).get("total_pages", 1)
        found_ids.extend(item["id"] for item in content.get("_embedded", {}).get("media", []))
        page += 1

    found_ids = list(dict.fromkeys(found_ids))
    if not found_ids:
        print("❌ Your GoPro media library appears to be empty.")
        return None

    print(f"✅ Success! Found {len(found_ids)} unique video IDs.")
    return found_ids

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

def process_pipeline(all_ids, auth_token, batch_size=5):
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
                with requests.get(url, headers=api_headers(auth_token), stream=True) as response:
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
    
    auth_token = load_auth_token()
    if not validate_auth_token(auth_token):
        input("\nPress Enter to exit...")
        raise SystemExit(1)

    har_input = input("Enter the name of your HAR file (or press Enter to fetch your media list straight from GoPro): ").strip()
    ids = extract_ids(har_input) if har_input else fetch_ids_from_api(auth_token)
    
    if ids:
        proceed = input("\nReady to start downloading? (y/n): ").strip().lower()
        if proceed == 'y':
            process_pipeline(ids, auth_token)
        else:
            print("Download cancelled.")
            
    input("\nPress Enter to exit...")
