# chrome.py

import time, win32gui, threading, subprocess, os, pygetwindow as gw
from browser_control import config
from browser_control import state
from browser_control.utils import get_path
from browser_control.launcher import launch_dc, launch_sc, setup_dc, setup_sc
from browser_control.constants import DC_TITLE, SC_TITLE
from selenium.common.exceptions import StaleElementReferenceException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By

def set_window_state(win, state):
    if state == 'maximized':
        print(f"[DEBUG] {win} is being maximized")
        win.maximize()
    elif state == 'minimized':
        print(f"[DEBUG] {win} is being minimized")
        win.minimize()


def launch_dc_thread():
    dc_ready = launch_dc()
    dc_ready.wait(timeout=20)

    all_windows = gw.getAllTitles()
    print("[DEBUG] Current window titles (DC):")
    for title in all_windows:
        print(f"    [DC] {title}")

    for _ in range(50):  # wait up to 5 seconds
        print(f"[DEBUG] Looking for window with title: {DC_TITLE}")

        windows = gw.getWindowsWithTitle(DC_TITLE)
        if windows:
            state.dc_win = windows[0]
            if config.cfg["dc_link"] == "https://dc.byjasco.com/LiveMetrics":
                setup_dc()
            break
        time.sleep(0.1)
    else:
        print(f"[ERROR] Timed out waiting for DC window: {DC_TITLE}")
        return

    set_window_state(state.dc_win, config.cfg["dc_state"])
    state.dc_event.set()

def launch_sc_thread():
    sc_ready = launch_sc()
    sc_ready.wait(timeout=20)

    all_windows = gw.getAllTitles()
    print("[DEBUG] Current window titles (SC):")
    for title in all_windows:
        print(f"    [SC] {title}")

    for _ in range(50):  # wait up to 5 seconds
        print(f"[DEBUG] Looking for window with title: {SC_TITLE}")
        windows = gw.getWindowsWithTitle(SC_TITLE)
        if windows:
            state.sc_win = windows[0]
            state.sc_hwnd = state.sc_win._hWnd
            if config.cfg["sc_link"] == "https://scale20.byjasco.com/RF/SignonMenuRF.aspx":
                setup_sc()
            break
        time.sleep(0.1)
    else:
        print(f"[ERROR] Timed out waiting for SC window: {SC_TITLE}")
        return
    
    set_window_state(state.sc_win, config.cfg["sc_state"])

    state.sc_event.set()

def start_threads():
    threading.Thread(target=launch_sc_thread, daemon=True).start()
    threading.Thread(target=launch_dc_thread, daemon=True).start()

def reorganize_windows():
    response = ""
    status = "error"
    if not state.driver_dc or not state.driver_sc:
        response = "Windows not defined."
        return response, status

    dc_organized = True
    try:
        state.driver_dc.set_window_position(config.cfg['dc_x'], config.cfg['dc_y'])
        state.driver_dc.set_window_size(config.cfg['dc_width'], config.cfg['dc_height'])
        set_window_state(state.dc_win, config.cfg["dc_state"])
    except:
        dc_organized = False

    try:
        state.driver_sc.set_window_position(config.cfg['sc_x'], config.cfg['sc_y'])
        state.driver_sc.set_window_size(config.cfg['sc_width'], config.cfg['sc_height'])
        set_window_state(state.sc_win, config.cfg["sc_state"])
        if dc_organized:
            response = "Windows organized."
            status = "success"
        else:
            response = "DC window not found."
    except:
        if dc_organized:
            response = "SC window not found."
        else:
            response = "Neither window found."
    return response, status

# Helper to run AHK zoom control
def run_ahk_zoom(percent: str):
    status = "error"
    if not state.sc_hwnd:
        return "Scale window not found", status
    
    exe_path = get_path("zoom_control.exe")
    if not os.path.isfile(exe_path):
        return "Zoom control executable not found", status

    loops_map = {
        "100": 2,
        "150": 3,
        "200": 5,
        "250": 6,
        "300": 7
    }

    count = loops_map.get(str(percent))
    if count is None:
        return "Unsupported zoom level", status
    try:
        subprocess.run([exe_path, str(state.sc_hwnd), str(count)], check=True)
        status = "success"
        return f"Zoom set to {percent}%", status
    except subprocess.CalledProcessError as e:
        return f"Zoom failed (exit {e.returncode})",  status
    except Exception as e:
        return f"Zoom failed ({e})", status
    
def select_on_scale(logistics_unit: str, gtin: str):
    if not state.driver_sc:
        return False, "Scale window not running"

    # find the right tab...
    for handle in state.driver_sc.window_handles:
        state.driver_sc.switch_to.window(handle)
        if "DecantProcessing.aspx" not in state.driver_sc.current_url:
            continue

        # locator tuple
        lp_locator = (By.NAME, "txtPalletLP")

        # robust retry loop to always re-find before use
        for attempt in range(3):
            try:
                # wait until the field is present & clickable
                lp_el = WebDriverWait(state.driver_sc, 100).until(
                    EC.element_to_be_clickable(lp_locator)
                )
                lp_el.clear()
                lp_el.send_keys(logistics_unit)
                break
            except StaleElementReferenceException:
                # element went stale before we could use it; retry
                time.sleep(0.1)
        else:
            return False, "Could not set pallet LP (element kept going stale)"
        
        item_locator = (By.NAME, "txtItem")

        # robust retry loop to always re-find before use
        for attempt in range(3):
            try:
                # wait until the field is present & clickable
                item_el = WebDriverWait(state.driver_sc, 100).until(
                    EC.element_to_be_clickable(item_locator)
                )
                item_el.clear()
                item_el.send_keys(gtin)
                break
            except StaleElementReferenceException:
                # element went stale before we could use it; retry
                time.sleep(0.1)
        else:
            return False, "Could not set item (element kept going stale)"
        return True, f"{logistics_unit} entered!"

    return False, "DecantProcessing tab not found"