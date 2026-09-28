import os
import subprocess
import sys

def main():
    print("Installing PyInstaller...")
    subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller", "uvicorn"], check=True)
    
    # We need to copy static/ and the bmi_logo.png
    # The --add-data syntax on Windows is "source;destination"
    command = [
        "pyinstaller",
        "--clean",
        "--name=SpecGenerator",
        "--onefile",
        "--add-data=backend/static;static",
        "--add-data=bmi_logo.png;.",
        "backend/main.py"
    ]
    
    print("Building Executable... This might take a few minutes.")
    subprocess.run(command, check=True)
    
    print("\n\nBuild Complete!")
    print("Your executable is located in the 'dist' folder: dist\\SpecGenerator.exe")

if __name__ == "__main__":
    main()
