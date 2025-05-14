# browser_control/launcher.py

import threading
import os
import sys
import time
import pygetwindow as gw
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from browser_control.bookmarks import generate_bookmarks
from browser_control.settings import load_settings, save_window_geometry, resource_path
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import StaleElementReferenceException, NoSuchElementException
import subprocess
from threading import Event
import pyautogui
import pyperclip

# Global ZoomControls instance, set after launch
scale_hwnd = None
driver_dc = None
driver_sc = None

def get_path(file):
    # if frozen (running as EXE), look next to the EXE
    if getattr(sys, "frozen", False):
        return os.path.join(os.path.dirname(sys.executable), file)
    # else (running from source), load the one in browser_control/
    return resource_path(file)

def select_on_scale(logistics_unit: str, gtin: str):
    global driver_sc
    if not driver_sc:
        return False, "Scale window not running"

    # find the right tab...
    for handle in driver_sc.window_handles:
        driver_sc.switch_to.window(handle)
        if "DecantProcessing.aspx" not in driver_sc.current_url:
            continue

        # locator tuple
        lp_locator = (By.NAME, "txtPalletLP")

        # robust retry loop to always re-find before use
        for attempt in range(3):
            try:
                # wait until the field is present & clickable
                lp_el = WebDriverWait(driver_sc, 10).until(
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
                item_el = WebDriverWait(driver_sc, 10).until(
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

def close_app():
    global driver_dc, driver_sc, scale_hwnd

    def close_driver(driver, name):
        try:
            if driver:
                print(f"[DEBUG] Closing {name}")
                driver.quit()
        except Exception as e:
            print(f"[ERROR] Failed to close {name}: {e}")

    t1 = threading.Thread(target=close_driver, args=(driver_dc, "DC"), daemon=True)
    t2 = threading.Thread(target=close_driver, args=(driver_sc, "SC"), daemon=True)

    t1.start()
    t2.start()
    t1.join()
    t2.join()

    driver_dc = driver_sc = scale_hwnd = None

def get_window_state(driver, exclude_window=None):
    try:
        pos = driver.get_window_position()
        size = driver.get_window_size()
        target = (pos['x'], pos['y'], size['width'], size['height'])

        for w in gw.getWindowsWithTitle('Google Chrome'):
            if (w.left, w.top, w.width, w.height) == target:
                if exclude_window and w == exclude_window:
                    continue
                if w.isMinimized:
                    print(f"[DEBUG] {w} is minimized")
                    return 'minimized', w
                elif w.isMaximized:
                    print(f"[DEBUG] {w} is maximized")
                    return 'maximized', w
                else:
                    print(f"[DEBUG] {w} is normal")
                    return 'normal', w
        print(f"[DEBUG] can't find other chrome assumption is minimized")
        return 'minimized', None  # Fallback
    except Exception as e:
        print(f"[DEBUG] get_window_state error: {e}")
        return 'unknown', None

def pass_window_geometry(): 
    global driver_dc, driver_sc
    if driver_dc and driver_sc:
        dc_pos = driver_dc.get_window_position()
        dc_size = driver_dc.get_window_size()
        sc_pos = driver_sc.get_window_position()
        sc_size = driver_sc.get_window_size()

        dc_state, dc_win = get_window_state(driver_dc)
        sc_state, _ = get_window_state(driver_sc, exclude_window=dc_win)

        save_window_geometry(
            dc_pos['x'], dc_pos['y'], dc_size['width'], dc_size['height'],
            sc_pos['x'], sc_pos['y'], sc_size['width'], sc_size['height'],
            dc_state, sc_state
        )

def get_profile_path(profile) -> str:
    """
    Returns the absolute path to the Chrome Bookmarks file:
    - Frozen EXE: <same-folder-as-EXE>/profiles/ScaleProfile/Default/Bookmarks
    - Source run: browser_control/profiles/ScaleProfile/Default/Bookmarks
    """
    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(sys.executable)
        return os.path.join(exe_dir, "profiles", profile)
    # running from source: use resource_path to drill into our package
    rel = os.path.join("profiles", profile)
    return resource_path(rel)

# Helper to run AHK credentials
def run_ahk_credentials(hwnd, user, pwd):
    exe_path = get_path("credentials.exe")
    if not os.path.isfile(exe_path):
        print("Credentials executable not found")
    try:
        subprocess.run([exe_path, str(hwnd), str(user), str(pwd)], check=True)
    except subprocess.CalledProcessError as e:
        print(f"Credentials failed (exit {e.returncode})")
    except Exception as e:
        print(f"Credentials failed ({e})")


def launch_dc():
    cfg = load_settings()
    global driver_dc

    chrome_ready = Event()  # <-- signal from thread to main
    driver_holder = {}

    def dc_worker():
        global driver_dc
        try:
            dc_profile = get_profile_path("LiveMetricsProfile")
            os.makedirs(dc_profile, exist_ok=True)

            opts_dc = webdriver.ChromeOptions()
            opts_dc.add_argument(f"--user-data-dir={dc_profile}")
            opts_dc.add_argument("--log-level=3")
            opts_dc.add_experimental_option("excludeSwitches", ["enable-automation"])
            opts_dc.add_experimental_option("useAutomationExtension", False)

            service_dc = Service(ChromeDriverManager().install())
            print("[DEBUG] Starting DC window")
            driver_dc = webdriver.Chrome(service=service_dc, options=opts_dc)
            driver_dc.set_window_position(cfg['dc_x'], cfg['dc_y'])
            driver_dc.set_window_size(cfg['dc_width'], cfg['dc_height'])
            driver_dc.get(cfg['dc_link'])

            WebDriverWait(driver_dc, 10).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )

            driver_dc.execute_script("document.title = 'DC'")

            driver_holder["driver"] = driver_dc
            chrome_ready.set()  # <-- signal main thread
        except Exception as e:
            print(f"[ERROR] DC worker failed: {e}")
            chrome_ready.set()  # still signal to avoid hanging

    threading.Thread(target=dc_worker, daemon=True).start()

    return chrome_ready, driver_holder

def setup_dc(username, password):
    pyperclip.copy(username)
    pyautogui.hotkey("ctrl", "v")
    pyautogui.press("tab")

    pyperclip.copy(password)
    pyautogui.hotkey("ctrl", "v")
    pyautogui.press("enter")
    pyperclip.copy("") # clear password

    WebDriverWait(driver_dc, 10).until(
        lambda d: d.title.startswith("Welcome")
    )
    
    driver_dc.execute_script("window.open('');")
    driver_dc.switch_to.window(driver_dc.window_handles[-1]) # Switch to the new tab
    driver_dc.get("https://dc.byjasco.com/LiveMetrics")

def set_window_state(win, state):
    if state == 'maximized':
        print(f"[DEBUG] {win} is being maximized")
        win.maximize()
    elif state == 'minimized':
        print(f"[DEBUG] {win} is being minimized")
        win.minimize()

def launch_sc(department_var):
    global driver_sc
    cfg = load_settings()

    chrome_ready = Event()  # <-- signal from thread to main
    driver_holder = {}
    
    def sc_worker():
        global driver_sc
        try:  
            # 1. Compute path          
            sc_profile = get_profile_path("ScaleProfile")
            # 2. Make sure it exists
            os.makedirs(sc_profile, exist_ok=True)
            # 3. Tell Chrome to use it
            opts_sc = webdriver.ChromeOptions()
            opts_sc.add_argument(f"--user-data-dir={sc_profile}")
            opts_sc.add_argument("--log-level=3")

            sel = department_var.get()
            # create/prepare profiles & bookmarks
            generate_bookmarks(sel)
            
            service_sc = Service(ChromeDriverManager().install())
            opts_sc.add_experimental_option("excludeSwitches", ["enable-automation"])
            opts_sc.add_experimental_option("useAutomationExtension", False)
            print("[DEBUG] Starting Scale window")
            try:
                driver_sc  = webdriver.Chrome(service=service_sc, options=opts_sc)
            except Exception as e:
                print("Failed to start Scale window:", e)
                return
            driver_sc.set_window_position(cfg['sc_x'], cfg['sc_y'])
            driver_sc.set_window_size(cfg['sc_width'], cfg['sc_height'])
            
            driver_sc.get(cfg['sc_link'])

            WebDriverWait(driver_sc, 10).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
            
            driver_sc.execute_script("document.title = 'SC'")
            driver_holder["driver"] = driver_sc
            chrome_ready.set()  # <-- signal main thread
        except Exception as e:
            print(f"[ERROR] DC worker failed: {e}")
            chrome_ready.set()  # still signal to avoid hanging

    threading.Thread(target=sc_worker, daemon=True).start()

    return chrome_ready, driver_holder

def setup_sc(department_var, dark_mode_var, username, password):
    WebDriverWait(driver_sc, 10).until(
                EC.presence_of_element_located((By.ID, "userNameInput"))
            ).send_keys(username)
    WebDriverWait(driver_sc, 10).until(
                EC.presence_of_element_located((By.ID, "passwordInput"))
            ).send_keys(password)
    WebDriverWait(driver_sc, 10).until(
        EC.element_to_be_clickable((By.ID, "submitButton"))
    ).click()
    
    sel = department_var.get()
    clicked = False
    for _ in range(10):  # try up to 10 times (1 second total)
        try:
            driver_sc.find_element(By.XPATH, "//input[@type='button' and @value='Continue']").click()
            clicked = True
            break
        except NoSuchElementException:
            time.sleep(0.1)

    if not clicked:
        print("No Continue button appeared — maybe already on menu.")

    WebDriverWait(driver_sc, 10).until(
        lambda d: d.current_url.startswith("https://scale20.byjasco.com/RF/SignonMenuRF.aspx")
    )

    if sel.startswith("DECANT.WS"):
        # Go to DecantProcessing
        driver_sc.get("https://scale20.byjasco.com/RF/DecantProcessing.aspx")

        if dark_mode_var.get():
            WebDriverWait(driver_sc, 10).until(
                EC.element_to_be_clickable((By.ID, "btnToggleDarkMode"))
            ).click()

    elif sel.startswith("PalletizingStation"):
        # Go to PalletComplete page
        driver_sc.get("https://scale20.byjasco.com/RF/PalletCompleteRF.aspx")

        # Wait for input box
        WebDriverWait(driver_sc, 10).until(
            EC.presence_of_element_located((By.ID, "txtSlotstaxLoc"))
        )

        # Enter station name
        station_input = driver_sc.find_element(By.ID, "txtSlotstaxLoc")
        station_input.clear()
        station_input.send_keys(sel)

        # Wait for and select "Shipping" from dropdown
        select_elem = Select(driver_sc.find_element(By.ID, "dropdownExecutionMode"))
        select_elem.select_by_visible_text("Shipping")

        # Click "Begin"
        WebDriverWait(driver_sc, 10).until(
            EC.element_to_be_clickable((By.ID, "btnBegin"))
        ).click()

    elif sel.startswith("Packing"):
        driver_sc.get("https://scale20.byjasco.com/scale/trans/packing")

    else:
        print("Unrecognized department:", sel)

    driver_sc.execute_script("window.open('');")
    driver_sc.switch_to.window(driver_sc.window_handles[-1]) # Switch to the new tab
    driver_sc.get("https://scale20.byjasco.com/RF/JPCILaborTrackingRF.aspx")
    WebDriverWait(driver_sc, 10).until(
        lambda d: d.execute_script("return document.readyState") == "complete"
    )

    department_map = {
        "Packing": "Packing",
        "DECANT.WS.1": "Decant",
        "DECANT.WS.2": "Decant",
        "DECANT.WS.3": "Decant",
        "DECANT.WS.4": "Decant",
        "DECANT.WS.5": "Decant",
        "PalletizingStation1": "PalletizingStation1",
        "PalletizingStation2": "PalletizingStation2",
        "PalletizingStation3": "PalletizingStation3"
    }

    selected_ui_value = department_var.get()
    labor_value = department_map.get(selected_ui_value, selected_ui_value)  # fallback just in case

    select_element = Select(driver_sc.find_element(By.ID, "DropDownListDepartment"))
    select_element.select_by_visible_text(labor_value)