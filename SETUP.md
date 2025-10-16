# BrowserControl - Setup Guide

Quick reference for running the code and building executables.

---

## Running the Code

### First Time Setup
```powershell
# Clone the repository
git clone https://github.com/ShutterSeeker/BrowserControl.git
cd BrowserControl

# Create virtual environment
python -m venv .venv
.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt
```

### Run the Application
```powershell
python main.py
```

### Run the Backend API (optional)
```powershell
cd backend
python app.py
```

---

## Building Executables

### Install PyInstaller
```powershell
pip install pyinstaller==6.11.0
```

### Build (Automated)

**Production Build (no console):**
```powershell
.\build.ps1
```

**Debug Build (with console for troubleshooting):**
```powershell
.\build.ps1 -Debug
```

**Output:** Executables in `dist/` folder
- `dist/BrowserControl.exe`
- `dist/BrowserControlAPI.exe`

> 💡 **Tip:** Use `-Debug` flag to see console output for troubleshooting errors

### Build (Manual)
```powershell
# Main application
pyinstaller BrowserControl.spec

# Backend API
cd backend
pyinstaller BrowserControlAPI.spec
cd ..
```

**For debug builds**, edit `.spec` files and change:
```python
console=False,  # Change to console=True
```

---

## Troubleshooting

**Missing module error?**  
→ Add to `hiddenimports` in `.spec` file

**Missing files at runtime?**  
→ Add to `datas` in `.spec` file

**Need console for debugging?**  
→ Change `console=False` to `console=True` in `.spec` file

---

## Distribution Package

```powershell
# Copy to distribution folder
$version = "2.1.0"
New-Item -ItemType Directory -Path "BrowserControl-v$version"
Copy-Item "dist\*.exe" "BrowserControl-v$version\"
Copy-Item "jasco.ico", "settings.ini" "BrowserControl-v$version\"

# Create ZIP
Compress-Archive -Path "BrowserControl-v$version" -DestinationPath "BrowserControl-v$version.zip"
```

---

**Python:** 3.13.8 | **PyInstaller:** 6.11.0
