# browser_control/launcher.py
import threading, os, sys, time
from selenium import webdriver
from threading import Event
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from browser_control.bookmarks import generate_bookmarks
from browser_control.utils import resource_path
from browser_control import config
from browser_control import state
from browser_control.constants import RF_URL, DECANT_URL, PACKING_URL, SLOTSTAX_URL, LABOR_URL

def apply_window_geometry(driver, prefix):
    try:
        x = int(config.cfg[f"{prefix}_x"])
        y = int(config.cfg[f"{prefix}_y"])
        width = int(config.cfg[f"{prefix}_width"])
        height = int(config.cfg[f"{prefix}_height"])

        driver.set_window_position(x, y)
        driver.set_window_size(width, height)
        return True
    except Exception as e:
        print(f"[ERROR] apply_window_geometry({prefix}): {e}")
        return False

def close_chrome():
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

def launch_dc():
    if state.should_abort:
        print("[INFO] launch_dc aborted early.")
        return None
    
    chrome_ready = Event()  # <-- signal from thread to main

    def dc_worker():
        try:
            dc_profile = get_profile_path("LiveMetricsProfile")
            os.makedirs(dc_profile, exist_ok=True)

            opts_dc = webdriver.ChromeOptions()
            opts_dc.add_argument(f"--user-data-dir={dc_profile}")
            opts_dc.add_argument("--log-level=3")
            opts_dc.add_experimental_option("excludeSwitches", ["enable-automation"])
            opts_dc.add_experimental_option("useAutomationExtension", False)

            service_dc = Service(state.driver_path)
            print("[DEBUG] Starting DC window")
            try:
                state.driver_dc = webdriver.Chrome(service=service_dc, options=opts_dc)
            except Exception as e:
                print(f"[ERROR] DC Chrome launch failed.", e)
            apply_window_geometry(state.driver_dc, "dc")
            state.driver_dc.get(config.cfg['dc_link'])

            WebDriverWait(state.driver_dc, 100).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )

            state.driver_dc.execute_script("document.title = 'DC'")

            chrome_ready.set()  # <-- signal main thread
        except Exception as e:
            print(f"[ERROR] DC worker failed: {e}")
            chrome_ready.set()  # still signal to avoid hanging

    threading.Thread(target=dc_worker, daemon=True).start()

    return chrome_ready

def setup_dc():
    if state.should_abort:
        print("[INFO] setup_dc aborted early.")
        return
    try:
        WebDriverWait(state.driver_dc, 100).until(
                    EC.presence_of_element_located((By.ID, "MainContent_txtUsername"))
                ).send_keys(state.username)
        WebDriverWait(state.driver_dc, 100).until(
                    EC.presence_of_element_located((By.ID, "MainContent_txtPassword"))
                ).send_keys(state.password)
        WebDriverWait(state.driver_dc, 100).until(
            EC.element_to_be_clickable((By.ID, "MainContent_btnLogin"))
        ).click()
    except:
        return
    
    state.driver_dc.get(config.cfg['dc_link'])
    
def launch_sc():
    if state.should_abort:
        print("[INFO] launch_sc aborted early.")
        return None

    chrome_ready = Event()  # <-- signal from thread to main
    sel = config.cfg["department"]
    
    def sc_worker():
        try:  
            # 1. Compute path          
            sc_profile = get_profile_path("ScaleProfile")
            # 2. Make sure it exists
            os.makedirs(sc_profile, exist_ok=True)
            # 3. Tell Chrome to use it
            opts_sc = webdriver.ChromeOptions()
            opts_sc.add_argument(f"--user-data-dir={sc_profile}")
            opts_sc.add_argument("--log-level=3")

            # create/prepare profiles & bookmarks
            generate_bookmarks(sel)
            
            service_sc = Service(state.driver_path)
            opts_sc.add_experimental_option("excludeSwitches", ["enable-automation"])
            opts_sc.add_experimental_option("useAutomationExtension", False)
            print("[DEBUG] Starting Scale window")
            try:
                state.driver_sc = webdriver.Chrome(service=service_sc, options=opts_sc)
            except Exception as e:
                print(f"[ERROR] DC Chrome launch failed.", e)
            apply_window_geometry(state.driver_sc, "sc")
            
            state.driver_sc.get(config.cfg['sc_link'])

            WebDriverWait(state.driver_sc, 100).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
            
            state.driver_sc.execute_script("document.title = 'SC'")
            chrome_ready.set()  # <-- signal main thread
        except Exception as e:
            print(f"[ERROR] DC worker failed: {e}")
            chrome_ready.set()  # still signal to avoid hanging

    threading.Thread(target=sc_worker, daemon=True).start()

    return chrome_ready

