# updater.py
# Handles automatic download and installation of updates via PowerShell script

import requests
import os
import subprocess
import tempfile
import shutil
import sys
from pathlib import Path
from constants import UPDATE_CHECK_URL, VERSION

def get_latest_release_info():
    """
    Get information about the latest release from GitHub.
    
    Returns:
        dict: {
            'version': str,
            'exe_url': str,
            'release_notes': str
        } or None on failure
    """
    try:
        response = requests.get(UPDATE_CHECK_URL, timeout=5)
        response.raise_for_status()
        
        data = response.json()
        latest_version = data.get("tag_name", "").lstrip("v")
        
        # Find direct exe asset
        assets = data.get("assets", [])
        exe_asset = None
        
        for asset in assets:
            if asset["name"] == "BrowserControl.exe":
                exe_asset = asset
                break
        
        if not exe_asset:
            print("[ERROR] No BrowserControl.exe found in latest release")
            return None
        
        return {
            'version': latest_version,
            'exe_url': exe_asset["browser_download_url"],
            'release_notes': data.get("body", "No release notes available"),
            'published_at': data.get("published_at", "")
        }
    
    except Exception as e:
        print(f"[ERROR] Failed to get release info: {e}")
        return None

def install_update_direct(exe_url):
    """
    Direct EXE replacement update using PowerShell script.
    Downloads new exe and creates PowerShell script to replace current one.
    
    Args:
        exe_url: Direct URL to BrowserControl.exe
    
    Returns:
        bool: True if update process was initiated successfully
    """
    try:
        import sys
        
        # Download new exe to temp
        temp_dir = Path(tempfile.gettempdir()) / "BrowserControl"
        temp_dir.mkdir(exist_ok=True)
        new_exe_path = temp_dir / "BrowserControl_new.exe"
        
        print(f"[INFO] Downloading update from {exe_url}")
        response = requests.get(exe_url, stream=True, timeout=30)
        response.raise_for_status()
        
        with open(new_exe_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        
        print(f"[INFO] Downloaded to {new_exe_path}")
        
        # Get current exe path
        if getattr(sys, 'frozen', False):
            current_exe = sys.executable
        else:
            # Running from source - simulate for testing
            current_exe = Path("C:/BrowserControl/BrowserControl.exe")
        
        current_exe = Path(current_exe)
        backup_exe = current_exe.parent / "BrowserControl_old.exe"
        
        # Debug: Print paths
        print(f"[DEBUG] Current exe: {current_exe}")
        print(f"[DEBUG] Backup exe: {backup_exe}")
        print(f"[DEBUG] New exe: {new_exe_path}")
        
        # Create PowerShell script in C:\BrowserControl for easy manual execution
        install_dir = current_exe.parent
        ps_script = install_dir / "update_browsercontrol.ps1"
        
        ps_content = f"""# BrowserControl Update Script
# This script will replace the old BrowserControl.exe with the new version
# Downloaded from GitHub release

Write-Host "======================================" -ForegroundColor Cyan
Write-Host "BrowserControl Update" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""

$newExe = "{new_exe_path}"
$currentExe = "{current_exe}"
$backupExe = "{backup_exe}"

Write-Host "Waiting 3 seconds for app to close..." -ForegroundColor Yellow
Start-Sleep -Seconds 3

# Check if new exe exists
if (-not (Test-Path $newExe)) {{
    Write-Host "ERROR: New exe not found at $newExe" -ForegroundColor Red
    Write-Host "Update failed!" -ForegroundColor Red
    pause
    exit 1
}}

# Backup current exe
if (Test-Path $currentExe) {{
    Write-Host "Backing up current version..." -ForegroundColor Gray
    try {{
        Move-Item -Path $currentExe -Destination $backupExe -Force
        Write-Host "SUCCESS: Backed up to $backupExe" -ForegroundColor Green
    }} catch {{
        Write-Host "ERROR: Failed to backup - $_" -ForegroundColor Red
        pause
        exit 1
    }}
}} else {{
    Write-Host "WARNING: Current exe not found (may be first install)" -ForegroundColor Yellow
}}

# Copy new exe
Write-Host "Installing new version..." -ForegroundColor Yellow
try {{
    Copy-Item -Path $newExe -Destination $currentExe -Force
    Write-Host "SUCCESS: Installed new version!" -ForegroundColor Green
}} catch {{
    Write-Host "ERROR: Failed to copy new exe - $_" -ForegroundColor Red
    # Try to restore backup
    if (Test-Path $backupExe) {{
        Write-Host "Attempting to restore backup..." -ForegroundColor Yellow
        Move-Item -Path $backupExe -Destination $currentExe -Force
    }}
    pause
    exit 1
}}

# Verify new exe exists
if (Test-Path $currentExe) {{
    Write-Host "SUCCESS: New exe exists at $currentExe" -ForegroundColor Green
}} else {{
    Write-Host "ERROR: New exe does not exist after copy!" -ForegroundColor Red
    pause
    exit 1
}}

# Clean up temp file
if (Test-Path $newExe) {{
    Remove-Item -Path $newExe -Force -ErrorAction SilentlyContinue
    Write-Host "Cleaned up temporary files" -ForegroundColor Gray
}}

Write-Host ""
Write-Host "======================================" -ForegroundColor Cyan
Write-Host "Update Complete!" -ForegroundColor Green
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Restarting BrowserControl..." -ForegroundColor White

# Relaunch the updated application
try {{
    Start-Process -FilePath $currentExe -WorkingDirectory (Split-Path -Path $currentExe)
    Write-Host "Launched BrowserControl" -ForegroundColor Green
}} catch {{
    Write-Host "WARNING: Could not relaunch BrowserControl automatically: $_" -ForegroundColor Yellow
    Write-Host "You can launch it manually from: $currentExe" -ForegroundColor White
}}

Write-Host "Closing update script in 3 seconds..." -ForegroundColor Yellow
Start-Sleep -Seconds 3

# Delete this script after successful update
Remove-Item -Path $PSCommandPath -Force -ErrorAction SilentlyContinue
"""
        
        with open(ps_script, 'w') as f:
            f.write(ps_content)
        
        print(f"[INFO] Created update script: {ps_script}")
        print(f"[INFO] You can run it manually if needed")
        
        # Try to launch PowerShell script automatically
        try:
            subprocess.Popen(
                ['powershell', '-ExecutionPolicy', 'Bypass', '-File', str(ps_script)],
                creationflags=subprocess.CREATE_NEW_CONSOLE
            )
            print(f"[INFO] Update script launched")
        except Exception as e:
            print(f"[WARNING] Could not auto-launch script: {e}")
            print(f"[INFO] Please run manually: {ps_script}")
        
        return True
    
    except Exception as e:
        print(f"[ERROR] Direct update failed: {e}")
        return False

def check_and_prompt_update():
    """
    Check for updates and return information if available.
    
    Returns:
        tuple: (bool, dict or str) 
            - (True, release_info_dict) if update available
            - (False, status_message) if no update or error
    """
    try:
        response = requests.get(UPDATE_CHECK_URL, timeout=5)
        if response.status_code == 200:
            data = response.json()
            latest_version = data.get("tag_name", "").lstrip("v")
            
            if latest_version > VERSION:
                # Update available - get full release info
                release_info = get_latest_release_info()
                if release_info:
                    return (True, release_info)
                else:
                    return (False, "Update available but couldn't fetch details")
            else:
                return (False, "You are on the latest version")
        else:
            return (False, f"Update check failed: HTTP {response.status_code}")
    
    except requests.exceptions.Timeout:
        return (False, "Connection timeout")
    
    except requests.exceptions.ConnectionError:
        return (False, "Connection failed")
    
    except Exception as e:
        return (False, f"Update check error: {str(e)}")
