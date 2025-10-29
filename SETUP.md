# BrowserControl - Setup Guide

## For End Users

**Just want to install and use BrowserControl?**

1. Download the latest installer from [GitHub Releases](https://github.com/ShutterSeeker/BrowserControl/releases/latest)
2. Run `BrowserControlSetup_X.X.X.exe`
3. Launch BrowserControl from your desktop or Start Menu
4. Updates will be automatic - just click "Update" when prompted!

## For Developers

Quick reference for running the code and building executables.

---

## ⚠️ IMPORTANT: First Time Setup

### Configure GitHub Token (Required for Error Reporting)

1. **Copy the template file:**
   ```powershell
   copy constants.py.template constants.py
   ```

2. **Get a GitHub Personal Access Token:**
   - Go to https://github.com/settings/tokens
   - Click "Generate new token (classic)"
   - Name: "BrowserControl Error Reporter"
   - Select scope: `repo`
   - Click "Generate token"
   - **Copy the token immediately!**

3. **Edit `constants.py`:**
   - Replace `"your_github_token_here"` with your actual token
   - Example: `GITHUB_TOKEN = "ghp_abc123..."`

4. **NEVER commit `constants.py` to Git!**
   - It's already in `.gitignore`
   - Only commit `constants.py.template`

---

## Development Setup

# Create virtual environment
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

# Install dependencies
```powershell
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

## Building Releases

**Install PyInstaller:**
```powershell
pip install pyinstaller==6.16.0
```

**Production Build (no console):**
```powershell
pyinstaller --clean BrowserControl.spec
```

Output: `dist\BrowserControl.exe`

**Production Build (no console):**
```powershell
cd backend
pyinstaller --clean BrowserControlAPI.spec
```

---

**Debug Build (with console for troubleshooting):**
```powershell
pyinstaller --clean BrowserControlConsole.spec
```

**Output:** Executables in `dist/` folder
- `dist/BrowserControl.exe`
- `dist/BrowserControlAPI.exe`

---

**Python:** 3.13.8 | **PyInstaller:** 6.11.0
