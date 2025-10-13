# utils.py

from constants import UPDATE_CHECK_URL, VERSION, MUTEX_NAME
import requests, win32event, win32api, winerror, sys, os

# Fix MD4 hash error for NTLM authentication (Python 3.9+)
# Python 3.13's OpenSSL has MD4 disabled. Use pycryptodome's implementation instead.
import hashlib

# Save original hashlib.new function
_orig_hashlib_new = hashlib.new

def _patched_hashlib_new(name, data=b'', **kwargs):
    """Patched hashlib.new that uses pycryptodome's MD4 when OpenSSL's is unavailable"""
    if name == 'md4':
        try:
            # Try OpenSSL's MD4 first
            return _orig_hashlib_new(name, data, **kwargs)
        except ValueError:
            # Fall back to pycryptodome's MD4
            from Crypto.Hash import MD4
            h = MD4.new()
            if data:
                h.update(data)
            return h
    else:
        return _orig_hashlib_new(name, data, **kwargs)

# Apply the patch
hashlib.new = _patched_hashlib_new

from ldap3 import Connection, NTLM
import tkinter as tk

def update_available():
    """
    Check if an update is available with retry logic.
    
    Returns:
        tuple: (bool, str) - (update_available, status_message)
            - (True, "New version X.X.X available") if update exists
            - (False, "You are on the latest version") if no update
            - (False, "Connection failed: ...") if network error after retries
    """
    max_retries = 3
    timeout = 2  # 2 seconds per attempt (faster failure detection)
    
    for attempt in range(1, max_retries + 1):
        try:
            response = requests.get(UPDATE_CHECK_URL, timeout=timeout)
            if response.status_code == 200:
                data = response.json()
                latest_version = data.get("tag_name", "").lstrip("v")
                if latest_version > VERSION:
                    return (True, f"New version {latest_version} available")
                else:
                    return (False, "You are on the latest version")
            else:
                # Non-200 status code
                if attempt < max_retries:
                    continue  # Retry
                return (False, f"Update check failed: HTTP {response.status_code}")
                
        except requests.exceptions.Timeout:
            if attempt < max_retries:
                continue  # Retry on timeout
            return (False, "Connection failed: Request timed out. Check your internet connection.")
            
        except requests.exceptions.ConnectionError:
            if attempt < max_retries:
                continue  # Retry on connection error
            return (False, "Connection failed: Unable to reach update server. Check your internet connection.")
            
        except Exception as e:
            if attempt < max_retries:
                continue  # Retry on any other error
            return (False, f"Update check error: {str(e)}")
    
    # Should never reach here, but just in case
    return (False, "Update check failed after retries")
    
def ensure_single_instance():
    mutex = win32event.CreateMutex(None, False, MUTEX_NAME)
    if win32api.GetLastError() == winerror.ERROR_ALREADY_EXISTS:
        sys.exit(0)

def resource_path(rel_path):
    # when frozen by PyInstaller, files are unpacked to _MEIPASS
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel_path)

def get_path(file):
    # if frozen (running as EXE), look next to the EXE
    if getattr(sys, "frozen", False):
        return os.path.join(os.path.dirname(sys.executable), file)
    # else (running from source), load the one in browser_control/
    return resource_path(file)

def validate_credentials(username, password, domain="JASCOPRODUCTS"):
    server = "JASDC03"
    user_dn = f"{domain}\\{username}"

    try:
        conn = Connection(server, user=user_dn, password=password, authentication=NTLM)
        if not conn.bind():
            print("Bind failed:", conn.result)
            return False
        print("Bind result:", conn.result)
        print("Last error:", conn.last_error)
        # No need to sleep - LDAP bind is already complete
        conn.unbind()
        return True
    except Exception as e:
        print(f"[ERROR] {e}")
        return False

# flash_msg.py
import tkinter as tk

def flash_message(label: tk.Label,
                  msg_var: tk.StringVar,
                  message: str,
                  status: str = 'normal',
                  duration: int = 500):
    """
    Set msg_var to message, flash the label’s text color:
      • status='success' → yellow
      • status='error'   → red
      • status='normal'  → white
    Then after `duration` ms, reset to white.
    """
    # 1) update text
    msg_var.set(message)

    # 2) pick color
    if status == 'success':
        fg = 'yellow'
    elif status == 'error':
        fg = 'red'
    else:
        fg = 'white'

    # 3) cancel any pending reset
    pending = getattr(label, '_flash_after_id', None)
    if pending:
        label.after_cancel(pending)

    # 4) apply color
    label.config(fg=fg)

    # 5) schedule reset
    def _reset():
        label.config(fg='white')
        label._flash_after_id = None

    label._flash_after_id = label.after(duration, _reset)