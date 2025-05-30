# File Deduplicator - GUI Overview

This is a **desktop application** with a **graphical user interface (GUI)** that lets users find and manage duplicate files and similar pics.

---

## 🧰 Main Features Available in the Interface

### 1. **File Scanning**
- Lets you select a **directory to scan**
- Supports filtering by:
  - **Minimum file size**
  - **Maximum file size**
  - **File extensions** (e.g., `.jpg`, `.png`)
- Shows status messages

### 2. **Duplicate Finder**
- Analyzes scanned files to find **duplicates**
- Uses smart hashing techniques from the backend
- Displays results as groups of duplicate files

### 3. **Similar Image Finder**
- Finds **visually similar images**, using perceptual hashing
- Allows adjusting **similarity threshold**(default is 5):
  - Lower = stricter match
  - Higher = more differences allowed
- Works only on image files

# Important Note 1: Scan Required for All Analyses

The "Find Duplicates" and "Find Similar Pictures" features **do not run the scanner automatically**.

They only work with **already scanned files** that is present on tree widget. So before searching dublicats or similar files, run scanning to update filelist.

# Important Note 2: Program Works Silently (No Progress Bar) 

This program currently works without a visible progress bar , which can make it seem like it's not doing anything — especially when processing large numbers of files. 

✅ What’s Actually Happening 

The app is working in the background using a worker thread , so it doesn’t freeze — but it gives very limited feedback during processing. 


### 4. **Preferences / Settings**
You can configure:

| Setting | Description |
|--------|-------------|
| **Default Directory** | Folder to scan by default |
| **Minimum Size** | Only scan files larger than this |
| **Maximum Size** | Only scan files smaller than this |
| **Extensions** | Which file types to include (e.g., `.jpg,.png`) |
| **Image Threshold** | How strict similarity detection should be |

> Changes saved automatically for next use.

---

## 🖥️ User Interface Elements

### - **Left Panel (Tree View)**
Shows:
- List of scanned files
- Or grouped duplicate/similar files
- Can expand/collapse groups
- Supports **multiple selection**

### - **Right Panel (Image Preview)**
- Shows preview of selected image
- If not an image, shows "Not an image"
- Double-click opens file or folder

### - **Context Menu (Right-click)**
Available actions:
- **Open File**
- **Reveal in Explorer**
- **Move to Trash**

> For multiple selections: only "Move to Trash" is available

---

## 📁 File Management

You can:
- **Save scan results** to a JSON file
- **Load previously saved results** from a JSON file
- **Move files to trash** directly from the app

---

## ⚙️ Menu Options

### **File Menu**
- `Save Results` – Save current scan to JSON
- `Load Results` – Load from JSON file

### **Scan Menu**
- `Start Scan` – Begin scanning directory
- `Stop Scan` – Stop ongoing scan
- `Preferences...` – Change settings

### **Look For Menu**
- `Duplicates` – Find exact duplicate files
- `Similar Pictures` – Find visually similar images

### **Help Menu**
- `About` – Info about the app
- `Contact` – Developer info

---

## 🧪 Technical Notes

- Built using **Python** and **PyQt5**
- Uses a **worker thread** to avoid freezing the UI during scans
- Efficiently handles large numbers of files
- Supports saving/loading results for later analysis

---

## ✅ Summary

This GUI makes it easy to:
- Scan folders and filter files
- Find exact duplicates or similar images
- Preview and manage files
- Save/load results
- Delete or explore files directly from the app

It's a **user-friendly front-end** for a powerful deduplication engine. I describe it later.