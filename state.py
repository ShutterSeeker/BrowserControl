#state.py
import threading

dc_event = threading.Event()
sc_event = threading.Event()
update_available = False
update_message = "Checking for updates..."  # Status message for update check
username = None
password = None
driver_dc = None
driver_sc = None
dc_win = None
sc_win = None
sc_hwnd = None
driver_path = None
root = None
should_abort = False
department_var = None
zoom_var = None
notebook = None
tools_frame = None
click_blocker = None
relaunched = False
settings_frame = None  # Reference to settings tab for refreshing after login
logged_in = False  # Track login state for user-specific settings