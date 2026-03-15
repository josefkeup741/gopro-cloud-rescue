# GoPro Cloud Rescue

A lightweight, automated tool to rescue your entire media library from GoPro's cloud servers when the official website fails.

## The Problem
If you have hundreds of videos stored in GoPro's cloud, downloading them is notoriously difficult. GoPro's "Download All" button has a hidden API limit: it often silently drops your request, giving you a zip file of only ~30 videos while ignoring the rest. Furthermore, trying to generate a Share Link for older media often results in a frustrating `"Media doesn't exist in the cloud"` error. 

This utility bypasses the broken web interface. It extracts your complete media list directly from the site's background data, interacts straight with the GoPro API, and downloads your entire library in safe, stable batches without crashing. 

## How to Use It (No Coding Required)

### Step 1: Get Your `.har` File (The Magic Key)
To bypass the broken download button, we need to capture the hidden IDs for your videos while the webpage loads.
1. Log into your GoPro Media Library.
2. Press **F12** on your keyboard to open Developer Tools, and click on the **Network** tab.
3. Refresh the webpage. 
4. **Slowly scroll all the way to the absolute bottom** of your GoPro media library. You must scroll to the bottom so the website is forced to load the data for every single video you own. 
5. Once at the bottom, inside of the network tab click the download botton that says Export Har when you hover over it.
6. Name the file `gopro.com.har` and save it to an empty folder on your desktop.

### Step 2: Run the Rescue App
1. Go to the [Releases](../../releases) tab on the right side of this page and download `gopro_rescue.exe`.
2. Move the `.exe` file into the exact same folder as your `gopro.com.har` file. 
3. Double-click `gopro_rescue.exe`. 
4. The terminal will open, read your file, and automatically begin downloading your footage in batches. It will automatically unzip the videos into a new `GoPro_Library_Recovered` folder and delete the heavy `.zip` files as it goes to save your hard drive space.

*Note: Because this is an independently developed tool, Windows Defender or your browser may flag the `.exe` as an "Unrecognized App." This is a normal false positive. Simply click "More Info" and then "Run Anyway."*

## For Developers (Running the Source Code)
If you prefer to run the raw Python script yourself instead of the compiled `.exe`:

1. Clone this repository.
2. Install the required dependencies:
   ```bash
   pip install requests tqdm
   ```
3. Place your `gopro.com.har` file in the root directory.
4. Run the script:
   ```bash
   python gopro_rescue.py
   ```

## Features
* **Resume Capability:** If your internet drops, simply run the app again. It will skip the files you already have and pick up exactly where it left off.
* **Storage Friendly:** Downloads in 5-file batches and auto-deletes the compressed folders after extracting, ensuring you don't need double the hard drive space.
* **Low Memory Footprint:** Streams the files directly to your disk in 8KB chunks, using almost zero RAM regardless of file size.
