import re
import json
import requests
import os
import zipfile
import time
from tqdm import tqdm

# Constants
COMPLETED_LOG = "completed_ids.txt"
OUTPUT_FOLDER = "GoPro_Library_Recovered"
TEMP_ZIP = "gopro_temp_batch.zip"
COOKIE_FILE = "gopro_cookie.txt"


def load_cookie_file(path=None):
    """First non-empty, non-# line from path (default COOKIE_FILE); full Cookie header value. None if missing/empty."""
    path = path or COOKIE_FILE
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                return line
    except OSError:
        return None
    return None


def extract_browser_headers(har_filename):
    """Headers from the first successful GET to api.gopro.com in the HAR (replay for zip download).

    GoPro's zip endpoint expects a browser-like request; session cookies are often required.
    Returns (headers_dict, has_cookie).
    """
    skip_lower = {
        ":authority", ":method", ":path", ":scheme",
        "content-length", "accept-encoding",
        "if-none-match", "if-modified-since", "if-match", "if-unmodified-since",
    }
    try:
        with open(har_filename, "r", encoding="utf-8", errors="ignore") as f:
            har = json.load(f)
    except (OSError, json.JSONDecodeError, KeyError):
        return {}, False

    entries = har.get("log", {}).get("entries", [])
    for entry in entries:
        req = entry.get("request") or {}
        url = req.get("url") or ""
        if "api.gopro.com" not in url or req.get("method") != "GET":
            continue
        if (entry.get("response") or {}).get("status") != 200:
            continue

        out = {}
        for h in req.get("headers") or []:
            name, value = h.get("name", ""), h.get("value", "")
            low = name.lower()
            if name.startswith(":") or low in skip_lower or low == "accept":
                continue
            if low == "cookie":
                out["Cookie"] = value
            else:
                out[name] = value

        cookie_parts = []
        for c in req.get("cookies") or []:
            n, v = c.get("name"), c.get("value", "")
            if n:
                cookie_parts.append(f"{n}={v}")
        if cookie_parts and "Cookie" not in out:
            out["Cookie"] = "; ".join(cookie_parts)

        return out, bool(out.get("Cookie"))

    return {}, False


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

def process_pipeline(all_ids, har_filename, batch_size=5):
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)

    base_headers, _har_has_cookie = extract_browser_headers(har_filename)
    file_cookie = load_cookie_file()
    if file_cookie:
        base_headers["Cookie"] = file_cookie
    has_cookie = bool(base_headers.get("Cookie"))
    if not has_cookie:
        print(
            "\n⚠️  No session cookie found. Put your DevTools `Cookie` header value in "
            f"'{COOKIE_FILE}' (first non-empty line), or export a HAR that includes credentials for api.gopro.com.\n"
            "    HAR in Chrome: DevTools → Network → preserve log → reload while logged in → right‑click → "
            '"Save all as HAR with content".'
        )
    
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
                # 1. DOWNLOAD (reuse browser context from HAR; zip API rejects bare User-Agent-only requests)
                headers = dict(base_headers)
                headers.setdefault(
                    "User-Agent",
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                )
                headers.setdefault("Origin", "https://gopro.com")
                headers.setdefault("Referer", "https://gopro.com/")
                headers["Accept"] = "*/*"
                with requests.get(url, headers=headers, stream=True) as response:
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
                
            except requests.HTTPError as e:
                resp = e.response
                if resp is not None and resp.status_code == 403:
                    print(
                        f"❌ Error during processing: {e}\n"
                        "   (403 Forbidden: session is missing or expired. Refresh "
                        f"'{COOKIE_FILE}' with a new Cookie from DevTools (while logged in at gopro.com), "
                        "or capture a fresh HAR that includes credentials, then run this script again.)"
                    )
                else:
                    print(f"❌ Error during processing: {e}")
                if os.path.exists(TEMP_ZIP):
                    os.remove(TEMP_ZIP)
                failed_batches.append(batch)
                time.sleep(2)
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
            process_pipeline(ids, har_input)
        else:
            print("Download cancelled.")
            
    input("\nPress Enter to exit...")
