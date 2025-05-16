# utils.py

from browser_control.constants import UPDATE_CHECK_URL, VERSION, MUTEX_NAME
import requests, win32event, win32api, winerror, sys, os
from ldap3 import Connection, NTLM
import tkinter as tk

def update_available():
    try:
        response = requests.get(UPDATE_CHECK_URL, timeout=5)
        if response.status_code == 200:
            data = response.json()
            latest_version = data.get("tag_name", "").lstrip("v")
            if latest_version > VERSION:
                return True # New version available
            else:
                return False # You are on the latest version
        else:
            return False # Failed to check for updates
    except Exception:
        return False # Update check error
    
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
        import time
        time.sleep(0.5)
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