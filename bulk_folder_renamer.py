import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import os
import re
import json
import threading
import queue
from pathlib import Path
import subprocess
from datetime import datetime
import sys
import shutil
import hashlib
from collections import defaultdict
try:
    from PIL import Image
except ImportError:
    Image = None

def get_ffmpeg_path():
    """Return a path/command to ffmpeg that works for source and PyInstaller builds.

    Resolution order (Windows-friendly):
    - If frozen (PyInstaller): try bundled location via sys._MEIPASS and beside the executable
    - Same directory as this script
    - On PATH via shutil.which('ffmpeg')
    - Fallback to 'ffmpeg' (let subprocess rely on PATH)
    """
    candidates = []

    # PyInstaller bundled temporary dir
    if getattr(sys, 'frozen', False):
        try:
            meipass_dir = getattr(sys, '_MEIPASS', None)
            if meipass_dir:
                candidates.append(os.path.join(meipass_dir, 'ffmpeg.exe'))
                candidates.append(os.path.join(meipass_dir, 'ffmpeg'))
        except Exception:
            pass
        # Directory of the executable
        exe_dir = os.path.dirname(sys.executable)
        candidates.append(os.path.join(exe_dir, 'ffmpeg.exe'))
        candidates.append(os.path.join(exe_dir, 'ffmpeg'))

    # Directory of this source file
    try:
        here = os.path.dirname(os.path.abspath(__file__))
        candidates.append(os.path.join(here, 'ffmpeg.exe'))
        candidates.append(os.path.join(here, 'ffmpeg'))
    except Exception:
        pass

    # PATH resolution
    which_ffmpeg = shutil.which('ffmpeg')
    if which_ffmpeg:
        candidates.append(which_ffmpeg)

    # Pick the first existing/accessible candidate
    for path in candidates:
        if path and os.path.exists(path):
            return path

    # Fallback: rely on PATH
    return 'ffmpeg'

