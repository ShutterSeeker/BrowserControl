# userscript_updater.py
# Auto-update userscripts from GitHub

import os
import sys
import requests
from utils import resource_path
from constants import USERSCRIPTS, USERSCRIPTS_REPO, USERSCRIPTS_BRANCH, USERSCRIPTS_DIR

def get_userscript_url(script_name: str) -> str:
    """
    Generate GitHub raw URL for a userscript.
    
    Args:
        script_name: Name of the script file (e.g., "OnContainerCloseCopy.user.js")
    
    Returns:
        Full GitHub raw URL
    """
    return f"https://raw.githubusercontent.com/{USERSCRIPTS_REPO}/{USERSCRIPTS_BRANCH}/{script_name}"

def get_userscripts_directory() -> str:
    """Get the absolute path to the userscripts directory."""
    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(sys.executable)
        return os.path.join(exe_dir, USERSCRIPTS_DIR)
    return resource_path(USERSCRIPTS_DIR)

def download_userscript(script_name: str, url: str, timeout: int = 5) -> bool:
    """
    Download a userscript from GitHub.
    
    Args:
        script_name: Name of the script file (e.g., "OnContainerCloseCopy.user.js")
        url: GitHub raw URL
        timeout: Request timeout in seconds
    
    Returns:
        bool: True if download successful
    """
    try:
        print(f"[UPDATE] Checking for updates: {script_name}")
        
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        
        new_content = response.text
        
        # Get local file path
        userscripts_dir = get_userscripts_directory()
        os.makedirs(userscripts_dir, exist_ok=True)
        local_path = os.path.join(userscripts_dir, script_name)
        
        # Check if local file exists and compare
        if os.path.exists(local_path):
            with open(local_path, 'r', encoding='utf-8') as f:
                old_content = f.read()
            
            if old_content == new_content:
                print(f"[UPDATE] {script_name} is up to date")
                return True
            else:
                print(f"[UPDATE] New version found for {script_name}")
        else:
            print(f"[UPDATE] {script_name} not found locally, downloading...")
        
        # Write new content
        with open(local_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        print(f"[UPDATE] ✅ Updated {script_name} ({len(new_content):,} bytes)")
        return True
        
    except requests.exceptions.Timeout:
        print(f"[UPDATE] ⚠️ Timeout downloading {script_name} (offline?)")
        return False
    except requests.exceptions.RequestException as e:
        print(f"[UPDATE] ⚠️ Failed to download {script_name}: {e}")
        return False
    except Exception as e:
        print(f"[UPDATE] ⚠️ Error updating {script_name}: {e}")
        return False

def update_all_userscripts(timeout: int = 5) -> dict:
    """
    Check for updates and download all configured userscripts from GitHub.
    
    Args:
        timeout: Request timeout in seconds
    
    Returns:
        dict: Results with counts of updated, skipped, and failed scripts
    """
    print("[UPDATE] Checking for userscript updates from GitHub...")
    
    results = {
        "updated": 0,
        "skipped": 0,
        "failed": 0,
        "total": len(USERSCRIPTS)
    }
    
    for script_name in USERSCRIPTS:
        url = get_userscript_url(script_name)
        success = download_userscript(script_name, url, timeout)
        if success:
            results["updated"] += 1
        else:
            results["failed"] += 1
    
    if results["failed"] == 0:
        print(f"[UPDATE] ✅ All userscripts checked ({results['updated']}/{results['total']})")
    else:
        print(f"[UPDATE] ⚠️ {results['failed']} script(s) failed to update")
    
    return results

def check_for_updates_silent() -> bool:
    """
    Silently check for updates without printing (for background checks).
    
    Returns:
        bool: True if check completed (regardless of updates found)
    """
    try:
        update_all_userscripts(timeout=3)
        return True
    except Exception:
        return False
