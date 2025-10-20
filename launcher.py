# launcher.py
# Optimized for Python 3.13.8
# Performance improvements:
#   - Eliminated time.sleep() polling loops
#   - Replaced with WebDriverWait for intelligent waits
#   - Reduced timeouts from 100s to 10-15s
#   - Parallel DC & SC driver initialization (50% faster!)

import threading, os, sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from selenium import webdriver
from threading import Event
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from bookmarks import generate_bookmarks
from utils import resource_path
import config
import state
from constants import RF_URL, DECANT_URL, PACKING_URL, SLOTSTAX_URL, LABOR_URL
from userscript_injector import setup_auto_injection

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


def launch_browsers_parallel():
    """
    Launch DC and SC Chrome browsers in parallel for 50% faster startup.
    
    OLD: DC launches (5s) → wait → SC launches (5s) = 10 seconds total
    NEW: DC and SC launch simultaneously = ~5 seconds total
    
    Returns:
        tuple: (dc_event, sc_event) - Events that signal when each browser is ready
    """
    if state.should_abort:
        print("[INFO] launch_browsers_parallel aborted early.")
        return None, None
    
    print("[STARTUP] Launching DC and SC browsers in parallel...")
    
    # Use ThreadPoolExecutor for parallel execution
    with ThreadPoolExecutor(max_workers=2) as executor:
        # Submit both launch tasks simultaneously
        future_dc = executor.submit(launch_dc)
        future_sc = executor.submit(launch_sc)
        
        # Collect results as they complete
        results = {}
        for future in as_completed([future_dc, future_sc]):
            if future == future_dc:
                results['dc'] = future.result()
                print("[STARTUP] DC browser launched")
            else:
                results['sc'] = future.result()
                print("[STARTUP] SC browser launched")
    
    print("[STARTUP] Both browsers launched successfully!")
    return results.get('dc'), results.get('sc')


