Bulk Folder Renamer & Video/Audio Merger
========================================

DESCRIPTION
-----------
This program batch-renames folders and their contents based on customizable rules.
It can also merge matching video and audio .mp4 files together using FFmpeg.

FEATURES
--------
- Rename multiple folders according to configurable rules:
  * Remove first/last characters
  * Remove everything before/after a certain character
  * Remove digits or special characters
  * Replace underscores with spaces
  * Convert to title case
- Rename files inside each folder to match the folder name.
- Optionally rejoin split .mp4 files (video and audio parts) using FFmpeg.
- Save and load configuration presets.

REQUIREMENTS
------------
- Windows (64-bit)
- FFmpeg installed (if using .py file - for audio/video merging)

USAGE
-----
1. Run the program
2. Click "Browse" to select the main folder containing subfolders you want to process.
3. Select specific subfolders to limit changes, or click "Select All".
4. Adjust renaming rules in the "Folder Renaming Options" section.
5. Choose processing options
6. Click "Preview Changes" to see what will happen.
7. If satisfied, click "Apply Changes" to perform the renaming (and merging if enabled).

MERGING VIDEO AND AUDIO
-----------------------
If "Rejoin Split .mp4 Files" is enabled:
- The program looks for files with the same base name, where one ends in " 2" (e.g., "Video.mp4" and "Video 2.mp4").
- It attempts to merge them into a single .mp4 file using FFmpeg.
- The original split files are deleted if the merge is successful.

SAVING & LOADING CONFIGURATION
------------------------------
- Click "Save Configuration" to store your current renaming settings as a .json file.
- Click "Load Configuration" to reuse them later.

DISCLAIMER
----------
Always preview changes before applying them to avoid accidental data loss.
The author is not responsible for any unintended file/folder modifications.
