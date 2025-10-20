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

### Quick Build (Executable + Installer)

See [BUILD_GUIDE.md](BUILD_GUIDE.md) for complete instructions.

```powershell
# Build everything (requires Inno Setup)
.\build_release.ps1
```

### Manual Build (Executable Only)

**Install PyInstaller:**
```powershell
pip install pyinstaller==6.16.0
```

**Production Build (no console):**
```powershell
pyinstaller --clean BrowserControl.spec
```

Output: `dist\BrowserControl.exe`

### Building the Installer

1. **Install Inno Setup 6**: https://jrsoftware.org/isdl.php
2. **Build executable first** (see above)
3. **Compile installer**:
   ```powershell
   "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" BrowserControl.iss
   ```

Output: `dist\BrowserControlSetup_X.X.X.exe`

**See [BUILD_GUIDE.md](BUILD_GUIDE.md) for release process and testing.**

---

## Project Structure

```
BrowserControl/
├── main.py                    # Application entry point
├── ui.py                      # Main window UI
├── tab_home.py                # Login tab
├── tab_settings.py            # Settings tab
├── tab_tools.py               # Tools tab
├── launcher.py                # Browser launch logic
├── chrome.py                  # Chrome automation
├── updater.py                 # Automatic update system
├── error_reporter.py          # GitHub issue creation
├── constants.py               # Configuration (gitignored)
├── constants.py.template      # Template for setup
├── BrowserControl.spec        # PyInstaller config
├── BrowserControl.iss         # Inno Setup config
└── build_release.ps1          # Automated build script
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
