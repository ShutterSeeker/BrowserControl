# BrowserControl - Setup Guide

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

## Building Executables

### Install PyInstaller
```powershell
pip install pyinstaller==6.11.0
```

**Production Build (no console):**
```powershell
pyinstaller --clean BrowserControl.spec
```

**Debug Build (with console for troubleshooting):**
```powershell
pyinstaller --clean BrowserControlConsole.spec
```

**Output:** Executables in `dist/` folder
- `dist/BrowserControl.exe`
- `dist/BrowserControlAPI.exe`

---

**Python:** 3.13.8 | **PyInstaller:** 6.11.0
