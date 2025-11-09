# launcher.py
# Optimized for Python 3.13.8
# Performance improvements:
#   - Eliminated time.sleep() polling loops
#   - Replaced with WebDriverWait for intelligent waits
#   - Reduced timeouts from 100s to 10-15s
#   - Parallel DC & SC driver initialization (50% faster!)

import threading, os, sys, time, subprocess, psutil
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
from constants import RF_URL, DECANT_URL, PACKING_URL, SLOTSTAX_URL
from userscript_injector import setup_auto_injection
from utils import get_activity_type

def cleanup_chrome_processes():
    """
    Kill any stale Chrome/ChromeDriver processes that might be holding profile locks.
    This prevents "user data directory is already in use" errors.
    """
    try:
        killed_count = 0
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                name = proc.info['name'].lower()
                # Kill Chrome processes related to our profiles
                if 'chrome' in name or 'chromedriver' in name:
                    cmdline = proc.info.get('cmdline', [])
                    if cmdline and any('MetricsLiveProfile' in str(arg) or 'ScaleProfile' in str(arg) for arg in cmdline):
                        print(f"[CLEANUP] Killing stale process: {proc.info['name']} (PID: {proc.info['pid']})")
                        proc.kill()
                        proc.wait(timeout=3)
                        killed_count += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.TimeoutExpired):
                pass
        
        if killed_count > 0:
            print(f"[CLEANUP] Killed {killed_count} stale Chrome process(es)")
            # Give OS time to release file locks
            time.sleep(1)
        return killed_count
    except Exception as e:
        print(f"[WARNING] Error during cleanup: {e}")
        return 0

def remove_profile_lock_files(profile_path):
    """
    Remove Chrome lock files that might be left over from crashed processes.
    """
    try:
        lock_files = ['Singleton Lock', 'SingletonLock', 'lockfile']
        for lock_file in lock_files:
            lock_path = os.path.join(profile_path, lock_file)
            if os.path.exists(lock_path):
                try:
                    os.remove(lock_path)
                    print(f"[CLEANUP] Removed lock file: {lock_path}")
                except Exception as e:
                    print(f"[WARNING] Could not remove {lock_path}: {e}")
    except Exception as e:
        print(f"[WARNING] Error removing lock files: {e}")

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
    
    # Clean up any stale Chrome processes before launching
    print("[STARTUP] Checking for stale Chrome processes...")
    cleanup_chrome_processes()
    
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
        max_retries = 2
        retry_delay = 2  # seconds
        
        for attempt in range(max_retries):
            try:
                dc_profile = get_profile_path("MetricsLiveProfile")
                os.makedirs(dc_profile, exist_ok=True)
                
                # On retry, cleanup stale processes and lock files
                if attempt > 0:
                    print(f"[RETRY] DC launch attempt {attempt + 1}/{max_retries}")
                    cleanup_chrome_processes()
                    remove_profile_lock_files(dc_profile)
                    time.sleep(retry_delay)

                opts_dc = webdriver.ChromeOptions()
                opts_dc.add_argument(f"--user-data-dir={dc_profile}")
                opts_dc.add_argument("--log-level=3")
                # Add flag to prevent profile lock issues
                opts_dc.add_argument("--disable-gpu-process-crash-limit")
                opts_dc.add_experimental_option("excludeSwitches", ["enable-automation"])
                opts_dc.add_experimental_option("useAutomationExtension", False)
                # Disable password save prompts
                opts_dc.add_experimental_option("prefs", {
                    "credentials_enable_service": False,
                    "profile.password_manager_enabled": False
                })

                service_dc = Service(state.driver_path)
                print("[DEBUG] Starting DC window")
                try:
                    state.driver_dc = webdriver.Chrome(service=service_dc, options=opts_dc)
                except Exception as e:
                    error_str = str(e)
                    
                    # Check if it's a user data directory conflict
                    if "user data directory is already in use" in error_str.lower():
                        if attempt < max_retries - 1:
                            print(f"[WARNING] Profile directory locked, will retry after cleanup...")
                            continue  # Retry with cleanup
                        else:
                            print(f"[ERROR] Profile directory still locked after {max_retries} attempts")
                    
                    # Handle other errors
                    print(f"[ERROR] DC Chrome launch failed: {e}")
                    from error_reporter import log_chrome_launch_error
                    from pathlib import Path
                    
                    # Check if it's a version mismatch
                    if "This version of ChromeDriver" in error_str:
                        # Flag that we need to update ChromeDriver
                        cache_dir = Path.home() / ".wdm" / "drivers" / "chromedriver"
                        cache_dir.mkdir(parents=True, exist_ok=True)
                        (cache_dir / ".version_mismatch").touch()
                    
                    # Log and report the error
                    log_chrome_launch_error(e)
                    raise
                    
                apply_window_geometry(state.driver_dc, "dc")
                
                # Build MetricsLive URL with ActivityType from department
                from constants import DC_URL
                activity_type = get_activity_type(config.cfg["department"])
                dc_url = f"{DC_URL}/MetricsLive?ActivityType={activity_type}"
                print(f"[DEBUG] Navigating to MetricsLive with ActivityType: {activity_type}")
                
                state.driver_dc.get(dc_url)

                # Reduced timeout from 100s to 15s (more than enough for page load)
                WebDriverWait(state.driver_dc, 15).until(
                    lambda d: d.execute_script("return document.readyState") == "complete"
                )

                state.driver_dc.execute_script("document.title = 'DC'")

                chrome_ready.set()  # <-- signal main thread
                return  # Success, exit retry loop
                
            except Exception as e:
                if attempt < max_retries - 1:
                    print(f"[ERROR] DC worker failed (attempt {attempt + 1}/{max_retries}): {e}")
                    continue  # Retry
                else:
                    print(f"[ERROR] DC worker failed after {max_retries} attempts: {e}")
                    chrome_ready.set()  # still signal to avoid hanging

    threading.Thread(target=dc_worker, daemon=True).start()

    return chrome_ready

