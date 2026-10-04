# GoPro Cloud Rescue

A lightweight, automated tool to rescue your entire media library from GoPro's cloud servers when the official website fails.

## The Problem

If you have hundreds of videos stored in GoPro's cloud, downloading them is notoriously difficult. GoPro's "Download All" button has a hidden API limit: it often silently drops your request, giving you a zip file of only ~30 videos while ignoring the rest. Furthermore, trying to generate a Share Link for older media often results in a frustrating `"Media doesn't exist in the cloud"` error.

This utility bypasses the broken web interface. It fetches your complete media list straight from the GoPro API (or from a HAR capture of the website), and downloads your entire library in safe, stable batches without crashing.

## How to Use It (No Coding Required)

[![GoPro Rescue Tutorial](https://img.youtube.com/vi/ALVnahS_QCU/0.jpg)](https://www.youtube.com/watch?v=ALVnahS_QCU)

**[Watch the Step-by-Step Video Tutorial on YouTube](https://youtu.be/ALVnahS_QCU)**

### Step 1: Get Your Auth Token (The Magic Key)

GoPro now rejects downloads that don't come from a logged-in account, so the app needs your login token. You copy it from your browser's cookies:

1. Log into your [GoPro Media Library](https://gopro.com/media-library/).
2. Press `F12` on your keyboard to open Developer Tools.
3. Open the **Application** tab (Chrome / Edge) or the **Storage** tab (Firefox). If you don't see it, click the `»` arrow next to the other tabs.
4. In the left sidebar, expand **Cookies** and click `https://gopro.com`.
5. Find the row named `gp_access_token`. Double-click its **Value**, then select all of it and copy it. It's a very long string (over a thousand characters), so make sure you copy the whole thing.
6. Create a text file named `Cookie.txt` in an empty folder on your desktop, paste the value into it, and save it.

The token expires after a while. If the app says *"GoPro rejected your auth token"*, log in again and copy a fresh one into `Cookie.txt`.

> **Keep your token private.** Anyone who has it can access your GoPro account until it expires. Don't share `Cookie.txt` or post it anywhere.

### Step 2: Run the Rescue App

1. Go to the [Releases](../../releases) tab on the right side of this page and download `gopro_rescue.exe`.
2. Move the `.exe` file into the exact same folder as your `Cookie.txt` file.
3. Double-click `gopro_rescue.exe`.
4. The app checks your token with GoPro. When it asks for a HAR file name, just press `Enter` and it will fetch your full media list straight from GoPro.
5. Type `y` to start. It downloads your footage in batches, unzips the videos into a new `GoPro_Library_Recovered` folder, and deletes the heavy `.zip` files as it goes to save your hard drive space.

### Optional: Use a `.har` File Instead

If you'd rather give the app a snapshot of your library than let it fetch the list from GoPro, you can capture one from the website:

1. Log into your GoPro Media Library.
2. Press `F12` on your keyboard to open Developer Tools, and click on the **Network** tab.
3. Refresh the webpage. The HAR file only includes requests made while the Network tab is open, so this step matters.
4. **Slowly scroll all the way to the absolute bottom** of your GoPro media library. You must scroll to the bottom so the website is forced to load the data for every single video you own.
5. Once at the bottom, inside of the network tab, click the download button that says "Export HAR" when you hover over it.
6. Save it as `gopro.com.har` in the same folder as the app, then type `gopro.com.har` when the app asks for a HAR file name.

You still need `Cookie.txt` from Step 1, because the downloads themselves require your token.

*Note: Because this is an independently developed tool, Windows Defender or your browser may flag the `.exe` as an "Unrecognized App." This is a normal false positive. Simply click "More Info" and then "Run Anyway."*

## For Developers (Running the Source Code)

If you prefer to run the raw Python script yourself instead of the compiled `.exe`:

1. Clone this repository.
2. Install the required dependencies:
   ```bash
   pip install requests tqdm
   ```
3. Put your token in `Cookie.txt` in the root directory (see Step 1), or set it in the `AUTH_TOKEN` environment variable. `Cookie.txt` can hold either just the token or the whole browser cookie string. If neither is found, the script asks you to paste the token.
4. Run the script:
   ```bash
   python gopro_rescue.py
   ```

## Features

* **Resume Capability:** If your internet drops, simply run the app again. It will skip the files you already have and pick up exactly where it left off.
* **Storage Friendly:** Downloads in 5-file batches and auto-deletes the compressed folders after extracting, ensuring you don't need double the hard drive space.
* **Low Memory Footprint:** Streams the files directly to your disk in 8KB chunks, using almost zero RAM regardless of file size.
