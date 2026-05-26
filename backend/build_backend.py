import os
import shutil
import subprocess
import sys
from pathlib import Path

def build():
    print("Building backend executable...")
    # Clean previous builds
    for folder in ["build", "dist"]:
        if os.path.exists(folder):
            print(f"Cleaning {folder}...")
            shutil.rmtree(folder)
            
    # PyInstaller command
    cmd = [
        "pyinstaller",
        "--name=localmind-backend",
        "--onefile",
        "--add-data=demo_data;demo_data",
        # hidden imports for libraries that are loaded dynamically (e.g., Uvicorn modules)
        "--hidden-import=uvicorn.logging",
        "--hidden-import=uvicorn.loops",
        "--hidden-import=uvicorn.loops.auto",
        "--hidden-import=uvicorn.protocols",
        "--hidden-import=uvicorn.protocols.http",
        "--hidden-import=uvicorn.protocols.http.auto",
        "--hidden-import=uvicorn.protocols.websockets",
        "--hidden-import=uvicorn.protocols.websockets.auto",
        "--hidden-import=uvicorn.lifespan",
        "--hidden-import=uvicorn.lifespan.on",
        "--hidden-import=numpy",
        "--hidden-import=faiss",
        "--hidden-import=sentence_transformers",
        "--collect-all=cryptography",
        "main.py"
    ]
    
    print(f"Running command: {' '.join(cmd)}")
    # We call PyInstaller directly
    try:
        import PyInstaller.__main__
        PyInstaller.__main__.run(cmd[1:])
        print("Backend build completed successfully via PyInstaller! Executable is at dist/localmind-backend.exe")
    except ImportError:
        # Fallback to subprocess if PyInstaller is not installed in the current environment
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print("PyInstaller build failed!")
            print("stdout:", result.stdout)
            print("stderr:", result.stderr)
            sys.exit(1)
        print("Backend build completed successfully! Executable is at dist/localmind-backend.exe")

if __name__ == "__main__":
    build()