def setup_sc():
    if state.should_abort:
        print("[INFO] setup_sc aborted early.")
        return
    try:
        # Login handling code remains the same
        WebDriverWait(state.driver_sc, 100).until(
                    EC.presence_of_element_located((By.ID, "userNameInput"))
                ).send_keys(state.username)
        WebDriverWait(state.driver_sc, 100).until(
                    EC.presence_of_element_located((By.ID, "passwordInput"))
                ).send_keys(state.password)
        WebDriverWait(state.driver_sc, 100).until(
            EC.element_to_be_clickable((By.ID, "submitButton"))
        ).click()
    except:
        return
    
    sel = config.cfg["department"]
    clicked = False
    for _ in range(10):  # try up to 10 times (1 second total)
        try:
            state.driver_sc.find_element(By.XPATH, "//input[@type='button' and @value='Continue']").click()
            clicked = True
            break
        except:
            time.sleep(0.1)

    if not clicked:
        print("No Continue button appeared — maybe already on menu.")

    WebDriverWait(state.driver_sc, 100).until(
        lambda d: d.current_url.startswith(RF_URL)
    )

    if sel.startswith("DECANT.WS"):
        # Go to DecantProcessing
        state.driver_sc.get(DECANT_URL)

        if config.cfg["darkmode"]:
            WebDriverWait(state.driver_sc, 100).until(
                EC.element_to_be_clickable((By.ID, "btnToggleDarkMode"))
            ).click()

    elif sel.startswith("PalletizingStation"):
        # Go to PalletComplete page
        state.driver_sc.get(SLOTSTAX_URL)

        # Wait for input box
        WebDriverWait(state.driver_sc, 100).until(
            EC.presence_of_element_located((By.ID, "txtSlotstaxLoc"))
        )

        # Enter station name
        station_input = state.driver_sc.find_element(By.ID, "txtSlotstaxLoc")
        station_input.clear()
        station_input.send_keys(sel)

        # Wait for and select "Shipping" from dropdown
        select_elem = Select(state.driver_sc.find_element(By.ID, "dropdownExecutionMode"))
        select_elem.select_by_visible_text("Shipping")

        # Click "Begin"
        WebDriverWait(state.driver_sc, 100).until(
            EC.element_to_be_clickable((By.ID, "btnBegin"))
        ).click()

    elif sel.startswith("Packing"):
        state.driver_sc.get(PACKING_URL)

    else:
        print("Unrecognized department:", sel)

    # Modified Labor department selection code
    state.driver_sc.execute_script("window.open('');")
    state.driver_sc.switch_to.window(state.driver_sc.window_handles[-1])
    state.driver_sc.get(LABOR_URL)
    
    # Wait for page load
    WebDriverWait(state.driver_sc, 100).until(
        lambda d: d.execute_script("return document.readyState") == "complete"
    )

    labor_value = "Decant" if sel.startswith("DECANT") else sel

    # Wait for dropdown to be present and enabled
    dropdown = WebDriverWait(state.driver_sc, 100).until(
        EC.presence_of_element_located((By.ID, "DropDownListDepartment"))
    )
    
    # Wait for dropdown to be enabled
    WebDriverWait(state.driver_sc, 100).until(
        lambda d: not dropdown.get_attribute("disabled")
    )

    select_element = Select(dropdown)
    select_element.select_by_visible_text(labor_value)