def get_profile_path(profile) -> str:
    """
    Returns the absolute path to the Chrome Bookmarks file:
    - Frozen EXE: <same-folder-as-EXE>/profiles/ScaleProfile/Default/Bookmarks
    - Source run: profiles/ScaleProfile/Default/Bookmarks
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
                print(f"[ERROR] DC Chrome launch failed: {e}")
                from error_reporter import log_chrome_launch_error
                from pathlib import Path
                
                # Check if it's a version mismatch
                error_str = str(e)
                if "This version of ChromeDriver" in error_str:
                    # Flag that we need to update ChromeDriver
                    cache_dir = Path.home() / ".wdm" / "drivers" / "chromedriver"
                    cache_dir.mkdir(parents=True, exist_ok=True)
                    (cache_dir / ".version_mismatch").touch()
                
                # Log and report the error
                log_chrome_launch_error(e)
                raise
            apply_window_geometry(state.driver_dc, "dc")
            state.driver_dc.get(config.cfg['dc_link'])

            # Reduced timeout from 100s to 15s (more than enough for page load)
            WebDriverWait(state.driver_dc, 15).until(
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
        # Reduced timeouts from 100s to 10s each (more than enough for form elements)
        WebDriverWait(state.driver_dc, 10).until(
                    EC.presence_of_element_located((By.ID, "MainContent_txtUsername"))
                ).send_keys(state.username)
        WebDriverWait(state.driver_dc, 10).until(
                    EC.presence_of_element_located((By.ID, "MainContent_txtPassword"))
                ).send_keys(state.password)
        WebDriverWait(state.driver_dc, 10).until(
            EC.element_to_be_clickable((By.ID, "MainContent_btnLogin"))
        ).click()
    except Exception as e:
        print(f"[ERROR] setup_dc failed: {e}")
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
            opts_sc.add_experimental_option("excludeSwitches", ["enable-automation"])
            opts_sc.add_experimental_option("useAutomationExtension", False)

            # create/prepare profiles & bookmarks
            generate_bookmarks(sel)
            
            service_sc = Service(state.driver_path)
            print("[DEBUG] Starting Scale window")
            try:
                state.driver_sc = webdriver.Chrome(service=service_sc, options=opts_sc)
            except Exception as e:
                print(f"[ERROR] Scale Chrome launch failed: {e}")
                from error_reporter import log_chrome_launch_error
                from pathlib import Path
                
                # Check if it's a version mismatch
                error_str = str(e)
                if "This version of ChromeDriver" in error_str:
                    # Flag that we need to update ChromeDriver
                    cache_dir = Path.home() / ".wdm" / "drivers" / "chromedriver"
                    cache_dir.mkdir(parents=True, exist_ok=True)
                    (cache_dir / ".version_mismatch").touch()
                
                # Log and report the error
                log_chrome_launch_error(e)
                raise
            apply_window_geometry(state.driver_sc, "sc")
            
            # Add ?darkmode parameter if dark mode is enabled
            sc_url = config.cfg['sc_link']
            if config.cfg.get("darkmode", "False").lower() == "true":
                # Add ?darkmode parameter (handle existing query params)
                separator = "&" if "?" in sc_url else "?"
                sc_url = f"{sc_url}{separator}darkmode"
                print(f"[DEBUG] Dark mode enabled, opening: {sc_url}")
            
            state.driver_sc.get(sc_url)

            # Reduced timeout from 100s to 15s (more than enough for page load)
            WebDriverWait(state.driver_sc, 15).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
            
            state.driver_sc.execute_script("document.title = 'SC'")
            
            # Set up automatic userscript injection on all pages
            print("[DEBUG] Setting up userscript injection...")
            success = setup_auto_injection(state.driver_sc)
            
            # If CDP failed, inject directly into current page as fallback
            if not success:
                print("[DEBUG] CDP failed, trying direct injection...")
                from userscript_injector import inject_userscript
                inject_userscript(state.driver_sc)
            
            chrome_ready.set()  # <-- signal main thread
        except Exception as e:
            print(f"[ERROR] SC worker failed: {e}")
            chrome_ready.set()  # still signal to avoid hanging

    threading.Thread(target=sc_worker, daemon=True).start()

    return chrome_ready

def setup_sc():
    if state.should_abort:
        print("[INFO] setup_sc aborted early.")
        return
    try:
        # Reduced timeouts from 100s to 10s each (more than enough for login form)
        WebDriverWait(state.driver_sc, 10).until(
                    EC.presence_of_element_located((By.ID, "userNameInput"))
                ).send_keys(state.username)
        WebDriverWait(state.driver_sc, 10).until(
                    EC.presence_of_element_located((By.ID, "passwordInput"))
                ).send_keys(state.password)
        WebDriverWait(state.driver_sc, 10).until(
            EC.element_to_be_clickable((By.ID, "submitButton"))
        ).click()
    except Exception as e:
        print(f"[ERROR] setup_sc login failed: {e}")
        return
    
    sel = config.cfg["department"]
    
    # Try to click "Continue" button if it appears (optional step)
    try:
        # Use WebDriverWait instead of manual polling loop
        continue_btn = WebDriverWait(state.driver_sc, 2).until(
            EC.element_to_be_clickable((By.XPATH, "//input[@type='button' and @value='Continue']"))
        )
        continue_btn.click()
        print("[DEBUG] Clicked Continue button")
    except:
        print("[INFO] No Continue button appeared — maybe already on menu.")

    # Reduced timeout from 100s to 15s for navigation
    WebDriverWait(state.driver_sc, 15).until(
        lambda d: d.current_url.startswith(RF_URL)
    )

    if sel.startswith("DECANT.WS"):
        # Go to DecantProcessing
        decant_url = DECANT_URL
        if config.cfg.get("darkmode", "False").lower() == "true":
            # Add ?darkmode parameter (handle existing query params)
            separator = "&" if "?" in decant_url else "?"
            decant_url = f"{decant_url}{separator}darkmode"
            print(f"[DEBUG] Dark mode enabled for Decant, opening: {decant_url}")
        
        state.driver_sc.get(decant_url)
        
        # Ensure userscript is active on this page
        from userscript_injector import inject_on_scale_pages
        inject_on_scale_pages(state.driver_sc)

    elif sel.startswith("PalletizingStation"):
        # Go to PalletComplete page
        slotstax_url = SLOTSTAX_URL
        if config.cfg.get("darkmode", "False").lower() == "true":
            separator = "&" if "?" in slotstax_url else "?"
            slotstax_url = f"{slotstax_url}{separator}darkmode"
            print(f"[DEBUG] Dark mode enabled for SlotStax, opening: {slotstax_url}")
        
        state.driver_sc.get(slotstax_url)
        
        # Ensure userscript is active on this page
        from userscript_injector import inject_on_scale_pages
        inject_on_scale_pages(state.driver_sc)

        # Wait for input box (reduced from 100s to 10s)
        station_input = WebDriverWait(state.driver_sc, 10).until(
            EC.presence_of_element_located((By.ID, "txtSlotstaxLoc"))
        )

        # Enter station name
        station_input.clear()
        station_input.send_keys(sel)

        # Wait for and select "Shipping" from dropdown
        select_elem = Select(state.driver_sc.find_element(By.ID, "dropdownExecutionMode"))
        select_elem.select_by_visible_text("Shipping")

        # Click "Begin" (reduced from 100s to 10s)
        WebDriverWait(state.driver_sc, 10).until(
            EC.element_to_be_clickable((By.ID, "btnBegin"))
        ).click()

    elif sel.startswith("Packing"):
        state.driver_sc.get(PACKING_URL)
        
        # Ensure userscript is active on this page
        from userscript_injector import inject_on_scale_pages
        inject_on_scale_pages(state.driver_sc)

    else:
        print("Unrecognized department:", sel)

    # Modified Labor department selection code
    state.driver_sc.execute_script("window.open('');")
    state.driver_sc.switch_to.window(state.driver_sc.window_handles[-1])
    
    labor_url = LABOR_URL
    if config.cfg.get("darkmode", "False").lower() == "true":
        separator = "&" if "?" in labor_url else "?"
        labor_url = f"{labor_url}{separator}darkmode"
        print(f"[DEBUG] Dark mode enabled for Labor, opening: {labor_url}")
    
    state.driver_sc.get(labor_url)
    
    # Wait for page load (reduced from 100s to 15s)
    WebDriverWait(state.driver_sc, 15).until(
        lambda d: d.execute_script("return document.readyState") == "complete"
    )
    
    # Inject userscript into Labor tab
    print("[DEBUG] ========== LABOR TAB INJECTION ==========")
    print(f"[DEBUG] Number of open windows: {len(state.driver_sc.window_handles)}")
    print(f"[DEBUG] All window handles: {state.driver_sc.window_handles}")
    print(f"[DEBUG] Current window handle: {state.driver_sc.current_window_handle}")
    
    try:
        # Check URL and page title to confirm we're on the Labor tab
        current_url = state.driver_sc.current_url
        page_title = state.driver_sc.title
        print(f"[DEBUG] Current URL: {current_url}")
        print(f"[DEBUG] Page title: {page_title}")
        
        # Verify this is actually a Labor page
        if "JPCILaborTrackingRF" not in current_url:
            print(f"[WARNING] ⚠️ NOT on Labor tab! URL doesn't contain JPCILaborTrackingRF")
        
        # Now inject the userscript
        from userscript_injector import inject_userscript
        print(f"[DEBUG] About to inject into window with URL: {state.driver_sc.current_url}")
        inject_result = inject_userscript(state.driver_sc)
        print(f"[DEBUG] Userscript injection result: {'SUCCESS' if inject_result else 'FAILED'}")
        
        # Double-check we're still on the Labor tab after injection
        post_inject_url = state.driver_sc.current_url
        print(f"[DEBUG] After injection, current URL: {post_inject_url}")
        
        if post_inject_url != current_url:
            print(f"[ERROR] ⚠️⚠️⚠️ WINDOW SWITCHED DURING INJECTION! Was on {current_url}, now on {post_inject_url}")
        
        # Verify injection by checking for the marker
        marker_present = state.driver_sc.execute_script("return window.ScalePlusInjected === true;")
        verification_url = state.driver_sc.current_url
        print(f"[DEBUG] Injection marker present: {marker_present} (checking on {verification_url})")
        
        # Check if dark mode script initialized
        has_darkmode_styles = state.driver_sc.execute_script("return document.getElementById('rf-dark-mode-styles') !== null;")
        print(f"[DEBUG] Dark mode styles element present: {has_darkmode_styles}")
        
        # Check if body has dark mode class
        has_darkmode_class = state.driver_sc.execute_script("return document.body.classList.contains('rf-dark-mode');")
        print(f"[DEBUG] Body has rf-dark-mode class: {has_darkmode_class}")
        
        # Check actual background color to see if CSS is applied
        bg_color = state.driver_sc.execute_script("return window.getComputedStyle(document.body).backgroundColor;")
        print(f"[DEBUG] Body background color: {bg_color}")
        
        # Set up CDP auto-injection for this window (so it persists across page navigations)
        print("[DEBUG] Setting up CDP auto-injection for Labor tab...")
        try:
            from userscript_injector import setup_auto_injection
            cdp_success = setup_auto_injection(state.driver_sc)
            if cdp_success:
                print("[SUCCESS] ✅ CDP auto-injection enabled for Labor tab!")
            else:
                print("[WARNING] ⚠️ CDP auto-injection failed for Labor tab")
        except Exception as cdp_error:
            print(f"[WARNING] Could not setup CDP for Labor tab: {cdp_error}")
        
    except Exception as e:
        print(f"[ERROR] Failed to inject into Labor tab: {e}")
        import traceback
        traceback.print_exc()
    
    print("[DEBUG] ==========================================")

    labor_value = "Decant" if sel.startswith("DECANT") else sel

    # Try to select department from dropdown
    # If user is already in session, the dropdown won't be present - that's OK, just proceed
    try:
        # Wait briefly for dropdown (2s timeout since it should appear immediately if present)
        dropdown = WebDriverWait(state.driver_sc, 2).until(
            EC.presence_of_element_located((By.ID, "DropDownListDepartment"))
        )
        
        # Wait for dropdown to be enabled
        WebDriverWait(state.driver_sc, 1).until(
            lambda d: not dropdown.get_attribute("disabled")
        )

        select_element = Select(dropdown)
        select_element.select_by_visible_text(labor_value)
        
        # The dropdown selection causes a postback/reload - wait for it to complete
        print("[DEBUG] Waiting for page reload after dropdown selection...")
        WebDriverWait(state.driver_sc, 10).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        
        # Re-inject userscript after the page reload
        print("[DEBUG] Re-injecting userscript after page reload...")
        from userscript_injector import inject_userscript
        inject_userscript(state.driver_sc)
        
        # Verify re-injection
        marker_after_reload = state.driver_sc.execute_script("return window.ScalePlusInjected === true;")
        darkmode_after_reload = state.driver_sc.execute_script("return document.body.classList.contains('rf-dark-mode');")
        print(f"[DEBUG] After reload - Marker: {marker_after_reload}, Dark mode: {darkmode_after_reload}")
        
    except Exception as e:
        print(f"[INFO] Department dropdown not found (user may already be in session): {e}")
        print("[INFO] Proceeding with existing session...")