class ImportFolderCleanup:
    def __init__(self, root):
        self.root = root
        self.root.title("Import Folder Cleanup")
        self.root.geometry("800x600")
        self.root.minsize(800, 600)
        
        # Variables
        self.selected_folder = tk.StringVar()
        # Media Merger tab state
        self.merger_selected_folder = tk.StringVar()
        # File Sorter tab state
        self.sorter_selected_folder = tk.StringVar()
        self.sorter_export_folder = tk.StringVar()
        # Folder Cleanup tab state
        self.cleanup_selected_folder = tk.StringVar()
        # Duplicate Finder tab state
        self.duplicate_selected_folder = tk.StringVar()
        self.processing_queue = queue.Queue()
        self.is_processing = False
        self.media_is_processing = False
        self.sorter_is_processing = False
        self.cleanup_is_processing = False
        self.duplicate_is_processing = False
        
        # Video/Audio file extensions
        self.video_extensions = {'.mp4', '.webm', '.avi', '.mov', '.mkv'}
        self.audio_extensions = {'.m4a', '.aac', '.mp3', '.wav', '.flac', '.audio'}
        
        self.setup_ui()
        self.load_config()
        
    def setup_ui(self):
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        # Notebook and tabs
        notebook = ttk.Notebook(self.root)
        notebook.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # ========================= Renamer Tab =========================
        renamer_frame = ttk.Frame(notebook, padding="10")
        notebook.add(renamer_frame, text="Bulk Folder Renamer")

        renamer_frame.columnconfigure(0, weight=3)
        renamer_frame.columnconfigure(1, weight=1)

        ttk.Label(renamer_frame, text="Select Import Folder:").grid(row=0, column=0, sticky=tk.W, pady=(0, 5))
        folder_frame = ttk.Frame(renamer_frame)
        folder_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        folder_frame.columnconfigure(0, weight=1)

        ttk.Entry(folder_frame, textvariable=self.selected_folder, state="readonly").grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 5))
        ttk.Button(folder_frame, text="Browse", command=self.browse_folder).grid(row=0, column=1)

        subfolders_frame = ttk.LabelFrame(renamer_frame, text="Subfolders (control/shift click to select to limit changes)", padding="10")
        subfolders_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        subfolders_frame.columnconfigure(0, weight=1)
        subfolders_frame.rowconfigure(0, weight=1)

        list_container = ttk.Frame(subfolders_frame)
        list_container.grid(row=0, column=0, sticky=(tk.W, tk.E))
        list_container.columnconfigure(0, weight=1)

        self.subfolder_listbox = tk.Listbox(list_container, selectmode=tk.EXTENDED, height=6, exportselection=False)
        self.subfolder_listbox.grid(row=0, column=0, sticky=(tk.W, tk.E))
        sub_scroll = ttk.Scrollbar(list_container, orient=tk.VERTICAL, command=self.subfolder_listbox.yview)
        sub_scroll.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.subfolder_listbox.configure(yscrollcommand=sub_scroll.set)

        select_all_frame = ttk.Frame(subfolders_frame)
        select_all_frame.grid(row=1, column=0, sticky=tk.W, pady=(6, 0))
        ttk.Button(select_all_frame, text="Select All", command=self.select_all_subfolders).grid(row=0, column=0, sticky=tk.W)

        options_frame = ttk.LabelFrame(renamer_frame, text="Folder Renaming Options", padding="10")
        options_frame.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        options_frame.columnconfigure(1, weight=1)

        ttk.Label(options_frame, text="Remove first X characters:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.remove_first_var = tk.StringVar(value="0")
        ttk.Entry(options_frame, textvariable=self.remove_first_var, width=10).grid(row=0, column=1, sticky=tk.W, padx=(10, 0), pady=2)

        ttk.Label(options_frame, text="Remove last X characters:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.remove_last_var = tk.StringVar(value="0")
        ttk.Entry(options_frame, textvariable=self.remove_last_var, width=10).grid(row=1, column=1, sticky=tk.W, padx=(10, 0), pady=2)

        ttk.Label(options_frame, text="Remove everything before character:").grid(row=2, column=0, sticky=tk.W, pady=2)
        self.before_char_var = tk.StringVar()
        ttk.Entry(options_frame, textvariable=self.before_char_var, width=10).grid(row=2, column=1, sticky=tk.W, padx=(10, 0), pady=2)

        ttk.Label(options_frame, text="Remove everything after character:").grid(row=3, column=0, sticky=tk.W, pady=2)
        self.after_char_var = tk.StringVar()
        ttk.Entry(options_frame, textvariable=self.after_char_var, width=10).grid(row=3, column=1, sticky=tk.W, padx=(10, 0), pady=2)

        self.remove_digits_var = tk.BooleanVar()
        ttk.Checkbutton(options_frame, text="Remove all digits", variable=self.remove_digits_var).grid(row=4, column=0, columnspan=2, sticky=tk.W, pady=2)

        self.remove_special_var = tk.BooleanVar()
        ttk.Checkbutton(options_frame, text="Remove special characters", variable=self.remove_special_var).grid(row=5, column=0, columnspan=2, sticky=tk.W, pady=2)

        self.replace_underscores_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="Replace underscores with spaces", variable=self.replace_underscores_var).grid(row=6, column=0, columnspan=2, sticky=tk.W, pady=2)

        self.title_case_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="Convert to title case", variable=self.title_case_var).grid(row=7, column=0, columnspan=2, sticky=tk.W, pady=2)

        processing_frame = ttk.LabelFrame(renamer_frame, text="Processing Options", padding="10")
        processing_frame.grid(row=4, column=0, sticky=(tk.W, tk.E, tk.N), pady=(0, 10))

        self.rename_files_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(processing_frame, text="Rename files to folder name", variable=self.rename_files_var).grid(row=0, column=0, sticky=tk.W, pady=2)

        buttons_frame = ttk.Frame(renamer_frame)
        buttons_frame.grid(row=5, column=0, columnspan=2, pady=(0, 10))

        ttk.Button(buttons_frame, text="Preview Changes", command=self.preview_changes).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(buttons_frame, text="Apply Changes", command=self.apply_changes).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(buttons_frame, text="Save Configuration", command=self.save_config).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(buttons_frame, text="Load Configuration", command=self.load_config_dialog).pack(side=tk.LEFT)

        progress_frame = ttk.LabelFrame(renamer_frame, text="Progress", padding="10")
        progress_frame.grid(row=6, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        progress_frame.columnconfigure(0, weight=1)
        renamer_frame.rowconfigure(3, weight=1)

        self.progress_var = tk.StringVar(value="Ready")
        ttk.Label(progress_frame, textvariable=self.progress_var).grid(row=0, column=0, sticky=tk.W)

        log_frame = ttk.LabelFrame(renamer_frame, text="Log", padding="10")
        log_frame.grid(row=3, column=1, rowspan=2, sticky=(tk.W, tk.E, tk.N, tk.S))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        renamer_frame.rowconfigure(3, weight=1)

        self.log_text = scrolledtext.ScrolledText(log_frame, height=10, wrap=tk.WORD, width=40)
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # ========================= Media Merger Tab =========================
        merger_frame = ttk.Frame(notebook, padding="10")
        notebook.add(merger_frame, text="Media Merger")

        merger_frame.columnconfigure(0, weight=3)
        merger_frame.columnconfigure(1, weight=1)

        ttk.Label(merger_frame, text="Select Import Folder:").grid(row=0, column=0, sticky=tk.W, pady=(0, 5))
        m_folder_frame = ttk.Frame(merger_frame)
        m_folder_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        m_folder_frame.columnconfigure(0, weight=1)

        ttk.Entry(m_folder_frame, textvariable=self.merger_selected_folder, state="readonly").grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 5))
        ttk.Button(m_folder_frame, text="Browse", command=self.merger_browse_folder).grid(row=0, column=1)

        m_subfolders_frame = ttk.LabelFrame(merger_frame, text="Subfolders (control/shift click to select to limit changes)", padding="10")
        m_subfolders_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        m_subfolders_frame.columnconfigure(0, weight=1)
        m_subfolders_frame.rowconfigure(0, weight=1)

        m_list_container = ttk.Frame(m_subfolders_frame)
        m_list_container.grid(row=0, column=0, sticky=(tk.W, tk.E))
        m_list_container.columnconfigure(0, weight=1)

        self.merger_subfolder_listbox = tk.Listbox(m_list_container, selectmode=tk.EXTENDED, height=6, exportselection=False)
        self.merger_subfolder_listbox.grid(row=0, column=0, sticky=(tk.W, tk.E))
        m_sub_scroll = ttk.Scrollbar(m_list_container, orient=tk.VERTICAL, command=self.merger_subfolder_listbox.yview)
        m_sub_scroll.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.merger_subfolder_listbox.configure(yscrollcommand=m_sub_scroll.set)

        m_select_all_frame = ttk.Frame(m_subfolders_frame)
        m_select_all_frame.grid(row=1, column=0, sticky=tk.W, pady=(6, 0))
        ttk.Button(m_select_all_frame, text="Select All", command=self.merger_select_all_subfolders).grid(row=0, column=0, sticky=tk.W)

        m_buttons_frame = ttk.Frame(merger_frame)
        m_buttons_frame.grid(row=5, column=0, columnspan=2, pady=(0, 10))

        ttk.Button(m_buttons_frame, text="Preview Merges", command=self.media_preview_changes).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(m_buttons_frame, text="Apply Merges", command=self.media_apply_changes).pack(side=tk.LEFT, padx=(0, 5))

        m_progress_frame = ttk.LabelFrame(merger_frame, text="Progress", padding="10")
        m_progress_frame.grid(row=6, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        m_progress_frame.columnconfigure(0, weight=1)
        merger_frame.rowconfigure(3, weight=1)

        self.media_progress_var = tk.StringVar(value="Ready")
        ttk.Label(m_progress_frame, textvariable=self.media_progress_var).grid(row=0, column=0, sticky=tk.W)

        m_log_frame = ttk.LabelFrame(merger_frame, text="Log", padding="10")
        m_log_frame.grid(row=3, column=0, rowspan=2, sticky=(tk.W, tk.E, tk.N, tk.S))
        m_log_frame.columnconfigure(0, weight=1)
        m_log_frame.rowconfigure(0, weight=1)
        merger_frame.rowconfigure(3, weight=1)

        self.media_log_text = scrolledtext.ScrolledText(m_log_frame, height=10, wrap=tk.WORD, width=25)
        self.media_log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # ========================= File Sorter Tab =========================
        sorter_frame = ttk.Frame(notebook, padding="10")
        notebook.add(sorter_frame, text="File Sorter")

        sorter_frame.columnconfigure(0, weight=3)
        sorter_frame.columnconfigure(1, weight=1)

        # Source folder selection
        ttk.Label(sorter_frame, text="Select Source Folder:").grid(row=0, column=0, sticky=tk.W, pady=(0, 5))
        s_folder_frame = ttk.Frame(sorter_frame)
        s_folder_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        s_folder_frame.columnconfigure(0, weight=1)

        ttk.Entry(s_folder_frame, textvariable=self.sorter_selected_folder, state="readonly").grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 5))
        ttk.Button(s_folder_frame, text="Browse", command=self.sorter_browse_folder).grid(row=0, column=1)

        # Sorting options frame
        s_options_frame = ttk.LabelFrame(sorter_frame, text="Sorting Options", padding="10")
        s_options_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        s_options_frame.columnconfigure(1, weight=1)

        # Sort mode selection
        ttk.Label(s_options_frame, text="Sort Mode:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.sort_mode_var = tk.StringVar(value="all")
        sort_mode_frame = ttk.Frame(s_options_frame)
        sort_mode_frame.grid(row=0, column=1, sticky=tk.W, padx=(10, 0), pady=2)
        
        ttk.Radiobutton(sort_mode_frame, text="All file types", variable=self.sort_mode_var, value="all").pack(side=tk.LEFT)
        ttk.Radiobutton(sort_mode_frame, text="Specific type:", variable=self.sort_mode_var, value="specific").pack(side=tk.LEFT, padx=(10, 0))
        
        self.specific_extension_var = tk.StringVar(value=".mp4")
        specific_entry = ttk.Entry(sort_mode_frame, textvariable=self.specific_extension_var, width=10)
        specific_entry.pack(side=tk.LEFT, padx=(5, 0))

        # Image handling
        self.separate_images_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(s_options_frame, text="Separate images into individual categories (.png, .jpg, .gif, etc.)", 
                       variable=self.separate_images_var).grid(row=1, column=0, columnspan=2, sticky=tk.W, pady=2)

        # Output options frame
        s_output_frame = ttk.LabelFrame(sorter_frame, text="Output Options", padding="10")
        s_output_frame.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        s_output_frame.columnconfigure(1, weight=1)

        # Output mode selection
        self.output_mode_var = tk.StringVar(value="in_place")
        ttk.Radiobutton(s_output_frame, text="Create folders in source directory", 
                       variable=self.output_mode_var, value="in_place").grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=2)
        ttk.Radiobutton(s_output_frame, text="Export to different directory:", 
                       variable=self.output_mode_var, value="export").grid(row=1, column=0, sticky=tk.W, pady=2)

        # Export folder selection
        s_export_frame = ttk.Frame(s_output_frame)
        s_export_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(5, 0))
        s_export_frame.columnconfigure(0, weight=1)

        ttk.Entry(s_export_frame, textvariable=self.sorter_export_folder, state="readonly").grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 5))
        ttk.Button(s_export_frame, text="Browse", command=self.sorter_browse_export_folder).grid(row=0, column=1)

        # Export operation mode (copy vs move)
        s_export_mode_frame = ttk.Frame(s_output_frame)
        s_export_mode_frame.grid(row=3, column=0, columnspan=2, sticky=tk.W, pady=(5, 0))
        
        ttk.Label(s_export_mode_frame, text="Export mode:").pack(side=tk.LEFT)
        
        self.export_operation_var = tk.StringVar(value="copy")
        ttk.Radiobutton(s_export_mode_frame, text="Copy files (keep originals)", 
                       variable=self.export_operation_var, value="copy").pack(side=tk.LEFT, padx=(10, 0))
        ttk.Radiobutton(s_export_mode_frame, text="Move files (remove originals)", 
                       variable=self.export_operation_var, value="move").pack(side=tk.LEFT, padx=(10, 0))

        # Buttons frame
        s_buttons_frame = ttk.Frame(sorter_frame)
        s_buttons_frame.grid(row=4, column=0, columnspan=2, pady=(0, 10))

        ttk.Button(s_buttons_frame, text="Preview Sort", command=self.sorter_preview_changes).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(s_buttons_frame, text="Apply Sort", command=self.sorter_apply_changes).pack(side=tk.LEFT, padx=(0, 5))

        # Progress frame
        s_progress_frame = ttk.LabelFrame(sorter_frame, text="Progress", padding="10")
        s_progress_frame.grid(row=5, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        s_progress_frame.columnconfigure(0, weight=1)
        sorter_frame.rowconfigure(2, weight=1)

        self.sorter_progress_var = tk.StringVar(value="Ready")
        ttk.Label(s_progress_frame, textvariable=self.sorter_progress_var).grid(row=0, column=0, sticky=tk.W)

        # Log frame
        s_log_frame = ttk.LabelFrame(sorter_frame, text="Log", padding="10")
        s_log_frame.grid(row=2, column=1, rowspan=2, sticky=(tk.W, tk.E, tk.N, tk.S))
        s_log_frame.columnconfigure(0, weight=1)
        s_log_frame.rowconfigure(0, weight=1)
        sorter_frame.rowconfigure(2, weight=1)

        self.sorter_log_text = scrolledtext.ScrolledText(s_log_frame, height=10, wrap=tk.WORD, width=30)
        self.sorter_log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # ========================= Folder Cleanup Tab =========================
        cleanup_frame = ttk.Frame(notebook, padding="10")
        notebook.add(cleanup_frame, text="Folder Cleanup")

        cleanup_frame.columnconfigure(0, weight=3)
        cleanup_frame.columnconfigure(1, weight=1)

        # Folder selection
        ttk.Label(cleanup_frame, text="Select Folder to Clean:").grid(row=0, column=0, sticky=tk.W, pady=(0, 5))
        c_folder_frame = ttk.Frame(cleanup_frame)
        c_folder_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        c_folder_frame.columnconfigure(0, weight=1)

        ttk.Entry(c_folder_frame, textvariable=self.cleanup_selected_folder, state="readonly").grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 5))
        ttk.Button(c_folder_frame, text="Browse", command=self.cleanup_browse_folder).grid(row=0, column=1)

        # Subfolders selection
        c_subfolders_frame = ttk.LabelFrame(cleanup_frame, text="Subfolders (control/shift click to select to limit changes)", padding="10")
        c_subfolders_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        c_subfolders_frame.columnconfigure(0, weight=1)
        c_subfolders_frame.rowconfigure(0, weight=1)

        c_list_container = ttk.Frame(c_subfolders_frame)
        c_list_container.grid(row=0, column=0, sticky=(tk.W, tk.E))
        c_list_container.columnconfigure(0, weight=1)

        self.cleanup_subfolder_listbox = tk.Listbox(c_list_container, selectmode=tk.EXTENDED, height=6, exportselection=False)
        self.cleanup_subfolder_listbox.grid(row=0, column=0, sticky=(tk.W, tk.E))
        c_sub_scroll = ttk.Scrollbar(c_list_container, orient=tk.VERTICAL, command=self.cleanup_subfolder_listbox.yview)
        c_sub_scroll.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.cleanup_subfolder_listbox.configure(yscrollcommand=c_sub_scroll.set)

        c_select_all_frame = ttk.Frame(c_subfolders_frame)
        c_select_all_frame.grid(row=1, column=0, sticky=tk.W, pady=(6, 0))
        ttk.Button(c_select_all_frame, text="Select All", command=self.cleanup_select_all_subfolders).grid(row=0, column=0, sticky=tk.W)

        # Cleanup options frame
        c_options_frame = ttk.LabelFrame(cleanup_frame, text="Cleanup Options", padding="10")
        c_options_frame.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        c_options_frame.columnconfigure(0, weight=1)

        # Flatten folders option
        self.flatten_folders_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(c_options_frame, text="Flatten folders (move files from flat subfolders up one level)", 
                       variable=self.flatten_folders_var).grid(row=0, column=0, sticky=tk.W, pady=2)

        self.remove_empty_folders_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(c_options_frame, text="Remove empty folders after flattening", 
                       variable=self.remove_empty_folders_var).grid(row=1, column=0, sticky=tk.W, pady=2, padx=(20, 0))

        # Remove broken media files
        self.remove_broken_media_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(c_options_frame, text="Remove broken/empty media files (0 bytes, 0 duration, unreadable)", 
                       variable=self.remove_broken_media_var).grid(row=2, column=0, sticky=tk.W, pady=2)

        # Remove .mp4 files without thumbnails (audio-only files)
        self.remove_no_thumbnail_videos_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(c_options_frame, text="Remove .mp4 files that can't generate thumbnails (audio-only files)", 
                       variable=self.remove_no_thumbnail_videos_var).grid(row=3, column=0, sticky=tk.W, pady=2)

        # Remove temporary files
        self.remove_temp_files_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(c_options_frame, text="Remove temporary/cache files (.tmp, .part, .download, .ds_store, thumbs.db, etc)", 
                       variable=self.remove_temp_files_var).grid(row=4, column=0, sticky=tk.W, pady=2)

        # Custom extension removal
        self.remove_custom_extensions_var = tk.BooleanVar(value=False)
        custom_ext_frame = ttk.Frame(c_options_frame)
        custom_ext_frame.grid(row=5, column=0, sticky=(tk.W, tk.E), pady=2)
        custom_ext_frame.columnconfigure(1, weight=1)

        ttk.Checkbutton(custom_ext_frame, text="Remove files with extensions:", 
                       variable=self.remove_custom_extensions_var).grid(row=0, column=0, sticky=tk.W)
        self.custom_extensions_var = tk.StringVar(value=".bak, .log, .tmp")
        ttk.Entry(custom_ext_frame, textvariable=self.custom_extensions_var, width=30).grid(row=0, column=1, sticky=tk.W, padx=(5, 0))

        # Buttons frame
        c_buttons_frame = ttk.Frame(cleanup_frame)
        c_buttons_frame.grid(row=4, column=0, columnspan=2, pady=(0, 10))

        ttk.Button(c_buttons_frame, text="Preview Cleanup", command=self.cleanup_preview_changes).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(c_buttons_frame, text="Apply Cleanup", command=self.cleanup_apply_changes).pack(side=tk.LEFT, padx=(0, 5))

        # Progress frame
        c_progress_frame = ttk.LabelFrame(cleanup_frame, text="Progress", padding="10")
        c_progress_frame.grid(row=5, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        c_progress_frame.columnconfigure(0, weight=1)
        cleanup_frame.rowconfigure(3, weight=1)

        self.cleanup_progress_var = tk.StringVar(value="Ready")
        ttk.Label(c_progress_frame, textvariable=self.cleanup_progress_var).grid(row=0, column=0, sticky=tk.W)

        # Log frame
        c_log_frame = ttk.LabelFrame(cleanup_frame, text="Log", padding="10")
        c_log_frame.grid(row=3, column=1, rowspan=2, sticky=(tk.W, tk.E, tk.N, tk.S))
        c_log_frame.columnconfigure(0, weight=1)
        c_log_frame.rowconfigure(0, weight=1)
        cleanup_frame.rowconfigure(3, weight=1)

        self.cleanup_log_text = scrolledtext.ScrolledText(c_log_frame, height=10, wrap=tk.WORD, width=30)
        self.cleanup_log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # ========================= Duplicate File Finder Tab =========================
        duplicate_frame = ttk.Frame(notebook, padding="10")
        notebook.add(duplicate_frame, text="Duplicate File Finder")

        duplicate_frame.columnconfigure(0, weight=4)
        duplicate_frame.columnconfigure(1, weight=1)

        # Folder selection
        ttk.Label(duplicate_frame, text="Select Folder to Scan for Duplicates:").grid(row=0, column=0, sticky=tk.W, pady=(0, 5))
        d_folder_frame = ttk.Frame(duplicate_frame)
        d_folder_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        d_folder_frame.columnconfigure(0, weight=1)

        ttk.Entry(d_folder_frame, textvariable=self.duplicate_selected_folder, state="readonly").grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 5))
        ttk.Button(d_folder_frame, text="Browse", command=self.duplicate_browse_folder).grid(row=0, column=1)

        # Scan options frame
        d_scan_options_frame = ttk.LabelFrame(duplicate_frame, text="Scan Options", padding="10")
        d_scan_options_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        d_scan_options_frame.columnconfigure(0, weight=1)

        # File type filter
        self.duplicate_scan_all_files_var = tk.BooleanVar(value=True)
        ttk.Radiobutton(d_scan_options_frame, text="Scan all files", 
                       variable=self.duplicate_scan_all_files_var, value=True).grid(row=0, column=0, sticky=tk.W, pady=2)

        self.duplicate_scan_media_only_var = tk.BooleanVar(value=False)
        ttk.Radiobutton(d_scan_options_frame, text="Scan media files only (images, videos, audio)", 
                       variable=self.duplicate_scan_all_files_var, value=False).grid(row=1, column=0, sticky=tk.W, pady=2)

        # Include subfolders
        self.duplicate_include_subfolders_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(d_scan_options_frame, text="Include subfolders in scan", 
                       variable=self.duplicate_include_subfolders_var).grid(row=2, column=0, sticky=tk.W, pady=2)

        # Minimum file size
        d_min_size_frame = ttk.Frame(d_scan_options_frame)
        d_min_size_frame.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=2)
        d_min_size_frame.columnconfigure(1, weight=1)

        ttk.Label(d_min_size_frame, text="Minimum file size (KB):").grid(row=0, column=0, sticky=tk.W)
        self.duplicate_min_size_var = tk.StringVar(value="100")
        ttk.Entry(d_min_size_frame, textvariable=self.duplicate_min_size_var, width=10).grid(row=0, column=1, sticky=tk.W, padx=(10, 0))

        # Action options frame
        d_action_frame = ttk.LabelFrame(duplicate_frame, text="Duplicate Actions", padding="10")
        d_action_frame.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        d_action_frame.columnconfigure(0, weight=1)

        self.duplicate_action_var = tk.StringVar(value="flag")
        ttk.Radiobutton(d_action_frame, text="Flag duplicates only (preview mode)", 
                       variable=self.duplicate_action_var, value="flag").grid(row=0, column=0, sticky=tk.W, pady=2)
        ttk.Radiobutton(d_action_frame, text="Delete duplicates (keep first occurrence)", 
                       variable=self.duplicate_action_var, value="delete").grid(row=1, column=0, sticky=tk.W, pady=2)
        ttk.Radiobutton(d_action_frame, text="Move duplicates to subfolder", 
                       variable=self.duplicate_action_var, value="move").grid(row=2, column=0, sticky=tk.W, pady=2)

        # Hash algorithm selection
        d_hash_frame = ttk.Frame(d_action_frame)
        d_hash_frame.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=(10, 0))
        d_hash_frame.columnconfigure(1, weight=1)

        ttk.Label(d_hash_frame, text="Hash algorithm:").grid(row=0, column=0, sticky=tk.W)
        self.duplicate_hash_algorithm_var = tk.StringVar(value="sha256")
        hash_combo = ttk.Combobox(d_hash_frame, textvariable=self.duplicate_hash_algorithm_var, 
                                 values=["md5", "sha1", "sha256"], state="readonly", width=10)
        hash_combo.grid(row=0, column=1, sticky=tk.W, padx=(10, 0))

        # Buttons frame
        d_buttons_frame = ttk.Frame(duplicate_frame)
        d_buttons_frame.grid(row=4, column=0, sticky=(tk.W, tk.E), pady=(0, 10))

        ttk.Button(d_buttons_frame, text="Scan for Duplicates", command=self.duplicate_scan_files).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(d_buttons_frame, text="Apply Actions", command=self.duplicate_apply_actions).pack(side=tk.LEFT, padx=(0, 5))

        # Progress frame
        d_progress_frame = ttk.LabelFrame(duplicate_frame, text="Progress", padding="10")
        d_progress_frame.grid(row=5, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        d_progress_frame.columnconfigure(0, weight=1)

        self.duplicate_progress_var = tk.StringVar(value="Ready")
        ttk.Label(d_progress_frame, textvariable=self.duplicate_progress_var).grid(row=0, column=0, sticky=tk.W)

        # Results frame with treeview and preview
        d_results_frame = ttk.LabelFrame(duplicate_frame, text="Duplicate Groups", padding="10")
        d_results_frame.grid(row=2, column=1, rowspan=3, sticky=(tk.W, tk.E, tk.N, tk.S))
        d_results_frame.columnconfigure(0, weight=3)
        d_results_frame.columnconfigure(1, weight=2)
        d_results_frame.rowconfigure(0, weight=1)
        duplicate_frame.rowconfigure(2, weight=1)

        # Duplicate results treeview
        d_tree_frame = ttk.Frame(d_results_frame)
        d_tree_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 5))
        d_tree_frame.columnconfigure(0, weight=1)
        d_tree_frame.rowconfigure(0, weight=1)

        columns = ("File", "Size", "Location")
        self.duplicate_tree = ttk.Treeview(d_tree_frame, columns=columns, show='tree headings')
        for col, width in [("File", 100), ("Size", 40), ("Location", 100)]:
            self.duplicate_tree.heading(col, text=col)
            self.duplicate_tree.column(col, width=width, anchor=tk.W)
        self.duplicate_tree.heading('#0', text='Group')
        self.duplicate_tree.column('#0', width=50)

        self.duplicate_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        d_tree_scroll = ttk.Scrollbar(d_tree_frame, orient=tk.VERTICAL, command=self.duplicate_tree.yview)
        d_tree_scroll.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.duplicate_tree.configure(yscrollcommand=d_tree_scroll.set)
        
        # Bind selection event to update preview
        self.duplicate_tree.bind('<<TreeviewSelect>>', self.on_duplicate_tree_select)

        # Image preview frame
        d_preview_frame = ttk.LabelFrame(d_results_frame, text="File Preview", padding="10")
        d_preview_frame.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N, tk.S))
        d_preview_frame.columnconfigure(0, weight=1)
        d_preview_frame.rowconfigure(0, weight=1)

        # Preview canvas
        self.preview_canvas = tk.Canvas(d_preview_frame, width=150, height=150, bg='white')
        self.preview_canvas.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Preview info label
        self.preview_info_label = ttk.Label(d_preview_frame, text="Select a file to preview", 
                                          wraplength=140, justify=tk.CENTER)
        self.preview_info_label.grid(row=1, column=0, pady=(5, 0))

        # Log frame
        d_log_frame = ttk.LabelFrame(duplicate_frame, text="Log", padding="10")
        d_log_frame.grid(row=5, column=1, rowspan=1, sticky=(tk.W, tk.E, tk.N, tk.S))
        d_log_frame.columnconfigure(0, weight=1)
        d_log_frame.rowconfigure(0, weight=1)

        self.duplicate_log_text = scrolledtext.ScrolledText(d_log_frame, height=8, wrap=tk.WORD, width=25)
        self.duplicate_log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
    def on_duplicate_tree_select(self, event):
        """Handle tree selection to update image preview"""
        try:
            selection = self.duplicate_tree.selection()
            if not selection:
                self.clear_preview()
                return
            
            item = selection[0]
            # Get the file path from the selected item
            item_values = self.duplicate_tree.item(item, 'values')
            
            if len(item_values) >= 3:  # It's a file item (has File, Size, Location columns)
                # Clean up the file name by removing prefixes and suffixes
                raw_file_name = item_values[0]
                clean_file_name = raw_file_name.replace("📁 ", "").replace("🔄 ", "")
                clean_file_name = clean_file_name.replace(" (Original)", "").replace(" (Duplicate)", "")
                
                file_location = item_values[2]
                file_path = os.path.join(file_location, clean_file_name)
                self.update_preview(file_path)
            else:
                self.clear_preview()
                
        except Exception as e:
            self.duplicate_log_message(f"Error updating preview: {e}")
            self.clear_preview()
    
    def update_preview(self, file_path):
        """Update the preview canvas with the selected file"""
        try:
            if not os.path.exists(file_path):
                self.preview_info_label.config(text="File not found")
                self.preview_canvas.delete("all")
                return
            
            # Get file info
            file_size = os.path.getsize(file_path)
            file_size_mb = file_size / (1024 * 1024)
            file_name = os.path.basename(file_path)
            
            # Check if it's an image file
            image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp'}
            file_ext = os.path.splitext(file_path)[1].lower()
            
            if file_ext in image_extensions and Image:
                self.load_image_preview(file_path, file_name, file_size_mb)
            else:
                # Show file info for non-image files
                self.show_file_info(file_name, file_size_mb, file_ext)
                
        except Exception as e:
            self.duplicate_log_message(f"Error loading preview for {file_path}: {e}")
            self.preview_info_label.config(text="Preview error")
            self.preview_canvas.delete("all")
    
    def load_image_preview(self, file_path, file_name, file_size_mb):
        """Load and display image preview"""
        try:
            # Open and resize image
            with Image.open(file_path) as img:
                # Convert to RGB if necessary
                if img.mode in ('RGBA', 'LA', 'P'):
                    img = img.convert('RGB')
                
                # Calculate size to fit in canvas (150x150) - maximize usage
                canvas_width = 140  # Leave small margin
                canvas_height = 140
                img_width, img_height = img.size
                
                # Calculate scaling factor to fit within canvas while maintaining aspect ratio
                width_scale = canvas_width / img_width
                height_scale = canvas_height / img_height
                scale_factor = min(width_scale, height_scale)
                
                # Apply scaling
                new_width = int(img_width * scale_factor)
                new_height = int(img_height * scale_factor)
                
                # Resize image
                img_resized = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                
                # Convert to PhotoImage for tkinter
                from tkinter import PhotoImage
                import io
                
                # Save to bytes and reload as PhotoImage
                img_bytes = io.BytesIO()
                img_resized.save(img_bytes, format='PNG')
                img_bytes.seek(0)
                
                # Clear canvas and display image
                self.preview_canvas.delete("all")
                
                # Create PhotoImage from bytes
                photo = tk.PhotoImage(data=img_bytes.getvalue())
                
                # Store reference to prevent garbage collection
                self.preview_canvas.image = photo
                
                # Center image on canvas
                canvas_width = 150
                canvas_height = 150
                x = (canvas_width - new_width) // 2
                y = (canvas_height - new_height) // 2
                
                self.preview_canvas.create_image(x, y, anchor=tk.NW, image=photo)
                
                # Update info label
                dimensions = f"{img_width}x{img_height}"
                self.preview_info_label.config(
                    text=f"{file_name[:20]}{'...' if len(file_name) > 20 else ''}\n"
                         f"{dimensions}\n{file_size_mb:.1f} MB"
                )
                
        except Exception as e:
            self.duplicate_log_message(f"Error loading image {file_path}: {e}")
            self.show_file_info(file_name, file_size_mb, os.path.splitext(file_path)[1])
    
    def show_file_info(self, file_name, file_size_mb, file_ext):
        """Show file info for non-image files"""
        self.preview_canvas.delete("all")
        
        # Show file type icon or text
        file_type = file_ext.upper().replace('.', '') if file_ext else 'FILE'
        
        # Draw file type indicator
        self.preview_canvas.create_rectangle(25, 25, 125, 125, outline='gray', width=2)
        self.preview_canvas.create_text(75, 75, text=file_type, font=('Arial', 10, 'bold'))
        
        # Update info label
        self.preview_info_label.config(
            text=f"{file_name[:20]}{'...' if len(file_name) > 20 else ''}\n"
                 f"{file_type} file\n{file_size_mb:.1f} MB"
        )
    
    def clear_preview(self):
        """Clear the preview canvas and info"""
        self.preview_canvas.delete("all")
        self.preview_info_label.config(text="Select a file to preview")
        
    def browse_folder(self):
        folder = filedialog.askdirectory(title="Select Import Folder")
        if folder:
            self.selected_folder.set(folder)
            self.log_message(f"Selected folder: {folder}")
            self.populate_subfolders()
    
    def populate_subfolders(self):
        """Populate the subfolder listbox based on the selected folder"""
        self.subfolder_listbox.delete(0, tk.END)
        try:
            if not self.selected_folder.get():
                return
            folder_path = Path(self.selected_folder.get())
            if folder_path.exists():
                subfolders = [f.name for f in folder_path.iterdir() if f.is_dir()]
                for name in sorted(subfolders, key=str.lower):
                    self.subfolder_listbox.insert(tk.END, name)
        except Exception as e:
            self.log_message(f"Failed to list subfolders: {e}")
    
    def select_all_subfolders(self):
        """Select all items in the subfolder listbox"""
        try:
            self.subfolder_listbox.select_set(0, tk.END)
        except Exception:
            pass

    def _get_selected_subfolder_names(self):
        """Return a set of selected subfolder names, or None if none selected (meaning all)."""
        try:
            selection = self.subfolder_listbox.curselection()
            if not selection:
                return None
            return {self.subfolder_listbox.get(i) for i in selection}
        except Exception:
            return None
            
    def log_message(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
        self.root.update_idletasks()

    def media_log_message(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.media_log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.media_log_text.see(tk.END)
        self.root.update_idletasks()
        
    def clean_folder_name(self, folder_name):
        """Apply renaming rules to folder name"""
        cleaned = folder_name
        
        # Remove first X characters
        try:
            remove_first = int(self.remove_first_var.get())
            if remove_first > 0:
                cleaned = cleaned[remove_first:]
        except ValueError:
            pass

        # Remove last X characters
        try:
            remove_last = int(self.remove_last_var.get())
            if remove_last > 0:
                if remove_last >= len(cleaned):
                    cleaned = ''
                else:
                    cleaned = cleaned[:-remove_last]
        except ValueError:
            pass
            
        # Remove everything before character
        if self.before_char_var.get():
            char = self.before_char_var.get()
            if char in cleaned:
                cleaned = cleaned[cleaned.find(char) + len(char):]
                
        # Remove everything after character
        if self.after_char_var.get():
            char = self.after_char_var.get()
            if char in cleaned:
                cleaned = cleaned[:cleaned.find(char)]
                
        # Remove digits
        if self.remove_digits_var.get():
            cleaned = re.sub(r'\d+', '', cleaned)
            
        # Remove special characters
        if self.remove_special_var.get():
            cleaned = re.sub(r'[^\w\s-]', '', cleaned)
            
        # Replace underscores with spaces
        if self.replace_underscores_var.get():
            cleaned = cleaned.replace('_', ' ')
            
        # Title case
        if self.title_case_var.get():
            cleaned = cleaned.title()
            
        # Clean up extra spaces
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        
        return cleaned
        
    def find_video_audio_pairs(self, folder_path):
        """Find related video and audio files in a folder - DISABLED"""
        # Merging functionality disabled - return empty pairs
        return []
        
    def merge_video_audio(self, video_path, audio_path, output_path):
        """Merge video and audio files using FFmpeg"""
        try:
            cmd = [
                get_ffmpeg_path(), '-y',
                '-i', str(video_path),
                '-i', str(audio_path),
                '-c:v', 'copy',
                '-c:a', 'aac',
                '-map', '0:v:0',
                '-map', '1:a:0',
                str(output_path)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            if result.returncode == 0:
                # Remove original files
                video_path.unlink()
                audio_path.unlink()
                return True
            else:
                self.media_log_message(f"FFmpeg error: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            self.media_log_message("FFmpeg operation timed out")
            return False
        except Exception as e:
            self.media_log_message(f"Error merging files: {e}")
            return False

    
            
    def preview_changes(self):
        """Preview all changes without applying them"""
        if not self.selected_folder.get():
            messagebox.showerror("Error", "Please select a folder first")
            return
            
        self.log_message("=== PREVIEW MODE ===")
        folder_path = Path(self.selected_folder.get())
        
        if not folder_path.exists():
            messagebox.showerror("Error", "Selected folder does not exist")
            return
            
        selected_names = self._get_selected_subfolder_names()

        # Build preview using a tree view
        preview_items = []  # list of dict: {folder_path, old_name, final_folder_name, folder_will_change, file_changes: [(old, new)]}

        # Handle case where user wants to process the selected folder itself (no subfolders selected)
        folders_to_process = []
        
        if selected_names is None:
            # No subfolders selected - check if the selected folder has subfolders
            subfolders = [p for p in folder_path.iterdir() if p.is_dir()]
            if subfolders:
                # Has subfolders - process all subfolders
                folders_to_process = subfolders
            else:
                # No subfolders - process the selected folder itself
                folders_to_process = [folder_path]
        else:
            # Specific subfolders selected
            folders_to_process = [folder_path / name for name in selected_names if (folder_path / name).exists() and (folder_path / name).is_dir()]

        # Prepare folder rename simulation to reflect conflict handling and case-insensitive FS
        planned = []
        for p in folders_to_process:
            if p == folder_path:
                # Processing the selected folder itself - don't rename it, just process its files
                planned.append((p, p.name))
            else:
                # Processing subfolders - apply renaming rules
                planned.append((p, self.clean_folder_name(p.name)))
        
        # Order by original name length (longest first), matching processing
        planned.sort(key=lambda x: len(x[0].name), reverse=True)

        def norm_name(name: str) -> str:
            return os.path.normcase(name)

        occupied = {norm_name(p.name) for p in folders_to_process}

        folder_final_names = {}

        for folder, target_name in planned:
            old_name = folder.name
            old_norm = norm_name(old_name)
            target_norm = norm_name(target_name)
            final_name = target_name
            
            # Don't rename the root selected folder
            if folder == folder_path:
                final_name = old_name
            elif old_name != target_name:
                if target_norm in occupied:
                    if target_norm == old_norm:
                        # Same folder (case-only or similar) – allow
                        final_name = target_name
                    else:
                        counter = 1
                        while norm_name(f"{target_name} ({counter})") in occupied:
                            counter += 1
                        final_name = f"{target_name} ({counter})"
                # Update occupied names to reflect rename
                occupied.discard(old_norm)
                occupied.add(norm_name(final_name))
            else:
                # No change
                final_name = old_name
            folder_final_names[folder] = final_name

        for folder, final_name in folder_final_names.items():
            old_name = folder.name
            folder_will_change = (old_name != final_name)

            file_changes = []
            if self.rename_files_var.get():
                files = [f for f in folder.iterdir() if f.is_file()]
                files.sort()
                existing_names = {f.name for f in files}
                planned_names = set()
                for i, file_path in enumerate(files):
                    base = final_name if i == 0 else f"{final_name} {i + 1}"
                    file_ext = file_path.suffix
                    candidate = f"{base}{file_ext}"
                    new_name = candidate
                    if new_name != file_path.name:
                        # Check conflicts with existing and planned
                        if (new_name in existing_names) or (new_name in planned_names):
                            counter = 1
                            conflict_candidate = f"{base} ({counter}){file_ext}"
                            while (conflict_candidate in existing_names) or (conflict_candidate in planned_names):
                                counter += 1
                                conflict_candidate = f"{base} ({counter}){file_ext}"
                            new_name = conflict_candidate
                    planned_names.add(new_name)
                    if new_name != file_path.name:
                        file_changes.append((file_path.name, new_name))

            if folder_will_change or file_changes:
                preview_items.append({
                    'folder_path': folder,
                    'old_name': old_name,
                    'final_folder_name': final_name,
                    'folder_will_change': folder_will_change,
                    'file_changes': file_changes,
                })

        if preview_items:
            preview_window = tk.Toplevel(self.root)
            preview_window.title("Preview Changes")
            preview_window.geometry("750x450")

            columns = ("Type", "Old Name", "Arrow", "New Name", "Location")
            tree = ttk.Treeview(preview_window, columns=columns, show='headings')
            for col, width in [("Type", 80), ("Old Name", 220), ("Arrow", 30), ("New Name", 220), ("Location", 200)]:
                tree.heading(col, text=col)
                tree.column(col, width=width, anchor=tk.W)
            tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            for item in preview_items:
                folder = item['folder_path']
                parent = folder.parent if folder != folder_path else folder_path.parent
                folder_row_id = tree.insert('', tk.END, values=(
                    "Folder",
                    item['old_name'],
                    "→",
                    item['final_folder_name'],
                    str(parent)
                ))
                for old_f, new_f in item['file_changes']:
                    tree.insert(folder_row_id, tk.END, values=(
                        "File",
                        old_f,
                        "→",
                        new_f,
                        str(parent / item['final_folder_name']) if folder != folder_path else str(folder)
                    ))
                tree.item(folder_row_id, open=True)
        else:
            self.log_message("No changes would be made")
            
    def apply_changes(self):
        """Apply all changes to the selected folder"""
        if not self.selected_folder.get():
            messagebox.showerror("Error", "Please select a folder first")
            return
            
        response = messagebox.askyesno("Confirm", "Do you want to apply all changes? This action cannot be undone.")
        if not response:
            return
                
        # Start processing in background thread
        self.is_processing = True
        self.progress_var.set("Processing...")
        
        # Capture selected subfolders at the time of applying
        self._selected_names_at_apply = self._get_selected_subfolder_names()

        thread = threading.Thread(target=self._process_folder)
        thread.daemon = True
        thread.start()
        
    def _process_folder(self):
        """Process folder in background thread"""
        try:
            folder_path = Path(self.selected_folder.get())
            self.log_message("=== STARTING PROCESSING ===")
            
            # Determine which folders to process
            folders_to_process = []
            
            if self._selected_names_at_apply is None:
                # No subfolders selected - check if the selected folder has subfolders
                subfolders = [p for p in folder_path.iterdir() if p.is_dir()]
                if subfolders:
                    # Has subfolders - process all subfolders
                    folders_to_process = subfolders
                else:
                    # No subfolders - process the selected folder itself
                    folders_to_process = [folder_path]
            else:
                # Specific subfolders selected
                folders_to_process = [folder_path / name for name in self._selected_names_at_apply if (folder_path / name).exists() and (folder_path / name).is_dir()]
            
            # Step 1: Rename folders (but not the root selected folder)
            self.log_message("Step 1: Renaming folders...")
            folders_to_rename = []
            
            for item in folders_to_process:
                if item != folder_path:  # Don't rename the root selected folder
                    old_name = item.name
                    new_name = self.clean_folder_name(old_name)
                    
                    if old_name != new_name:
                        folders_to_rename.append((item, new_name))
                        
            # Sort by name length (longest first) to avoid conflicts
            folders_to_rename.sort(key=lambda x: len(x[0].name), reverse=True)
            
            for folder, new_name in folders_to_rename:
                try:
                    new_path = folder.parent / new_name
                    if new_path.exists():
                        # If the existing path is the same folder (case-only change on Windows), allow it
                        is_same = False
                        try:
                            is_same = new_path.samefile(folder)
                        except Exception:
                            # Fallback for Windows when samefile may fail
                            is_same = os.path.normcase(os.fspath(new_path)) == os.path.normcase(os.fspath(folder))
                        if not is_same:
                            # Handle conflicts by adding number
                            counter = 1
                            candidate = folder.parent / f"{new_name} ({counter})"
                            while candidate.exists():
                                counter += 1
                                candidate = folder.parent / f"{new_name} ({counter})"
                            new_path = candidate
                            
                    try:
                        folder.rename(new_path)
                    except OSError as e:
                        # Handle Windows case-change edge case by renaming via a temp name
                        if os.name == 'nt' and "already exists" in str(e).lower():
                            temp_path = folder.parent / f"{new_name}.__tmp_case__"
                            folder.rename(temp_path)
                            temp_path.rename(new_path)
                        else:
                            raise
                    self.log_message(f"Renamed folder: '{folder.name}' → '{new_path.name}'")
                except Exception as e:
                    self.log_message(f"Error renaming folder '{folder.name}': {e}")
                    
            # Step 2: Rename files
            self.log_message("Step 2: Processing files...")
            
            if self.rename_files_var.get():
                # Re-scan folders after renaming
                current_folders = []
                if self._selected_names_at_apply is None:
                    subfolders = [p for p in folder_path.iterdir() if p.is_dir()]
                    if subfolders:
                        current_folders = subfolders
                    else:
                        current_folders = [folder_path]
                else:
                    # After renaming, we need to find the renamed folders
                    current_folders = [p for p in folder_path.iterdir() if p.is_dir()]
                    if not current_folders and folder_path.exists():
                        current_folders = [folder_path]
                
                for item in current_folders:
                    self._process_folder_contents(item)

            self.log_message("=== PROCESSING COMPLETE ===")
            
        except Exception as e:
            self.log_message(f"Error during processing: {e}")
        finally:
            self.is_processing = False
            self.progress_var.set("Ready")
            # Refresh subfolders list to reflect any renames
            try:
                self.populate_subfolders()
            except Exception:
                pass

    def _process_folder_contents(self, folder_path):
        """Process contents of a single folder"""
        folder_name = folder_path.name
        
        # Rename files
        files = [f for f in folder_path.iterdir() if f.is_file()]
        files.sort()  # Sort for consistent numbering
        
        for i, file_path in enumerate(files):
            file_ext = file_path.suffix
            if i == 0:
                new_file_name = f"{folder_name}{file_ext}"
            else:
                new_file_name = f"{folder_name} {i + 1}{file_ext}"
                
            try:
                new_file_path = folder_path / new_file_name
                if new_file_path != file_path:
                    if new_file_path.exists():
                        # Handle conflicts
                        counter = 1
                        while new_file_path.exists():
                            if i == 0:
                                new_file_name = f"{folder_name} ({counter}){file_ext}"
                            else:
                                new_file_name = f"{folder_name} {i + 1} ({counter}){file_ext}"
                            new_file_path = folder_path / new_file_name
                            counter += 1
                            
                    file_path.rename(new_file_path)
                    self.log_message(f"Renamed file: '{file_path.name}' → '{new_file_name}'")
            except Exception as e:
                self.log_message(f"Error renaming file '{file_path.name}': {e}")
                
    def save_config(self):
        """Save current configuration to file"""
        config = {
            'remove_first': self.remove_first_var.get(),
            'remove_last': self.remove_last_var.get(),
            'before_char': self.before_char_var.get(),
            'after_char': self.after_char_var.get(),
            'remove_digits': self.remove_digits_var.get(),
            'remove_special': self.remove_special_var.get(),
            'replace_underscores': self.replace_underscores_var.get(),
            'title_case': self.title_case_var.get(),
            'rename_files': self.rename_files_var.get()
        }
        
        filename = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if filename:
            try:
                with open(filename, 'w') as f:
                    json.dump(config, f, indent=2)
                self.log_message(f"Configuration saved to: {filename}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save configuration: {e}")
                
    def load_config(self, filename=None):
        """Load configuration from file"""
        if filename is None:
            filename = "config.json"
            
        try:
            if os.path.exists(filename):
                with open(filename, 'r') as f:
                    config = json.load(f)
                    
                self.remove_first_var.set(config.get('remove_first', '0'))
                self.remove_last_var.set(config.get('remove_last', '0'))
                self.before_char_var.set(config.get('before_char', ''))
                self.after_char_var.set(config.get('after_char', ''))
                self.remove_digits_var.set(config.get('remove_digits', False))
                self.remove_special_var.set(config.get('remove_special', False))
                self.replace_underscores_var.set(config.get('replace_underscores', True))
                self.title_case_var.set(config.get('title_case', True))
                self.rename_files_var.set(config.get('rename_files', True))
                
                self.log_message(f"Configuration loaded from: {filename}")
        except Exception as e:
            self.log_message(f"Failed to load configuration: {e}")
            
    def load_config_dialog(self):
        """Load configuration from file dialog"""
        filename = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if filename:
            self.load_config(filename)

    # ========================= Media Merger Tab Logic =========================
    def merger_browse_folder(self):
        folder = filedialog.askdirectory(title="Select Import Folder")
        if folder:
            self.merger_selected_folder.set(folder)
            self.media_log_message(f"Selected folder: {folder}")
            self.merger_populate_subfolders()

    def merger_populate_subfolders(self):
        self.merger_subfolder_listbox.delete(0, tk.END)
        try:
            if not self.merger_selected_folder.get():
                return
            folder_path = Path(self.merger_selected_folder.get())
            if folder_path.exists():
                subfolders = [f.name for f in folder_path.iterdir() if f.is_dir()]
                for name in sorted(subfolders, key=str.lower):
                    self.merger_subfolder_listbox.insert(tk.END, name)
        except Exception as e:
            self.media_log_message(f"Failed to list subfolders: {e}")

    def merger_select_all_subfolders(self):
        try:
            self.merger_subfolder_listbox.select_set(0, tk.END)
        except Exception:
            pass

    def _merger_get_selected_subfolder_names(self):
        try:
            selection = self.merger_subfolder_listbox.curselection()
            if not selection:
                return None
            return {self.merger_subfolder_listbox.get(i) for i in selection}
        except Exception:
            return None

    def media_find_video_audio_pairs(self, folder_path: Path):
        """Return list of (video_path, audio_path, output_path) pairs for a folder.
        Rules:
        - Handle split .mp4 files (files ending with ' 2' that pair with base name)
        - Prefer files with matching stem names across video/audio sets
        - If exactly one video and one audio exist, pair them
        - Output name based on video stem with video extension; ensure no conflict by suffixing (n)
        """
        try:
            files = [f for f in folder_path.iterdir() if f.is_file()]
            videos = [f for f in files if f.suffix.lower() in self.video_extensions]
            audios = [f for f in files if f.suffix.lower() in self.audio_extensions]

            pairs = []
            used_videos = set()
            used_audio = set()

            # First, handle split .mp4 files (files ending with ' 2')
            mp4_files = [f for f in files if f.suffix.lower() == ".mp4"]
            split_mp4_pairs = {}
            
            for f in mp4_files:
                name_no_ext = f.stem
                if name_no_ext.endswith(" 2"):
                    base = name_no_ext[:-2]
                    split_mp4_pairs.setdefault(base, {})['second'] = f
                else:
                    split_mp4_pairs.setdefault(name_no_ext, {})['first'] = f

            # Process split .mp4 pairs
            for base, parts in split_mp4_pairs.items():
                first = parts.get('first')
                second = parts.get('second')
                if first and second:
                    output = folder_path / f"{base}.mp4"
                    if output.exists():
                        counter = 1
                        candidate = folder_path / f"{base} ({counter}).mp4"
                        while candidate.exists():
                            counter += 1
                            candidate = folder_path / f"{base} ({counter}).mp4"
                        output = candidate
                    pairs.append((first, second, output))
                    used_videos.add(first)
                    used_videos.add(second)

            # Then handle regular video/audio pairs
            audio_by_stem = {}
            for a in audios:
                audio_by_stem.setdefault(a.stem, []).append(a)

            for v in videos:
                if v in used_videos:
                    continue  # Skip if already used in split mp4 pairs
                    
                candidates = audio_by_stem.get(v.stem, [])
                if candidates:
                    a = candidates[0]
                    if a not in used_audio:
                        used_audio.add(a)
                        output = folder_path / f"{v.stem}{v.suffix}"
                        if output.exists():
                            counter = 1
                            candidate = folder_path / f"{v.stem} ({counter}){v.suffix}"
                            while candidate.exists():
                                counter += 1
                                candidate = folder_path / f"{v.stem} ({counter}){v.suffix}"
                            output = candidate
                        pairs.append((v, a, output))
                        used_videos.add(v)

            # If none matched by stem and there is exactly one video and one audio left
            remaining_videos = [v for v in videos if v not in used_videos]
            remaining_audios = [a for a in audios if a not in used_audio]
            if len(remaining_videos) == 1 and len(remaining_audios) == 1:
                v = remaining_videos[0]
                a = remaining_audios[0]
                output = folder_path / f"{v.stem}{v.suffix}"
                if output.exists():
                    counter = 1
                    candidate = folder_path / f"{v.stem} ({counter}){v.suffix}"
                    while candidate.exists():
                        counter += 1
                        candidate = folder_path / f"{v.stem} ({counter}){v.suffix}"
                    output = candidate
                pairs.append((v, a, output))

            return pairs
        except Exception as e:
            self.media_log_message(f"Error finding media pairs in '{folder_path}': {e}")
            return []

    def media_preview_changes(self):
        if not self.merger_selected_folder.get():
            messagebox.showerror("Error", "Please select a folder first")
            return

        root_folder = Path(self.merger_selected_folder.get())
        if not root_folder.exists():
            messagebox.showerror("Error", "Selected folder does not exist")
            return

        selected = self._merger_get_selected_subfolder_names()

        preview_items = []  # list of dict: {folder, file_renames, pairs}
        
        # Determine which folders to process
        folders_to_process = []
        
        if selected is None:
            # No subfolders selected - check if the selected folder has subfolders
            subfolders = [item for item in root_folder.iterdir() if item.is_dir()]
            if subfolders:
                # Has subfolders - process all subfolders
                folders_to_process = subfolders
            else:
                # No subfolders - process the selected folder itself
                folders_to_process = [root_folder]
        else:
            # Specific subfolders selected
            folders_to_process = [root_folder / name for name in selected if (root_folder / name).exists() and (root_folder / name).is_dir()]
        
        for item in folders_to_process:            
            # Preview file renames that will happen first
            file_renames = []
            files = [f for f in item.iterdir() if f.is_file()]
            files.sort()
            folder_name = item.name
            
            for i, file_path in enumerate(files):
                file_ext = file_path.suffix
                if i == 0:
                    new_file_name = f"{folder_name}{file_ext}"
                else:
                    new_file_name = f"{folder_name} {i + 1}{file_ext}"
                
                if new_file_name != file_path.name:
                    # Check for conflicts and adjust name if needed
                    new_file_path = item / new_file_name
                    if new_file_path.exists() and new_file_path != file_path:
                        counter = 1
                        while new_file_path.exists():
                            if i == 0:
                                new_file_name = f"{folder_name} ({counter}){file_ext}"
                            else:
                                new_file_name = f"{folder_name} {i + 1} ({counter}){file_ext}"
                            new_file_path = item / new_file_name
                            counter += 1
                    file_renames.append((file_path.name, new_file_name))
            
            # Preview merges that will happen after renaming
            # Note: We can't accurately preview pairs after renaming without actually renaming,
            # so we'll show the current pairs and note that files will be renamed first
            pairs = self.media_find_video_audio_pairs(item)
            
            if file_renames or pairs:
                preview_items.append({
                    'folder': item,
                    'file_renames': file_renames,
                    'pairs': pairs,
                })

        if not preview_items:
            self.media_log_message("No changes would be made")
            return

        preview_window = tk.Toplevel(self.root)
        preview_window.title("Preview Media Processing")
        preview_window.geometry("800x500")

        # Add note about the process
        note_frame = ttk.Frame(preview_window)
        note_frame.pack(fill=tk.X, padx=10, pady=5)
        note_label = ttk.Label(note_frame, text="Note: Files will be renamed first, then media pairs will be identified and merged.", 
                              font=('TkDefaultFont', 9, 'italic'))
        note_label.pack()

        columns = ("Type", "Source", "Arrow", "Output", "Location")
        tree = ttk.Treeview(preview_window, columns=columns, show='headings')
        for col, width in [("Type", 80), ("Source", 420), ("Arrow", 30), ("Output", 170), ("Location", 200)]:
            tree.heading(col, text=col)
            tree.column(col, width=width, anchor=tk.W)
        tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        for item in preview_items:
            folder = item['folder']
            parent = folder.parent if folder != root_folder else root_folder.parent
            folder_row_id = tree.insert('', tk.END, values=(
                "Folder",
                folder.name,
                "",
                "",
                str(parent)
            ))
            
            # Show file renames
            for old_name, new_name in item['file_renames']:
                tree.insert(folder_row_id, tk.END, values=(
                    "Rename",
                    old_name,
                    "→",
                    new_name,
                    str(folder)
                ))
            
            # Show merges (note: these are based on current file names, actual merges will use renamed files)
            for v, a, outp in item['pairs']:
                src = f"{v.name} + {a.name}"
                tree.insert(folder_row_id, tk.END, values=(
                    "Merge",
                    src,
                    "→",
                    outp.name,
                    str(folder)
                ))
            tree.item(folder_row_id, open=True)

    def media_apply_changes(self):
        if not self.merger_selected_folder.get():
            messagebox.showerror("Error", "Please select a folder first")
            return

        if self.media_is_processing:
            messagebox.showinfo("Info", "Media merging is already in progress")
            return

        response = messagebox.askyesno("Confirm", "Apply media merges to selected subfolders?")
        if not response:
            return

        self.media_is_processing = True
        self.media_progress_var.set("Processing...")
        self._merger_selected_at_apply = self._merger_get_selected_subfolder_names()

        thread = threading.Thread(target=self._media_process_folder)
        thread.daemon = True
        thread.start()

    def _media_rename_files_in_folder(self, folder_path):
        """Rename files in a folder to follow folder naming convention before merging"""
        folder_name = folder_path.name
        
        # Get all files and sort for consistent numbering
        files = [f for f in folder_path.iterdir() if f.is_file()]
        files.sort()  # Sort for consistent numbering
        
        for i, file_path in enumerate(files):
            file_ext = file_path.suffix
            if i == 0:
                new_file_name = f"{folder_name}{file_ext}"
            else:
                new_file_name = f"{folder_name} {i + 1}{file_ext}"
                
            try:
                new_file_path = folder_path / new_file_name
                if new_file_path != file_path:
                    if new_file_path.exists():
                        # Handle conflicts
                        counter = 1
                        while new_file_path.exists():
                            if i == 0:
                                new_file_name = f"{folder_name} ({counter}){file_ext}"
                            else:
                                new_file_name = f"{folder_name} {i + 1} ({counter}){file_ext}"
                            new_file_path = folder_path / new_file_name
                            counter += 1
                            
                    file_path.rename(new_file_path)
                    self.media_log_message(f"Renamed file: '{file_path.name}' → '{new_file_name}'")
            except Exception as e:
                self.media_log_message(f"Error renaming file '{file_path.name}': {e}")

    def _media_process_folder(self):
        try:
            root_folder = Path(self.merger_selected_folder.get())
            self.media_log_message("=== STARTING MEDIA MERGE ===")
            
            # Determine which folders to process
            folders_to_process = []
            
            if self._merger_selected_at_apply is None:
                # No subfolders selected - check if the selected folder has subfolders
                subfolders = [item for item in root_folder.iterdir() if item.is_dir()]
                if subfolders:
                    # Has subfolders - process all subfolders
                    folders_to_process = subfolders
                else:
                    # No subfolders - process the selected folder itself
                    folders_to_process = [root_folder]
            else:
                # Specific subfolders selected
                folders_to_process = [root_folder / name for name in self._merger_selected_at_apply if (root_folder / name).exists() and (root_folder / name).is_dir()]
            
            for item in folders_to_process:
                # Step 1: Rename files to follow folder naming convention
                self.media_log_message(f"Renaming files in '{item.name}'...")
                self._media_rename_files_in_folder(item)
                
                # Step 2: Find pairs and merge after renaming
                self.media_log_message(f"Finding media pairs in '{item.name}'...")
                pairs = self.media_find_video_audio_pairs(item)
                
                if pairs:
                    self.media_log_message(f"Found {len(pairs)} pair(s) to merge in '{item.name}'")
                    for v, a, outp in pairs:
                        try:
                            ok = self.merge_video_audio(v, a, outp)
                            if ok:
                                self.media_log_message(f"Merged into '{outp.name}' in '{item.name}'")
                            else:
                                self.media_log_message(f"Failed to merge '{v.name}' and '{a.name}' in '{item.name}'")
                        except Exception as e:
                            self.media_log_message(f"Error merging in '{item.name}': {e}")
                else:
                    self.media_log_message(f"No media pairs found in '{item.name}'")

            self.media_log_message("=== MEDIA MERGE COMPLETE ===")
        except Exception as e:
            self.media_log_message(f"Error during media merge: {e}")
        finally:
            self.media_is_processing = False
            self.media_progress_var.set("Ready")
            try:
                self.merger_populate_subfolders()
            except Exception:
                pass

    # ========================= File Sorter Tab Logic =========================
    def sorter_browse_folder(self):
        folder = filedialog.askdirectory(title="Select Source Folder")
        if folder:
            self.sorter_selected_folder.set(folder)
            self.sorter_log_message(f"Selected source folder: {folder}")

    def sorter_browse_export_folder(self):
        folder = filedialog.askdirectory(title="Select Export Folder")
        if folder:
            self.sorter_export_folder.set(folder)
            self.sorter_log_message(f"Selected export folder: {folder}")

    def sorter_log_message(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.sorter_log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.sorter_log_text.see(tk.END)
        self.root.update_idletasks()

    def _get_file_category(self, file_path: Path):
        """Determine the category folder name for a file"""
        extension = file_path.suffix.lower()
        
        if not extension:
            return "no_extension"
        
        # Handle image separation
        if self.separate_images_var.get():
            image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.tif', '.webp', '.svg', '.ico'}
            if extension in image_extensions:
                return extension[1:]  # Remove the dot
        
        # Group common image formats if not separating
        if not self.separate_images_var.get():
            image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.tif', '.webp', '.svg', '.ico'}
            if extension in image_extensions:
                return "images"
        
        # Return extension without the dot for other files
        return extension[1:]

    def _analyze_files_for_sorting(self, source_folder: Path):
        """Analyze files and return sorting plan"""
        sorting_plan = {}  # category -> list of files
        
        try:
            files = [f for f in source_folder.iterdir() if f.is_file()]
            
            for file_path in files:
                # Check if we should process this file
                if self.sort_mode_var.get() == "specific":
                    target_ext = self.specific_extension_var.get().lower()
                    if not target_ext.startswith('.'):
                        target_ext = '.' + target_ext
                    if file_path.suffix.lower() != target_ext:
                        continue
                
                category = self._get_file_category(file_path)
                if category not in sorting_plan:
                    sorting_plan[category] = []
                sorting_plan[category].append(file_path)
            
            return sorting_plan
        except Exception as e:
            self.sorter_log_message(f"Error analyzing files: {e}")
            return {}

    def sorter_preview_changes(self):
        if not self.sorter_selected_folder.get():
            messagebox.showerror("Error", "Please select a source folder first")
            return
        
        if self.output_mode_var.get() == "export" and not self.sorter_export_folder.get():
            messagebox.showerror("Error", "Please select an export folder")
            return

        source_folder = Path(self.sorter_selected_folder.get())
        if not source_folder.exists():
            messagebox.showerror("Error", "Source folder does not exist")
            return

        self.sorter_log_message("=== PREVIEW MODE ===")
        sorting_plan = self._analyze_files_for_sorting(source_folder)

        if not sorting_plan:
            self.sorter_log_message("No files found to sort")
            return

        preview_window = tk.Toplevel(self.root)
        preview_window.title("Preview File Sorting")
        preview_window.geometry("800x500")

        # Add info about the operation
        info_frame = ttk.Frame(preview_window)
        info_frame.pack(fill=tk.X, padx=10, pady=5)
        
        mode_text = "All file types" if self.sort_mode_var.get() == "all" else f"Only {self.specific_extension_var.get()} files"
        
        if self.output_mode_var.get() == "in_place":
            output_text = "In source directory (move)"
        else:
            operation_text = "copy" if self.export_operation_var.get() == "copy" else "move"
            output_text = f"Export to: {self.sorter_export_folder.get()} ({operation_text})"
        
        image_text = "Images separated by type" if self.separate_images_var.get() else "Images grouped together"
        
        info_text = f"Mode: {mode_text} | Output: {output_text} | {image_text}"
        ttk.Label(info_frame, text=info_text, font=('TkDefaultFont', 9, 'italic')).pack()

        columns = ("Category", "File Count", "Files", "Destination")
        tree = ttk.Treeview(preview_window, columns=columns, show='headings')
        for col, width in [("Category", 100), ("File Count", 80), ("Files", 400), ("Destination", 200)]:
            tree.heading(col, text=col)
            tree.column(col, width=width, anchor=tk.W)
        tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Determine destination base
        if self.output_mode_var.get() == "in_place":
            dest_base = source_folder
        else:
            dest_base = Path(self.sorter_export_folder.get())

        for category, files in sorted(sorting_plan.items()):
            files_text = ", ".join([f.name for f in files[:3]])  # Show first 3 files
            if len(files) > 3:
                files_text += f", ... and {len(files) - 3} more"
            
            dest_folder = dest_base / category
            tree.insert('', tk.END, values=(
                category,
                len(files),
                files_text,
                str(dest_folder)
            ))

        total_files = sum(len(files) for files in sorting_plan.values())
        self.sorter_log_message(f"Preview: {total_files} files in {len(sorting_plan)} categories")

    def sorter_apply_changes(self):
        if not self.sorter_selected_folder.get():
            messagebox.showerror("Error", "Please select a source folder first")
            return
        
        if self.output_mode_var.get() == "export" and not self.sorter_export_folder.get():
            messagebox.showerror("Error", "Please select an export folder")
            return

        if self.sorter_is_processing:
            messagebox.showinfo("Info", "File sorting is already in progress")
            return

        # Create confirmation message based on operation
        if self.output_mode_var.get() == "in_place":
            confirm_msg = "Apply file sorting? This will move files into categorized folders within the source directory."
        else:
            if self.export_operation_var.get() == "copy":
                confirm_msg = "Apply file sorting? This will copy files to categorized folders in the export directory (originals will remain)."
            else:
                confirm_msg = "Apply file sorting? This will move files to categorized folders in the export directory (originals will be removed)."
        
        response = messagebox.askyesno("Confirm", confirm_msg)
        if not response:
            return

        self.sorter_is_processing = True
        self.sorter_progress_var.set("Processing...")

        thread = threading.Thread(target=self._sorter_process_files)
        thread.daemon = True
        thread.start()

    def _sorter_process_files(self):
        try:
            source_folder = Path(self.sorter_selected_folder.get())
            self.sorter_log_message("=== STARTING FILE SORTING ===")
            
            sorting_plan = self._analyze_files_for_sorting(source_folder)
            
            if not sorting_plan:
                self.sorter_log_message("No files found to sort")
                return

            # Determine destination base and operation
            if self.output_mode_var.get() == "in_place":
                dest_base = source_folder
                operation = "move"
            else:
                dest_base = Path(self.sorter_export_folder.get())
                operation = self.export_operation_var.get()  # "copy" or "move" based on user choice

            total_files = sum(len(files) for files in sorting_plan.values())
            processed_files = 0

            for category, files in sorting_plan.items():
                # Create category folder
                category_folder = dest_base / category
                try:
                    category_folder.mkdir(parents=True, exist_ok=True)
                    self.sorter_log_message(f"Created category folder: {category}")
                except Exception as e:
                    self.sorter_log_message(f"Error creating folder '{category}': {e}")
                    continue

                # Move/copy files
                for file_path in files:
                    try:
                        dest_file = category_folder / file_path.name
                        
                        # Handle name conflicts
                        if dest_file.exists():
                            counter = 1
                            name_part = file_path.stem
                            ext_part = file_path.suffix
                            while dest_file.exists():
                                new_name = f"{name_part} ({counter}){ext_part}"
                                dest_file = category_folder / new_name
                                counter += 1

                        if operation == "move":
                            file_path.rename(dest_file)
                            self.sorter_log_message(f"Moved: {file_path.name} → {category}/{dest_file.name}")
                        else:  # copy
                            import shutil
                            shutil.copy2(file_path, dest_file)
                            self.sorter_log_message(f"Copied: {file_path.name} → {category}/{dest_file.name}")
                        
                        processed_files += 1
                        
                    except Exception as e:
                        self.sorter_log_message(f"Error processing '{file_path.name}': {e}")

            self.sorter_log_message(f"=== SORTING COMPLETE: {processed_files}/{total_files} files processed ===")
            
        except Exception as e:
            self.sorter_log_message(f"Error during file sorting: {e}")
        finally:
            self.sorter_is_processing = False
            self.sorter_progress_var.set("Ready")

    # ========================= Folder Cleanup Tab Logic =========================
    def cleanup_browse_folder(self):
        folder = filedialog.askdirectory(title="Select Folder to Clean")
        if folder:
            self.cleanup_selected_folder.set(folder)
            self.cleanup_log_message(f"Selected folder: {folder}")
            self.cleanup_populate_subfolders()

    def cleanup_populate_subfolders(self):
        """Populate the cleanup subfolder listbox"""
        self.cleanup_subfolder_listbox.delete(0, tk.END)
        try:
            if not self.cleanup_selected_folder.get():
                return
            folder_path = Path(self.cleanup_selected_folder.get())
            if folder_path.exists():
                subfolders = [f.name for f in folder_path.iterdir() if f.is_dir()]
                for name in sorted(subfolders, key=str.lower):
                    self.cleanup_subfolder_listbox.insert(tk.END, name)
        except Exception as e:
            self.cleanup_log_message(f"Failed to list subfolders: {e}")

    def cleanup_select_all_subfolders(self):
        try:
            self.cleanup_subfolder_listbox.select_set(0, tk.END)
        except Exception:
            pass

    def _cleanup_get_selected_subfolder_names(self):
        """Return a set of selected subfolder names, or None if none selected (meaning all)."""
        try:
            selection = self.cleanup_subfolder_listbox.curselection()
            if not selection:
                return None
            return {self.cleanup_subfolder_listbox.get(i) for i in selection}
        except Exception:
            return None

    def cleanup_log_message(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.cleanup_log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.cleanup_log_text.see(tk.END)
        self.root.update_idletasks()

    def cleanup_preview_changes(self):
        """Preview all cleanup changes without applying them"""
        if not self.cleanup_selected_folder.get():
            messagebox.showerror("Error", "Please select a folder first")
            return

        self.cleanup_log_message("=== PREVIEW MODE ===")
        folder_path = Path(self.cleanup_selected_folder.get())
        
        if not folder_path.exists():
            messagebox.showerror("Error", "Selected folder does not exist")
            return

        selected_names = self._cleanup_get_selected_subfolder_names()
        
        # Determine which folders to process
        folders_to_process = []
        
        if selected_names is None:
            # No subfolders selected - check if the selected folder has subfolders
            subfolders = [p for p in folder_path.iterdir() if p.is_dir()]
            if subfolders:
                # Has subfolders - process all subfolders
                folders_to_process = subfolders
            else:
                # No subfolders - process the selected folder itself
                folders_to_process = [folder_path]
        else:
            # Specific subfolders selected
            folders_to_process = [folder_path / name for name in selected_names if (folder_path / name).exists() and (folder_path / name).is_dir()]

        preview_items = self._analyze_cleanup_changes(folders_to_process)
        
        if not preview_items:
            self.cleanup_log_message("No changes would be made")
            return

        # Create preview window
        preview_window = tk.Toplevel(self.root)
        preview_window.title("Preview Cleanup Changes")
        preview_window.geometry("900x600")

        columns = ("Action", "Item", "Details", "Location")
        tree = ttk.Treeview(preview_window, columns=columns, show='headings')
        for col, width in [("Action", 120), ("Item", 300), ("Details", 280), ("Location", 200)]:
            tree.heading(col, text=col)
            tree.column(col, width=width, anchor=tk.W)
        tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        for action, items in preview_items.items():
            action_node = tree.insert('', tk.END, values=(action, f"{len(items)} items", "", ""))
            for item_path, details in items:
                tree.insert(action_node, tk.END, values=("", item_path.name, details, str(item_path.parent)))
            tree.item(action_node, open=True)

    def cleanup_apply_changes(self):
        """Apply all cleanup changes"""
        if not self.cleanup_selected_folder.get():
            messagebox.showerror("Error", "Please select a folder first")
            return

        if self.cleanup_is_processing:
            messagebox.showinfo("Info", "Cleanup is already in progress")
            return

        # Check if any cleanup options are selected
        if not any([
            self.flatten_folders_var.get(),
            self.remove_broken_media_var.get(),
            self.remove_no_thumbnail_videos_var.get(),
            self.remove_temp_files_var.get(),
            self.remove_custom_extensions_var.get()
        ]):
            messagebox.showwarning("Warning", "Please select at least one cleanup option")
            return

        response = messagebox.askyesno("Confirm", "Apply cleanup changes? This action cannot be undone.")
        if not response:
            return

        self.cleanup_is_processing = True
        self.cleanup_progress_var.set("Processing...")
        self._cleanup_selected_at_apply = self._cleanup_get_selected_subfolder_names()

        thread = threading.Thread(target=self._cleanup_process_folder)
        thread.daemon = True
        thread.start()

    def _analyze_cleanup_changes(self, folders_to_process):
        """Analyze what changes would be made during cleanup"""
        preview_items = {
            "Flatten Files": [],
            "Remove Empty Folders": [],
            "Remove Broken Media": [],
            "Remove No-Thumbnail Videos": [],
            "Remove Temp Files": [],
            "Remove Custom Extensions": []
        }

        for folder in folders_to_process:
            try:
                # Analyze flatten folders
                if self.flatten_folders_var.get():
                    if self._cleanup_selected_at_apply is not None:
                        # Specific subfolders selected - analyze flattening the selected folders themselves
                        all_items = list(folder.iterdir())
                        files = [item for item in all_items if item.is_file()]
                        subdirs = [item for item in all_items if item.is_dir()]
                        
                        # Show files that will be moved
                        preview_items["Flatten Files"].extend([(f, f"Move to parent folder") for f in files])
                        # Show subdirectories that will be moved
                        preview_items["Flatten Files"].extend([(d, f"Move to parent folder") for d in subdirs])
                        # Show that the selected folder will be removed if it becomes empty
                        if all_items:  # Only if there are items to move
                            preview_items["Remove Empty Folders"].append((folder, f"Remove after flattening"))
                    else:
                        # No specific selection - analyze flattening subfolders within the folder
                        flat_folders = self._find_flat_folders(folder)
                        for flat_folder in flat_folders:
                            files = [f for f in flat_folder.iterdir() if f.is_file()]
                            preview_items["Flatten Files"].extend([(f, f"Move to {folder.name}") for f in files])
                            # Also show that the empty folder will be removed
                            if files:  # Only if there are files to move
                                preview_items["Remove Empty Folders"].append((flat_folder, f"Remove after flattening"))

                # Analyze broken media files
                if self.remove_broken_media_var.get():
                    broken_media = self._find_broken_media_files(folder)
                    preview_items["Remove Broken Media"].extend([(f, "0 bytes or corrupted") for f in broken_media])

                # Analyze no-thumbnail videos
                if self.remove_no_thumbnail_videos_var.get():
                    no_thumbnail_videos = self._find_no_thumbnail_videos(folder)
                    preview_items["Remove No-Thumbnail Videos"].extend([(f, "Cannot generate thumbnail") for f in no_thumbnail_videos])

                # Analyze temp files
                if self.remove_temp_files_var.get():
                    temp_files = self._find_temp_files(folder)
                    preview_items["Remove Temp Files"].extend([(f, "Temporary/cache file") for f in temp_files])

                # Analyze custom extensions
                if self.remove_custom_extensions_var.get():
                    custom_files = self._find_custom_extension_files(folder)
                    preview_items["Remove Custom Extensions"].extend([(f, "Custom extension") for f in custom_files])

                # Analyze empty folders (separate from flattening)
                if self.remove_empty_folders_var.get():
                    empty_folders = self._find_empty_folders(folder)
                    preview_items["Remove Empty Folders"].extend([(f, "Empty folder") for f in empty_folders])

            except Exception as e:
                self.cleanup_log_message(f"Error analyzing folder '{folder}': {e}")

        # Remove empty categories
        return {k: v for k, v in preview_items.items() if v}

    def _cleanup_process_folder(self):
        """Process folder cleanup in background thread"""
        try:
            folder_path = Path(self.cleanup_selected_folder.get())
            self.cleanup_log_message("=== STARTING CLEANUP ===")
            
            # Determine which folders to process
            folders_to_process = []
            
            if self._cleanup_selected_at_apply is None:
                # No subfolders selected - check if the selected folder has subfolders
                subfolders = [p for p in folder_path.iterdir() if p.is_dir()]
                if subfolders:
                    # Has subfolders - process all subfolders
                    folders_to_process = subfolders
                else:
                    # No subfolders - process the selected folder itself
                    folders_to_process = [folder_path]
            else:
                # Specific subfolders selected
                folders_to_process = [folder_path / name for name in self._cleanup_selected_at_apply if (folder_path / name).exists() and (folder_path / name).is_dir()]

            for folder in folders_to_process:
                self.cleanup_log_message(f"Processing folder: {folder.name}")
                
                # Step 1: Flatten folders
                if self.flatten_folders_var.get():
                    if self._cleanup_selected_at_apply is not None:
                        # Specific subfolders selected - flatten the selected folders themselves
                        self._flatten_selected_folder(folder, folder_path)
                    else:
                        # No specific selection - flatten subfolders within the folder
                        self._flatten_folders_in_path(folder)
                
                # Step 2: Remove broken media files
                if self.remove_broken_media_var.get():
                    self._remove_broken_media_files(folder)
                
                # Step 3: Remove no-thumbnail videos
                if self.remove_no_thumbnail_videos_var.get():
                    self._remove_no_thumbnail_videos(folder)
                
                # Step 4: Remove temp files
                if self.remove_temp_files_var.get():
                    self._remove_temp_files(folder)
                
                # Step 5: Remove custom extension files
                if self.remove_custom_extensions_var.get():
                    self._remove_custom_extension_files(folder)
                
                # Step 6: Remove empty folders (after all other operations)
                if self.remove_empty_folders_var.get():
                    self._remove_empty_folders(folder)

            self.cleanup_log_message("=== CLEANUP COMPLETE ===")
            
        except Exception as e:
            self.cleanup_log_message(f"Error during cleanup: {e}")
        finally:
            self.cleanup_is_processing = False
            self.cleanup_progress_var.set("Ready")
            try:
                self.cleanup_populate_subfolders()
            except Exception:
                pass

    # ========================= Cleanup Helper Methods =========================
    def _find_flat_folders(self, parent_folder):
        """Find folders that contain only files (no subfolders)"""
        flat_folders = []
        try:
            for item in parent_folder.iterdir():
                if item.is_dir():
                    # Check if this folder contains only files (no subdirectories)
                    contents = list(item.iterdir())
                    if contents and all(f.is_file() for f in contents):
                        flat_folders.append(item)
        except Exception as e:
            self.cleanup_log_message(f"Error finding flat folders in '{parent_folder}': {e}")
        return flat_folders

    def _find_broken_media_files(self, folder):
        """Find broken or empty media files"""
        broken_files = []
        media_extensions = {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v',
                           '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.tif', '.webp', '.svg', '.ico'}
        
        try:
            for item in folder.rglob('*'):
                if item.is_file() and item.suffix.lower() in media_extensions:
                    # Check if file is 0 bytes
                    if item.stat().st_size == 0:
                        broken_files.append(item)
                        continue
                    
                    # Check video files with ffprobe
                    if item.suffix.lower() in {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v'}:
                        if self._is_broken_video(item):
                            broken_files.append(item)
                    
                    # Check image files
                    elif item.suffix.lower() in {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.tif', '.webp'}:
                        if self._is_broken_image(item):
                            broken_files.append(item)
                            
        except Exception as e:
            self.cleanup_log_message(f"Error finding broken media files in '{folder}': {e}")
        
        return broken_files

    def _find_no_thumbnail_videos(self, folder):
        """Find .mp4 files that can't generate a thumbnail (audio-only files)"""
        no_thumbnail_videos = []
        
        try:
            for item in folder.rglob('*.mp4'):
                if item.is_file():
                    # Skip 0-byte files (handled by broken media detection)
                    if item.stat().st_size == 0:
                        continue
                    
                    # Check if file can generate a thumbnail
                    if not self._can_generate_thumbnail(item):
                        no_thumbnail_videos.append(item)
                            
        except Exception as e:
            self.cleanup_log_message(f"Error finding no-thumbnail videos in '{folder}': {e}")
        
        return no_thumbnail_videos

    def _can_generate_thumbnail(self, video_path):
        """Check if video file can generate a thumbnail using ffmpeg"""
        import tempfile
        
        try:
            # Create a temporary file for the thumbnail
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
                temp_thumbnail = temp_file.name
            
            try:
                # Try to extract the first frame as a thumbnail
                cmd = [
                    get_ffmpeg_path(),
                    '-i', str(video_path),
                    '-vframes', '1',
                    '-f', 'image2',
                    '-y',  # Overwrite output file
                    '-v', 'quiet',  # Suppress output
                    temp_thumbnail
                ]
                
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                
                # Check if thumbnail was created and has content
                if result.returncode == 0:
                    try:
                        import os
                        # Check if file exists and has reasonable size (not just a tiny error image)
                        if os.path.exists(temp_thumbnail) and os.path.getsize(temp_thumbnail) > 1000:
                            return True
                    except Exception:
                        pass
                
                return False
                
            finally:
                # Clean up temporary file
                try:
                    import os
                    if os.path.exists(temp_thumbnail):
                        os.unlink(temp_thumbnail)
                except Exception:
                    pass
                
        except subprocess.TimeoutExpired:
            return False  # Timeout suggests issues
        except Exception:
            # If ffmpeg is not available, assume it's a valid video
            return True

    def _is_broken_video(self, video_path):
        """Check if video file is broken using ffprobe"""
        try:
            cmd = [
                get_ffmpeg_path().replace('ffmpeg', 'ffprobe').replace('ffmpeg.exe', 'ffprobe.exe'),
                '-v', 'quiet',
                '-show_entries', 'format=duration',
                '-of', 'csv=p=0',
                str(video_path)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode != 0:
                return True  # ffprobe failed, likely corrupted
            
            # Check if duration is 0 or invalid
            try:
                duration = float(result.stdout.strip())
                return duration <= 0
            except (ValueError, TypeError):
                return True  # Invalid duration output
                
        except subprocess.TimeoutExpired:
            return True  # Timeout suggests corruption
        except Exception:
            # If ffprobe is not available, skip video checking
            return False

    def _is_broken_image(self, image_path):
        """Check if image file is broken"""
        if Image is None:
            # PIL not available, only check file size
            return False
        
        try:
            with Image.open(image_path) as img:
                img.verify()  # Verify the image
            return False
        except Exception:
            return True  # Image is corrupted or unreadable

    def _find_temp_files(self, folder):
        """Find temporary and cache files"""
        temp_files = []
        temp_extensions = {'.tmp', '.temp', '.part', '.download', '.crdownload', '.partial'}
        temp_names = {'thumbs.db', '.ds_store', 'desktop.ini', '.localized', '.fseventsd', '.spotlight-v100', '.trashes'}
        
        try:
            for item in folder.rglob('*'):
                if item.is_file():
                    # Check by extension
                    if item.suffix.lower() in temp_extensions:
                        temp_files.append(item)
                    # Check by filename
                    elif item.name.lower() in temp_names:
                        temp_files.append(item)
                    # Check for browser temp files
                    elif item.name.startswith('.') and any(x in item.name.lower() for x in ['cache', 'temp', 'tmp']):
                        temp_files.append(item)
                        
        except Exception as e:
            self.cleanup_log_message(f"Error finding temp files in '{folder}': {e}")
        
        return temp_files

    def _find_custom_extension_files(self, folder):
        """Find files with custom extensions specified by user"""
        custom_files = []
        
        try:
            # Parse custom extensions
            extensions_text = self.custom_extensions_var.get().strip()
            if not extensions_text:
                return custom_files
            
            extensions = [ext.strip().lower() for ext in extensions_text.split(',')]
            # Ensure extensions start with dot
            extensions = [ext if ext.startswith('.') else f'.{ext}' for ext in extensions if ext]
            
            if not extensions:
                return custom_files
            
            for item in folder.rglob('*'):
                if item.is_file() and item.suffix.lower() in extensions:
                    custom_files.append(item)
                    
        except Exception as e:
            self.cleanup_log_message(f"Error finding custom extension files in '{folder}': {e}")
        
        return custom_files

    def _find_empty_folders(self, parent_folder):
        """Find empty folders"""
        empty_folders = []
        
        try:
            # Get all directories in reverse order (deepest first)
            all_dirs = [d for d in parent_folder.rglob('*') if d.is_dir()]
            all_dirs.sort(key=lambda x: len(x.parts), reverse=True)
            
            for folder in all_dirs:
                try:
                    # Check if folder is empty
                    if not any(folder.iterdir()):
                        empty_folders.append(folder)
                except Exception:
                    continue
                    
        except Exception as e:
            self.cleanup_log_message(f"Error finding empty folders in '{parent_folder}': {e}")
        
        return empty_folders

    def _flatten_folders_in_path(self, parent_folder):
        """Flatten folders by moving files from flat subfolders up one level"""
        try:
            flat_folders = self._find_flat_folders(parent_folder)
            
            for flat_folder in flat_folders:
                self.cleanup_log_message(f"Flattening folder: {flat_folder.name}")
                
                files = [f for f in flat_folder.iterdir() if f.is_file()]
                moved_count = 0
                
                for file_path in files:
                    try:
                        # Determine destination path
                        dest_path = parent_folder / file_path.name
                        
                        # Handle name conflicts
                        if dest_path.exists():
                            counter = 1
                            name_part = file_path.stem
                            ext_part = file_path.suffix
                            while dest_path.exists():
                                new_name = f"{name_part} ({counter}){ext_part}"
                                dest_path = parent_folder / new_name
                                counter += 1
                        
                        # Move the file
                        file_path.rename(dest_path)
                        moved_count += 1
                        
                    except Exception as e:
                        self.cleanup_log_message(f"Error moving file '{file_path.name}': {e}")
                
                self.cleanup_log_message(f"Moved {moved_count} files from '{flat_folder.name}'")
                
                # Remove the now-empty folder after moving all files
                try:
                    if moved_count > 0:  # Only remove if we successfully moved files
                        # Double-check the folder is actually empty
                        remaining_items = list(flat_folder.iterdir())
                        if not remaining_items:
                            flat_folder.rmdir()
                            self.cleanup_log_message(f"Removed empty folder: {flat_folder.name}")
                        else:
                            self.cleanup_log_message(f"Folder '{flat_folder.name}' not removed - still contains {len(remaining_items)} items")
                except Exception as e:
                    self.cleanup_log_message(f"Error removing empty folder '{flat_folder.name}': {e}")
                
        except Exception as e:
            self.cleanup_log_message(f"Error flattening folders in '{parent_folder}': {e}")

    def _flatten_selected_folder(self, selected_folder, parent_folder):
        """Flatten a specific selected folder by moving its contents to the parent folder"""
        try:
            self.cleanup_log_message(f"Flattening selected folder: {selected_folder.name}")
            
            # Get all items in the selected folder (files and subdirectories)
            all_items = list(selected_folder.iterdir())
            files = [item for item in all_items if item.is_file()]
            subdirs = [item for item in all_items if item.is_dir()]
            
            moved_count = 0
            
            # Move all files to parent folder
            for file_path in files:
                try:
                    # Determine destination path
                    dest_path = parent_folder / file_path.name
                    
                    # Handle name conflicts
                    if dest_path.exists():
                        counter = 1
                        name_part = file_path.stem
                        ext_part = file_path.suffix
                        while dest_path.exists():
                            new_name = f"{name_part} ({counter}){ext_part}"
                            dest_path = parent_folder / new_name
                            counter += 1
                    
                    # Move the file
                    file_path.rename(dest_path)
                    moved_count += 1
                    
                except Exception as e:
                    self.cleanup_log_message(f"Error moving file '{file_path.name}': {e}")
            
            # Move all subdirectories to parent folder
            for subdir in subdirs:
                try:
                    # Determine destination path
                    dest_path = parent_folder / subdir.name
                    
                    # Handle name conflicts
                    if dest_path.exists():
                        counter = 1
                        base_name = subdir.name
                        while dest_path.exists():
                            new_name = f"{base_name} ({counter})"
                            dest_path = parent_folder / new_name
                            counter += 1
                    
                    # Move the subdirectory
                    subdir.rename(dest_path)
                    moved_count += 1
                    
                except Exception as e:
                    self.cleanup_log_message(f"Error moving folder '{subdir.name}': {e}")
            
            self.cleanup_log_message(f"Moved {moved_count} items from '{selected_folder.name}'")
            
            # Remove the now-empty selected folder if all items were moved successfully
            try:
                remaining_items = list(selected_folder.iterdir())
                if not remaining_items:
                    selected_folder.rmdir()
                    self.cleanup_log_message(f"Removed empty folder: {selected_folder.name}")
                else:
                    self.cleanup_log_message(f"Folder '{selected_folder.name}' not removed - still contains {len(remaining_items)} items")
            except Exception as e:
                self.cleanup_log_message(f"Error removing empty folder '{selected_folder.name}': {e}")
                
        except Exception as e:
            self.cleanup_log_message(f"Error flattening selected folder '{selected_folder}': {e}")

    def _remove_broken_media_files(self, folder):
        """Remove broken or empty media files"""
        try:
            broken_files = self._find_broken_media_files(folder)
            removed_count = 0
            
            for file_path in broken_files:
                try:
                    file_path.unlink()
                    self.cleanup_log_message(f"Removed broken media file: {file_path.name}")
                    removed_count += 1
                except Exception as e:
                    self.cleanup_log_message(f"Error removing broken file '{file_path.name}': {e}")
            
            if removed_count > 0:
                self.cleanup_log_message(f"Removed {removed_count} broken media files")
                
        except Exception as e:
            self.cleanup_log_message(f"Error removing broken media files in '{folder}': {e}")

    def _remove_no_thumbnail_videos(self, folder):
        """Remove .mp4 files that can't generate thumbnails (audio-only files)"""
        try:
            no_thumbnail_videos = self._find_no_thumbnail_videos(folder)
            removed_count = 0
            
            for file_path in no_thumbnail_videos:
                try:
                    file_path.unlink()
                    self.cleanup_log_message(f"Removed .mp4 file without thumbnail: {file_path.name}")
                    removed_count += 1
                except Exception as e:
                    self.cleanup_log_message(f"Error removing .mp4 file '{file_path.name}': {e}")
            
            if removed_count > 0:
                self.cleanup_log_message(f"Removed {removed_count} .mp4 files without thumbnails")
                
        except Exception as e:
            self.cleanup_log_message(f"Error removing .mp4 files without thumbnails in '{folder}': {e}")

    def _remove_temp_files(self, folder):
        """Remove temporary and cache files"""
        try:
            temp_files = self._find_temp_files(folder)
            removed_count = 0
            
            for file_path in temp_files:
                try:
                    file_path.unlink()
                    self.cleanup_log_message(f"Removed temp file: {file_path.name}")
                    removed_count += 1
                except Exception as e:
                    self.cleanup_log_message(f"Error removing temp file '{file_path.name}': {e}")
            
            if removed_count > 0:
                self.cleanup_log_message(f"Removed {removed_count} temporary files")
                
        except Exception as e:
            self.cleanup_log_message(f"Error removing temp files in '{folder}': {e}")

    def _remove_custom_extension_files(self, folder):
        """Remove files with custom extensions"""
        try:
            custom_files = self._find_custom_extension_files(folder)
            removed_count = 0
            
            for file_path in custom_files:
                try:
                    file_path.unlink()
                    self.cleanup_log_message(f"Removed custom extension file: {file_path.name}")
                    removed_count += 1
                except Exception as e:
                    self.cleanup_log_message(f"Error removing custom file '{file_path.name}': {e}")
            
            if removed_count > 0:
                self.cleanup_log_message(f"Removed {removed_count} custom extension files")
                
        except Exception as e:
            self.cleanup_log_message(f"Error removing custom extension files in '{folder}': {e}")

    def _remove_empty_folders(self, parent_folder):
        """Remove empty folders"""
        try:
            empty_folders = self._find_empty_folders(parent_folder)
            removed_count = 0
            
            for folder_path in empty_folders:
                try:
                    folder_path.rmdir()
                    self.cleanup_log_message(f"Removed empty folder: {folder_path.name}")
                    removed_count += 1
                except Exception as e:
                    self.cleanup_log_message(f"Error removing empty folder '{folder_path.name}': {e}")
            
            if removed_count > 0:
                self.cleanup_log_message(f"Removed {removed_count} empty folders")
                
        except Exception as e:
            self.cleanup_log_message(f"Error removing empty folders in '{parent_folder}': {e}")

    # ========================= Duplicate File Finder Tab Logic =========================
    def duplicate_browse_folder(self):
        folder = filedialog.askdirectory(title="Select Folder to Scan for Duplicates")
        if folder:
            self.duplicate_selected_folder.set(folder)
            self.duplicate_log_message(f"Selected folder: {folder}")

    def duplicate_log_message(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.duplicate_log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.duplicate_log_text.see(tk.END)
        self.root.update_idletasks()

    def duplicate_scan_files(self):
        """Scan for duplicate files using optimized approach"""
        if not self.duplicate_selected_folder.get():
            messagebox.showerror("Error", "Please select a folder first")
            return

        if self.duplicate_is_processing:
            messagebox.showinfo("Info", "Duplicate scan is already in progress")
            return

        self.duplicate_is_processing = True
        self.duplicate_progress_var.set("Scanning...")
        
        # Clear previous results
        for item in self.duplicate_tree.get_children():
            self.duplicate_tree.delete(item)

        thread = threading.Thread(target=self._duplicate_scan_worker)
        thread.daemon = True
        thread.start()

    def _duplicate_scan_worker(self):
        """Worker thread for duplicate scanning"""
        try:
            folder_path = Path(self.duplicate_selected_folder.get())
            self.duplicate_log_message("=== STARTING DUPLICATE SCAN ===")
            
            # Get minimum file size
            try:
                min_size_kb = int(self.duplicate_min_size_var.get())
                min_size_bytes = min_size_kb * 1024
            except ValueError:
                min_size_bytes = 100 * 1024  # Default 100KB
            
            # Step 1: Collect all files and group by size
            self.duplicate_log_message("Step 1: Collecting files and grouping by size...")
            size_groups = self._collect_files_by_size(folder_path, min_size_bytes)
            
            # Step 2: Filter out unique sizes (optimization)
            self.duplicate_log_message("Step 2: Filtering unique file sizes...")
            potential_duplicates = {size: files for size, files in size_groups.items() if len(files) > 1}
            
            if not potential_duplicates:
                self.duplicate_log_message("No potential duplicates found (no files with matching sizes)")
                return
            
            self.duplicate_log_message(f"Found {sum(len(files) for files in potential_duplicates.values())} files with matching sizes")
            
            # Step 3: Quick hash check (first few KB)
            self.duplicate_log_message("Step 3: Performing quick hash check...")
            quick_hash_groups = self._quick_hash_check(potential_duplicates)
            
            # Step 4: Full hash for final confirmation
            self.duplicate_log_message("Step 4: Full hash verification...")
            duplicate_groups = self._full_hash_check(quick_hash_groups)
            
            # Step 5: Display results
            self._display_duplicate_results(duplicate_groups)
            
            total_duplicates = sum(len(group) - 1 for group in duplicate_groups.values())  # -1 because we keep one original
            self.duplicate_log_message(f"=== SCAN COMPLETE: Found {total_duplicates} duplicate files in {len(duplicate_groups)} groups ===")
            
        except Exception as e:
            self.duplicate_log_message(f"Error during duplicate scan: {e}")
        finally:
            self.duplicate_is_processing = False
            self.duplicate_progress_var.set("Ready")

    def _collect_files_by_size(self, folder_path, min_size_bytes):
        """Collect all files and group them by size"""
        size_groups = defaultdict(list)
        
        try:
            # Determine scan pattern
            if self.duplicate_include_subfolders_var.get():
                pattern = "**/*"
            else:
                pattern = "*"
            
            # Media file extensions for filtering
            media_extensions = {
                '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.tif', '.webp', '.svg', '.ico',  # Images
                '.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.m2ts', '.ts',   # Videos
                '.mp3', '.wav', '.flac', '.aac', '.m4a', '.ogg', '.wma'  # Audio
            }
            
            for file_path in folder_path.glob(pattern):
                if file_path.is_file():
                    try:
                        file_size = file_path.stat().st_size
                        
                        # Skip files smaller than minimum
                        if file_size < min_size_bytes:
                            continue
                        
                        # Filter by file type if needed
                        if not self.duplicate_scan_all_files_var.get():
                            if file_path.suffix.lower() not in media_extensions:
                                continue
                        
                        size_groups[file_size].append(file_path)
                        
                    except Exception as e:
                        self.duplicate_log_message(f"Error accessing file '{file_path}': {e}")
                        continue
            
            self.duplicate_log_message(f"Collected {sum(len(files) for files in size_groups.values())} files")
            
        except Exception as e:
            self.duplicate_log_message(f"Error collecting files: {e}")
        
        return size_groups

    def _quick_hash_check(self, size_groups):
        """Perform quick hash check on first few KB of files"""
        quick_hash_groups = defaultdict(list)
        hash_algorithm = self.duplicate_hash_algorithm_var.get()
        
        try:
            total_files = sum(len(files) for files in size_groups.values())
            processed = 0
            
            for size, files in size_groups.items():
                for file_path in files:
                    try:
                        # Calculate quick hash (first 64KB)
                        quick_hash = self._calculate_quick_hash(file_path, hash_algorithm)
                        if quick_hash:
                            # Use size + quick_hash as key for better grouping
                            key = f"{size}_{quick_hash}"
                            quick_hash_groups[key].append(file_path)
                        
                        processed += 1
                        if processed % 50 == 0:  # Update progress every 50 files
                            self.duplicate_progress_var.set(f"Quick hash: {processed}/{total_files}")
                        
                    except Exception as e:
                        self.duplicate_log_message(f"Error quick hashing '{file_path}': {e}")
                        continue
            
            # Filter out groups with only one file
            quick_hash_groups = {key: files for key, files in quick_hash_groups.items() if len(files) > 1}
            self.duplicate_log_message(f"Quick hash found {len(quick_hash_groups)} potential duplicate groups")
            
        except Exception as e:
            self.duplicate_log_message(f"Error in quick hash check: {e}")
        
        return quick_hash_groups

    def _full_hash_check(self, quick_hash_groups):
        """Perform full hash check for final confirmation"""
        duplicate_groups = defaultdict(list)
        hash_algorithm = self.duplicate_hash_algorithm_var.get()
        
        try:
            total_files = sum(len(files) for files in quick_hash_groups.values())
            processed = 0
            
            for quick_key, files in quick_hash_groups.items():
                for file_path in files:
                    try:
                        # Calculate full file hash
                        full_hash = self._calculate_full_hash(file_path, hash_algorithm)
                        if full_hash:
                            duplicate_groups[full_hash].append(file_path)
                        
                        processed += 1
                        if processed % 20 == 0:  # Update progress every 20 files
                            self.duplicate_progress_var.set(f"Full hash: {processed}/{total_files}")
                        
                    except Exception as e:
                        self.duplicate_log_message(f"Error full hashing '{file_path}': {e}")
                        continue
            
            # Filter out groups with only one file
            duplicate_groups = {hash_val: files for hash_val, files in duplicate_groups.items() if len(files) > 1}
            
        except Exception as e:
            self.duplicate_log_message(f"Error in full hash check: {e}")
        
        return duplicate_groups

    def _calculate_quick_hash(self, file_path, algorithm):
        """Calculate hash of first 64KB of file"""
        try:
            hasher = hashlib.new(algorithm)
            with open(file_path, 'rb') as f:
                # Read first 64KB
                chunk = f.read(65536)
                hasher.update(chunk)
            return hasher.hexdigest()
        except Exception:
            return None

    def _calculate_full_hash(self, file_path, algorithm):
        """Calculate hash of entire file"""
        try:
            hasher = hashlib.new(algorithm)
            with open(file_path, 'rb') as f:
                # Read file in chunks to handle large files
                while True:
                    chunk = f.read(65536)  # 64KB chunks
                    if not chunk:
                        break
                    hasher.update(chunk)
            return hasher.hexdigest()
        except Exception:
            return None

    def _display_duplicate_results(self, duplicate_groups):
        """Display duplicate results in the treeview"""
        try:
            group_num = 1
            for hash_value, files in duplicate_groups.items():
                if len(files) < 2:
                    continue
                
                # Sort files by path for consistent ordering
                files.sort(key=lambda x: str(x))
                
                # Create group node
                group_name = f"Group {group_num} ({len(files)} files)"
                group_node = self.duplicate_tree.insert('', tk.END, text=group_name, values=("", "", ""))
                
                # Add files to group
                for i, file_path in enumerate(files):
                    try:
                        file_size = file_path.stat().st_size
                        size_str = self._format_file_size(file_size)
                        
                        # Mark duplicates (keep first as original)
                        if i == 0:
                            file_name = f"📁 {file_path.name} (Original)"
                        else:
                            file_name = f"🔄 {file_path.name} (Duplicate)"
                        
                        self.duplicate_tree.insert(group_node, tk.END, text="", 
                                                 values=(file_name, size_str, str(file_path.parent)))
                    except Exception as e:
                        self.duplicate_log_message(f"Error displaying file '{file_path}': {e}")
                
                # Expand group
                self.duplicate_tree.item(group_node, open=True)
                group_num += 1
                
        except Exception as e:
            self.duplicate_log_message(f"Error displaying results: {e}")

    def _format_file_size(self, size_bytes):
        """Format file size in human readable format"""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"

    def duplicate_apply_actions(self):
        """Apply selected action to duplicate files"""
        # Get duplicate groups from tree
        duplicate_groups = self._extract_duplicate_groups_from_tree()
        
        if not duplicate_groups:
            messagebox.showinfo("Info", "No duplicates found. Please scan for duplicates first.")
            return

        action = self.duplicate_action_var.get()
        
        if action == "flag":
            messagebox.showinfo("Info", "Duplicates are set to flag only. Select the delete or move option to make changes. No files were modified.")
            return
        
        # Confirm action
        total_duplicates = sum(len(group) - 1 for group in duplicate_groups)  # -1 for original
        if action == "delete":
            msg = f"Delete {total_duplicates} duplicate files? This cannot be undone."
        elif action == "move":
            msg = f"Move {total_duplicates} duplicate files to 'Duplicates' subfolder?"
        
        if not messagebox.askyesno("Confirm", msg):
            return

        # Apply action in background thread
        self.duplicate_is_processing = True
        self.duplicate_progress_var.set("Applying actions...")
        
        thread = threading.Thread(target=self._apply_duplicate_actions_worker, args=(duplicate_groups, action))
        thread.daemon = True
        thread.start()

    def _extract_duplicate_groups_from_tree(self):
        """Extract duplicate file groups from the treeview"""
        duplicate_groups = []
        
        try:
            for group_item in self.duplicate_tree.get_children():
                group_files = []
                for file_item in self.duplicate_tree.get_children(group_item):
                    values = self.duplicate_tree.item(file_item, 'values')
                    if len(values) >= 3:
                        file_name = values[0].replace("📁 ", "").replace("🔄 ", "").replace(" (Original)", "").replace(" (Duplicate)", "")
                        file_location = values[2]
                        file_path = Path(file_location) / file_name
                        group_files.append(file_path)
                
                if len(group_files) > 1:
                    duplicate_groups.append(group_files)
                    
        except Exception as e:
            self.duplicate_log_message(f"Error extracting duplicate groups: {e}")
        
        return duplicate_groups

    def _apply_duplicate_actions_worker(self, duplicate_groups, action):
        """Worker thread for applying actions to duplicates"""
        try:
            self.duplicate_log_message(f"=== APPLYING {action.upper()} ACTION ===")
            
            if action == "move":
                # Create duplicates folder
                base_folder = Path(self.duplicate_selected_folder.get())
                duplicates_folder = base_folder / "Duplicates"
                duplicates_folder.mkdir(exist_ok=True)
                self.duplicate_log_message(f"Created duplicates folder: {duplicates_folder}")
            
            processed = 0
            total_files = sum(len(group) - 1 for group in duplicate_groups)  # -1 for original
            
            for group in duplicate_groups:
                # Skip first file (original), process the rest as duplicates
                for duplicate_file in group[1:]:
                    try:
                        if action == "delete":
                            duplicate_file.unlink()
                            self.duplicate_log_message(f"Deleted: {duplicate_file.name}")
                        elif action == "move":
                            dest_path = duplicates_folder / duplicate_file.name
                            # Handle name conflicts
                            counter = 1
                            while dest_path.exists():
                                name_part = duplicate_file.stem
                                ext_part = duplicate_file.suffix
                                dest_path = duplicates_folder / f"{name_part} ({counter}){ext_part}"
                                counter += 1
                            
                            duplicate_file.rename(dest_path)
                            self.duplicate_log_message(f"Moved: {duplicate_file.name} → Duplicates/{dest_path.name}")
                        
                        processed += 1
                        self.duplicate_progress_var.set(f"{action.title()}: {processed}/{total_files}")
                        
                    except Exception as e:
                        self.duplicate_log_message(f"Error processing '{duplicate_file}': {e}")
            
            self.duplicate_log_message(f"=== {action.upper()} COMPLETE: {processed} files processed ===")
            
            # Show completion message to user
            if processed > 0:
                if action == "delete":
                    messagebox.showinfo("Success", f"Successfully deleted {processed} duplicate files!\n\nRefreshing scan to show updated results...")
                elif action == "move":
                    messagebox.showinfo("Success", f"Successfully moved {processed} duplicate files to 'Duplicates' folder!\n\nRefreshing scan to show updated results...")
                
                self.duplicate_log_message("Refreshing duplicate scan to show updated results...")
                # Clear current results first
                self.root.after(100, self._clear_and_refresh_duplicates)
            else:
                messagebox.showwarning("Warning", "No files were processed. Please check the log for details.")
            
        except Exception as e:
            self.duplicate_log_message(f"Error applying actions: {e}")
        finally:
            self.duplicate_is_processing = False
            self.duplicate_progress_var.set("Ready")

    def _clear_and_refresh_duplicates(self):
        """Clear the duplicate tree view and refresh the scan"""
        try:
            # Clear the tree view
            for item in self.duplicate_tree.get_children():
                self.duplicate_tree.delete(item)
            
            # Show visual feedback
            self.duplicate_progress_var.set("Refreshing scan...")
            self.duplicate_log_message("Cleared previous results, starting fresh scan...")
            
            # Start a new scan in background
            self.duplicate_is_processing = True
            thread = threading.Thread(target=self._duplicate_scan_worker)
            thread.daemon = True
            thread.start()
            
        except Exception as e:
            self.duplicate_log_message(f"Error refreshing duplicates: {e}")
            self.duplicate_is_processing = False
            self.duplicate_progress_var.set("Ready")

def main():
    root = tk.Tk()
    app = ImportFolderCleanup(root)
    root.mainloop()

if __name__ == "__main__":
    main() 
