# browser_control/launcher.py

import threading
import os
import time
import pygetwindow as gw
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from screeninfo import get_monitors
from browser_control.bookmarks import generate_bookmarks
from browser_control.zoom_controls import ZoomControls
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from browser_control.settings import load_settings, save_window_geometry
from selenium.common.exceptions import StaleElementReferenceException

# Global ZoomControls instance, set after launch
zoom_controller = None
scale_hwnd = None
driver_dc = None
driver_sc = None
stop_event = threading.Event()

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
    try:
        if driver_dc:
            driver_dc.quit()
    except: pass
    try:
        if driver_sc:
            driver_sc.quit()
    except: pass
    driver_dc = driver_sc = scale_hwnd = None

def pass_window_geometry():
    global driver_dc, driver_sc
    #print(f"[DEBUG] on_save_settings driver_dc: {driver_dc}, driver_sc: {driver_sc}")
    # if browsers exist, save their geometry
    if driver_dc and driver_sc:
        dc_pos = driver_dc.get_window_position()
        dc_size = driver_dc.get_window_size()
        sc_pos = driver_sc.get_window_position()
        sc_size = driver_sc.get_window_size()
        save_window_geometry(
            dc_pos['x'], dc_pos['y'], dc_size['width'], dc_size['height'],
            sc_pos['x'], sc_pos['y'], sc_size['width'], sc_size['height']
        )
        #print(f"[DEBUG] Geometry saved")


def launch_app(department_var, dark_mode_var, zoom_var):
    """
    Starts the Selenium threads to launch DC and Scale windows.
    After starting, sets the global `zoom_controller` to control zoom.
    """
    global zoom_controller, scale_hwnd, driver_dc, driver_sc
    cfg = load_settings()
    stop_event.clear()

    def _worker():
        #global driver_sc
        global zoom_controller, scale_hwnd, driver_dc, driver_sc
        try:
            # 1. Compute a real, absolute path
            base_dir   = os.path.dirname(os.path.abspath(__file__))
            dc_profile = os.path.join(base_dir, "profiles", "LiveMetricsProfile")
            sc_profile = os.path.join(base_dir, "profiles", "ScaleProfile")

            # 2. Make sure it exists
            os.makedirs(dc_profile, exist_ok=True)
            os.makedirs(sc_profile, exist_ok=True)

            # 3. Tell Chrome to use it
            opts_dc = webdriver.ChromeOptions()
            opts_dc.add_argument(f"--user-data-dir={dc_profile}")

            opts_sc = webdriver.ChromeOptions()
            opts_sc.add_argument(f"--user-data-dir={sc_profile}")

            sel = department_var.get()
            cfg = load_settings()
            
            # create/prepare profiles & bookmarks
            generate_bookmarks(sel)

            # compute window sizes
            mon = get_monitors()[0]
            rw = int(mon.width * 0.25)
            lw = mon.width - rw

            # DC window
            service_dc = Service(ChromeDriverManager().install())
            opts_dc.add_experimental_option("excludeSwitches", ["enable-automation"])
            opts_dc.add_experimental_option("useAutomationExtension", False)
            try:
                driver_dc  = webdriver.Chrome(service=service_dc, options=opts_dc)
            except Exception as e:
                print("Failed to start chrome:", e)
                return
            
            driver_dc.set_window_position(cfg['dc_x'], cfg['dc_y'])
            driver_dc.set_window_size(cfg['dc_width'], cfg['dc_height'])
            driver_dc.get("https://dc.byjasco.com/LiveMetrics")

            # Scale window
            service_sc = Service(ChromeDriverManager().install())
            opts_sc.add_experimental_option("excludeSwitches", ["enable-automation"])
            opts_sc.add_experimental_option("useAutomationExtension", False)
            driver_sc  = webdriver.Chrome(service=service_sc, options=opts_sc)
            driver_sc.set_window_position(cfg['sc_x'], cfg['sc_y'])
            driver_sc.set_window_size(cfg['sc_width'], cfg['sc_height'])
            global scale_hwnd
            pos = driver_sc.get_window_position()
            size = driver_sc.get_window_size()
            #print(f"[DEBUG] Looking for Scale window at {pos}, size {size}")
            for w in gw.getAllWindows():
                #print(f"[DEBUG] Saw window {w.title!r} at ({w.left},{w.top}) size {w.width}×{w.height}")
                if (w.left, w.top, w.width, w.height) == (
                    pos["x"], pos["y"], size["width"], size["height"]
                ):
                    scale_hwnd = w._hWnd
                    #print(f"Scale HWND found: {scale_hwnd}")
                    break
            else:
                print("Could not find Scale window in PyGetWindow")
            driver_sc.get("https://scale20.byjasco.com/RF/SignonMenuRF.aspx")

            # Attach ZoomControls
            zoomer = ZoomControls(driver_sc, zoom_var)
            zoom_controller = zoomer
            #print("Zoom hooked up")

            # wait indefinitely for the Scale sign‑on menu to appear
            while not stop_event.is_set() and "SignonMenuRF.aspx" not in driver_sc.current_url:
                time.sleep(0.5)
            if stop_event.is_set():
                return
            
            try:
                driver_sc.find_element(By.XPATH, "//input[@type='button' and @value='Continue']").click()
            except:
                print("No Continue button appeared — maybe already on menu.")

            WebDriverWait(driver_sc, 10).until(
                lambda d: d.current_url == "https://scale20.byjasco.com/RF/SignonMenuRF.aspx"
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
            #print(f"[DEBUG] launcher end driver_dc: {driver_dc}, driver_sc: {driver_sc}")
        except Exception:
            # swallow any errors on shutdown or network failures
            return
    # Start thread
    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()