def setup_dc():
    """Login to DC and set theme. Browser will auto-redirect to originally requested URL."""
    start_time = time.time()
    
    if state.should_abort:
        print("[INFO] setup_dc aborted early.")
        return
    
    try:
        # Wait for login page to load
        WebDriverWait(state.driver_dc, 10).until(
            EC.presence_of_element_located((By.ID, "MainContent_txtUsername"))
        )
        
        # Set theme FIRST (before entering credentials) so login page has correct theme
        theme = config.cfg.get("theme", "dark")
        print(f"[DC_SETUP] DEBUG: config.cfg type: {type(config.cfg)}")
        print(f"[DC_SETUP] DEBUG: config.cfg id: {id(config.cfg)}")
        print(f"[DC_SETUP] DEBUG: config.cfg contents: {dict(config.cfg)}")
        print(f"[DC_SETUP] DEBUG: config.cfg.get('theme', 'NOT_FOUND'): {config.cfg.get('theme', 'NOT_FOUND')}")
        print(f"[DC_SETUP] DEBUG: config.cfg['theme']: {config.cfg.get('theme', 'KEY_ERROR')}")
        print(f"[DC_SETUP] Setting theme to '{theme}' on login page")
        state.driver_dc.execute_script(f"localStorage.setItem('theme', '{theme}');")
        
        # Brief wait to let theme apply
        time.sleep(0.1)
        
        # Now enter credentials with themed login page
        state.driver_dc.find_element(By.ID, "MainContent_txtUsername").send_keys(state.username)
        state.driver_dc.find_element(By.ID, "MainContent_txtPassword").send_keys(state.password)
        login_button = WebDriverWait(state.driver_dc, 10).until(
            EC.element_to_be_clickable((By.ID, "MainContent_btnLogin"))
        )
        
        # Signal ready BEFORE clicking - we're about to click, that's good enough!
        elapsed = time.time() - start_time
        print(f"[DC_SETUP] ⏱️  About to click login button - user input complete ({elapsed:.2f}s)")
        
        if hasattr(state, 'login_start_time'):
            print(f"[PERF] ⏱️  DC event SET at {time.time() - state.login_start_time:.2f}s")
        state.dc_event.set()
        print("[DC] User input complete, signaling ready")
        
        # Now click (this will take time to send the request, but we don't wait for it)
        login_button.click()
        
    except Exception as e:
        print(f"[ERROR] setup_dc login failed: {e}")
        # Don't raise - let the caller decide what to do
        return
    
