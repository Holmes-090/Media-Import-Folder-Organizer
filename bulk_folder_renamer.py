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

class ImportFolderCleanup:
    def __init__(self, root):
        self.root = root
        self.root.title("Import Folder Cleanup")
        self.root.geometry("800x600")
        self.root.minsize(800, 600)
        
        # Variables
        self.selected_folder = tk.StringVar()
        self.processing_queue = queue.Queue()
        self.is_processing = False
        
        # Video/Audio file extensions
        self.video_extensions = {'.mp4', '.webm', '.avi', '.mov', '.mkv'}
        self.audio_extensions = {'.m4a', '.aac', '.mp3', '.wav', '.flac', '.audio'}
        
        self.setup_ui()
        self.load_config()
        
    def setup_ui(self):
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=3)
        main_frame.columnconfigure(1, weight=1)
        
        # Folder selection
        ttk.Label(main_frame, text="Select Import Folder:").grid(row=0, column=0, sticky=tk.W, pady=(0, 5))
        folder_frame = ttk.Frame(main_frame)
        folder_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        folder_frame.columnconfigure(0, weight=1)
        
        ttk.Entry(folder_frame, textvariable=self.selected_folder, state="readonly").grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 5))
        ttk.Button(folder_frame, text="Browse", command=self.browse_folder).grid(row=0, column=1)
        
        # Subfolder selection
        subfolders_frame = ttk.LabelFrame(main_frame, text="Subfolders (control/shift click to select to limit changes)", padding="10")
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

        # Select all button
        select_all_frame = ttk.Frame(subfolders_frame)
        select_all_frame.grid(row=1, column=0, sticky=tk.W, pady=(6, 0))
        ttk.Button(select_all_frame, text="Select All", command=self.select_all_subfolders).grid(row=0, column=0, sticky=tk.W)

        # Renaming options frame
        options_frame = ttk.LabelFrame(main_frame, text="Folder Renaming Options", padding="10")
        options_frame.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        options_frame.columnconfigure(1, weight=1)
        
        # Remove first X characters
        ttk.Label(options_frame, text="Remove first X characters:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.remove_first_var = tk.StringVar(value="0")
        ttk.Entry(options_frame, textvariable=self.remove_first_var, width=10).grid(row=0, column=1, sticky=tk.W, padx=(10, 0), pady=2)

        # Remove last X characters
        ttk.Label(options_frame, text="Remove last X characters:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.remove_last_var = tk.StringVar(value="0")
        ttk.Entry(options_frame, textvariable=self.remove_last_var, width=10).grid(row=1, column=1, sticky=tk.W, padx=(10, 0), pady=2)
        
        # Remove everything before character
        ttk.Label(options_frame, text="Remove everything before character:").grid(row=2, column=0, sticky=tk.W, pady=2)
        self.before_char_var = tk.StringVar()
        ttk.Entry(options_frame, textvariable=self.before_char_var, width=10).grid(row=2, column=1, sticky=tk.W, padx=(10, 0), pady=2)
        
        # Remove everything after character
        ttk.Label(options_frame, text="Remove everything after character:").grid(row=3, column=0, sticky=tk.W, pady=2)
        self.after_char_var = tk.StringVar()
        ttk.Entry(options_frame, textvariable=self.after_char_var, width=10).grid(row=3, column=1, sticky=tk.W, padx=(10, 0), pady=2)
        
        # Remove digits
        self.remove_digits_var = tk.BooleanVar()
        ttk.Checkbutton(options_frame, text="Remove all digits", variable=self.remove_digits_var).grid(row=4, column=0, columnspan=2, sticky=tk.W, pady=2)
        
        # Remove special characters
        self.remove_special_var = tk.BooleanVar()
        ttk.Checkbutton(options_frame, text="Remove special characters", variable=self.remove_special_var).grid(row=5, column=0, columnspan=2, sticky=tk.W, pady=2)
        
        # Replace underscores with spaces
        self.replace_underscores_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="Replace underscores with spaces", variable=self.replace_underscores_var).grid(row=6, column=0, columnspan=2, sticky=tk.W, pady=2)
        
        # Title case
        self.title_case_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="Convert to title case", variable=self.title_case_var).grid(row=7, column=0, columnspan=2, sticky=tk.W, pady=2)
        
        # Processing options frame
        processing_frame = ttk.LabelFrame(main_frame, text="Processing Options", padding="10")
        processing_frame.grid(row=4, column=0, sticky=(tk.W, tk.E, tk.N), pady=(0, 10))

        # Rename files to folder name
        self.rename_files_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(processing_frame, text="Rename files to folder name", variable=self.rename_files_var).grid(row=0, column=0, sticky=tk.W, pady=2)
        
        # Rejoin split .mp4 files
        self.rejoin_split_mp4_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(processing_frame, text="Rejoin Split .mp4 Files", variable=self.rejoin_split_mp4_var).grid(row=1, column=0, sticky=tk.W, pady=2)
        
        # Buttons frame
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.grid(row=5, column=0, columnspan=2, pady=(0, 10))
        
        ttk.Button(buttons_frame, text="Preview Changes", command=self.preview_changes).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(buttons_frame, text="Apply Changes", command=self.apply_changes).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(buttons_frame, text="Save Configuration", command=self.save_config).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(buttons_frame, text="Load Configuration", command=self.load_config_dialog).pack(side=tk.LEFT)
        
        # Progress frame (no loading bar)
        progress_frame = ttk.LabelFrame(main_frame, text="Progress", padding="10")
        progress_frame.grid(row=6, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        progress_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(3, weight=1)
        
        self.progress_var = tk.StringVar(value="Ready")
        ttk.Label(progress_frame, textvariable=self.progress_var).grid(row=0, column=0, sticky=tk.W)
        
        # Log frame
        log_frame = ttk.LabelFrame(main_frame, text="Log", padding="10")
        log_frame.grid(row=3, column=1, rowspan=2, sticky=(tk.W, tk.E, tk.N, tk.S))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        main_frame.rowconfigure(3, weight=1)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=10, wrap=tk.WORD, width=40)
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
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
                self.log_message(f"FFmpeg error: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            self.log_message("FFmpeg operation timed out")
            return False
        except Exception as e:
            self.log_message(f"Error merging files: {e}")
            return False

    def get_ffmpeg_path():
        if getattr(sys, 'frozen', False):  # running as exe
            return os.path.join(sys._MEIPASS, 'ffmpeg.exe')
        return 'ffmpeg'  # running from source
            
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

        # Prepare folder rename simulation to reflect conflict handling and case-insensitive FS
        folders = [p for p in folder_path.iterdir() if p.is_dir() and (selected_names is None or p.name in selected_names)]
        planned = [(p, self.clean_folder_name(p.name)) for p in folders]
        # Order by original name length (longest first), matching processing
        planned.sort(key=lambda x: len(x[0].name), reverse=True)

        def norm_name(name: str) -> str:
            return os.path.normcase(name)

        occupied = {norm_name(p.name) for p in folders}

        folder_final_names = {}

        for folder, target_name in planned:
            old_name = folder.name
            old_norm = norm_name(old_name)
            target_norm = norm_name(target_name)
            final_name = target_name
            if old_name != target_name:
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
                parent = folder.parent
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
                        str(parent / item['final_folder_name'])
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
            
            # Step 1: Rename folders
            self.log_message("Step 1: Renaming folders...")
            folders_to_rename = []
            
            for item in folder_path.iterdir():
                if item.is_dir() and (self._selected_names_at_apply is None or item.name in self._selected_names_at_apply):
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
                    
            # Step 2: Rename files and merge video/audio
            self.log_message("Step 2: Processing files...")
            
            if self.rename_files_var.get():
                for item in folder_path.iterdir():
                    if item.is_dir() and (self._selected_names_at_apply is None or item.name in self._selected_names_at_apply):
                        self._process_folder_contents(item)
                    
            # Step 3: Optionally rejoin split mp4 files
            if self.rejoin_split_mp4_var.get():
                self.log_message("Step 3: Rejoining split .mp4 files...")
                self._rejoin_split_mp4_in_selected(folder_path)

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

    def _rejoin_split_mp4_in_selected(self, root_folder: Path) -> None:
        """Search selected subfolders for pairs of mp4 files with same base name (one suffixed with ' 2') and concatenate them with ffmpeg."""
        selected = self._selected_names_at_apply
        try:
            for item in root_folder.iterdir():
                if not item.is_dir():
                    continue
                if selected is not None and item.name not in selected:
                    continue

                mp4_files = [f for f in item.iterdir() if f.is_file() and f.suffix.lower() == ".mp4"]
                # Build map from base without trailing ' 2' to entries
                base_to_files = {}
                for f in mp4_files:
                    name_no_ext = f.stem
                    if name_no_ext.endswith(" 2"):
                        base = name_no_ext[:-2]
                        key = base
                        base_to_files.setdefault(key, {1: None, 2: None})
                        base_to_files[key][2] = f
                    else:
                        key = name_no_ext
                        base_to_files.setdefault(key, {1: None, 2: None})
                        base_to_files[key][1] = f

                for base, parts in base_to_files.items():
                    first = parts.get(1)
                    second = parts.get(2)
                    if first and second:
                        try:
                            output_path = item / f"{base}.mp4"
                            # If output exists, add numeric suffix
                            if output_path.exists():
                                counter = 1
                                candidate = item / f"{base} ({counter}).mp4"
                                while candidate.exists():
                                    counter += 1
                                    candidate = item / f"{base} ({counter}).mp4"
                                output_path = candidate

                            # Attempt to merge assuming first is video and second is audio
                            merged = self.merge_video_audio(first, second, output_path)
                            if not merged:
                                # Fallback: assume reversed
                                merged = self.merge_video_audio(second, first, output_path)
                            if merged:
                                try:
                                    first.unlink()
                                    second.unlink()
                                except Exception:
                                    pass
                                self.log_message(f"Joined split mp4 into '{output_path.name}' in '{item.name}'")
                            else:
                                self.log_message(f"Failed to join split mp4 for '{base}'.")
                        except Exception as e:
                            self.log_message(f"Error joining split mp4 for '{base}': {e}")
        except Exception as e:
            self.log_message(f"Error scanning folders to rejoin videos: {e}")
            
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

def main():
    root = tk.Tk()
    app = ImportFolderCleanup(root)
    root.mainloop()

if __name__ == "__main__":
    main() 
