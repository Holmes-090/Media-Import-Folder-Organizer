@echo off
echo Building Bulk Folder Renamer executable...
echo.

REM Install PyInstaller if not already installed
pip install pyinstaller

REM Clean previous builds
if exist "build" rmdir /s /q build
if exist "dist" rmdir /s /q dist
if exist "*.spec" del *.spec

REM Create executable with PyInstaller
pyinstaller --onefile ^
    --windowed ^
    --name "BulkFolderRenamer" ^
    --icon=icon.ico ^
    --add-binary "ffmpeg.exe;." ^
    --hidden-import "PIL" ^
    --hidden-import "PIL.Image" ^
    --hidden-import "tkinter" ^
    --hidden-import "tkinter.ttk" ^
    --hidden-import "tkinter.filedialog" ^
    --hidden-import "tkinter.messagebox" ^
    --hidden-import "tkinter.scrolledtext" ^
    --distpath "dist" ^
    --workpath "build" ^
    bulk_folder_renamer.py

echo.
echo Build complete! Check the 'dist' folder for your executable.
echo.
pause