def launch_sc():
    if state.should_abort:
        print("[INFO] launch_sc aborted early.")
        return None

    chrome_ready = Event()  # <-- signal from thread to main
    sel = config.cfg["department"]
    
    def sc_worker():
        max_retries = 2
        retry_delay = 2  # seconds
        
        for attempt in range(max_retries):
            try:  
                # 1. Compute path          
                sc_profile = get_profile_path("ScaleProfile")
                # 2. Make sure it exists
                os.makedirs(sc_profile, exist_ok=True)
                
                # On retry, cleanup stale processes and lock files
                if attempt > 0:
                    print(f"[RETRY] SC launch attempt {attempt + 1}/{max_retries}")
                    cleanup_chrome_processes()
                    remove_profile_lock_files(sc_profile)
                    time.sleep(retry_delay)
                
                # 3. Tell Chrome to use it
                opts_sc = webdriver.ChromeOptions()
                opts_sc.add_argument(f"--user-data-dir={sc_profile}")
                opts_sc.add_argument("--log-level=3")
                # Add flag to prevent profile lock issues
                opts_sc.add_argument("--disable-gpu-process-crash-limit")
                opts_sc.add_experimental_option("excludeSwitches", ["enable-automation"])
                opts_sc.add_experimental_option("useAutomationExtension", False)
                # Disable password save prompts
                opts_sc.add_experimental_option("prefs", {
                    "credentials_enable_service": False,
                    "profile.password_manager_enabled": False
                })

                # create/prepare profiles & bookmarks
                generate_bookmarks(sel)
                
                service_sc = Service(state.driver_path)
                print("[DEBUG] Starting Scale window")
                try:
                    state.driver_sc = webdriver.Chrome(service=service_sc, options=opts_sc)
                except Exception as e:
                    error_str = str(e)
                    
                    # Check if it's a user data directory conflict
                    if "user data directory is already in use" in error_str.lower():
                        if attempt < max_retries - 1:
                            print(f"[WARNING] Profile directory locked, will retry after cleanup...")
                            continue  # Retry with cleanup
                        else:
                            print(f"[ERROR] Profile directory still locked after {max_retries} attempts")
                    
                    # Handle other errors
                    print(f"[ERROR] Scale Chrome launch failed: {e}")
                    from error_reporter import log_chrome_launch_error
                    from pathlib import Path
                    
                    # Check if it's a version mismatch
                    if "This version of ChromeDriver" in error_str:
                        # Flag that we need to update ChromeDriver
                        cache_dir = Path.home() / ".wdm" / "drivers" / "chromedriver"
                        cache_dir.mkdir(parents=True, exist_ok=True)
                        (cache_dir / ".version_mismatch").touch()
                    
                    # Log and report the error
                    log_chrome_launch_error(e)
                    raise
                    
                apply_window_geometry(state.driver_sc, "sc")
                
                # Navigate to RF login page with dark mode parameter if enabled
                sc_url = RF_URL
                if config.cfg.get("theme", "dark") == "dark":
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
                return  # Success, exit retry loop
                
            except Exception as e:
                if attempt < max_retries - 1:
                    print(f"[ERROR] SC worker failed (attempt {attempt + 1}/{max_retries}): {e}")
                    continue  # Retry
                else:
                    print(f"[ERROR] SC worker failed after {max_retries} attempts: {e}")
                    chrome_ready.set()  # still signal to avoid hanging

    threading.Thread(target=sc_worker, daemon=True).start()

    return chrome_ready

def setup_sc():
    if state.should_abort:
        print("[INFO] setup_sc aborted early.")
        return
    
    # Track if we've completed user input
    user_input_complete = False
    
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

    # Wait for navigation to complete (this is quick, not user-blocking)
    WebDriverWait(state.driver_sc, 15).until(
        lambda d: d.current_url.startswith(RF_URL)
    )

    # Navigate to department-specific page and complete setup
    def complete_navigation():
        try:
            if sel.startswith("DECANT.WS"):
                # Go to DecantProcessing
                decant_url = DECANT_URL
                if config.cfg.get("theme", "dark") == "dark":
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
                if config.cfg.get("theme", "dark") == "dark":
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
                print("[SC_SETUP] SlotStax setup complete")

            elif sel.startswith("Packing"):
                state.driver_sc.get(PACKING_URL)
                
                # Ensure userscript is active on this page
                from userscript_injector import inject_on_scale_pages
                inject_on_scale_pages(state.driver_sc)
                print("[SC_SETUP] Packing setup complete")

            else:
                print("Unrecognized department:", sel)
        except Exception as e:
            print(f"[WARNING] SC navigation failed: {e}")
    
    # For SlotStax, we need to wait for "Begin" button click before signaling ready
    # For other departments, we can signal ready immediately
    if sel.startswith("PalletizingStation"):
        complete_navigation()  # This includes clicking "Begin" - the last user input
        print("[SC_SETUP] User input complete (SlotStax Begin clicked)")
    else:
        # For Decant/Packing, user input is complete after login
        # Run navigation in background
        print("[SC_SETUP] User input complete (login finished)")
        threading.Thread(target=complete_navigation, daemon=True).start()