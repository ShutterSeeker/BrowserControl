#state.py
import threading

dc_event = threading.Event()
sc_event = threading.Event()
update_available = False
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