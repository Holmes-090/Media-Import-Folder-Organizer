# Import Folder Cleanup

A Windows application for organizing and renaming folders and files from bulk media downloads, particularly useful for Reddit post downloads.

## Features

- **Flexible Folder Renaming**: Customize how folder names are cleaned up
  - Remove first X characters
  - Remove everything before/after specific characters
  - Remove digits and special characters
  - Replace underscores with spaces
  - Convert to title case

- **Automatic File Renaming**: Files inside folders are renamed to match the cleaned folder name with numbered suffixes

- **Video/Audio Merging**: Automatically detects and merges related video and audio files using FFmpeg
  - Supports common formats: .mp4/.m4a, .webm/.audio, etc.
  - Intelligent pairing based on filename patterns

- **Preview Mode**: See all changes before applying them

- **Configuration Management**: Save and load custom renaming rules

## Requirements

- Python 3.7+
- FFmpeg (must be installed and available in PATH)
- Windows OS

## Installation

1. Ensure Python is installed on your system
2. Install FFmpeg and add it to your system PATH
3. Download the application files
4. Run `python main.py` or double-click `run.bat`

## Usage

1. **Select Folder**: Click "Browse" to select the folder containing your media downloads
2. **Configure Rules**: Set up your preferred renaming rules
3. **Preview**: Click "Preview Changes" to see what will be modified
4. **Apply**: Click "Apply Changes" to process all folders and files

## Example

Input folder structure:
```
Downloads/
├── 112j23_My_test_post/
│   ├── video.mp4
│   └── audio.m4a
└── 456k78_Another_post/
    └── image.jpg
```

After processing:
```
Downloads/
├── My Test Post/
│   └── My Test Post_merged.mp4
└── Another Post/
    └── Another Post.jpg
```

## Configuration

The app saves your settings in `config.json`. You can also save custom configurations for different use cases.

## Safety Features

- Preview mode shows all changes before applying
- Confirmation dialog when applying changes
- Error handling and logging
- Automatic conflict resolution for duplicate names

## Troubleshooting

- **FFmpeg not found**: Ensure FFmpeg is installed and in your system PATH
- **Permission errors**: Run as administrator if needed
- **Large files**: Video merging may take time for large files

## License

This project is open source and available under the MIT License. 