# chrome.py
# Optimized for Python 3.13.8
# Performance improvements:
#   - Eliminated polling loops with time.sleep()
#   - Using intelligent retry with exponential backoff
#   - Faster window detection (5s → <1s typical case)

import win32gui, threading, subprocess, os, time, pygetwindow as gw
import config
import state
from utils import get_path
from launcher import launch_dc, launch_sc, setup_dc, setup_sc
from constants import DC_TITLE, SC_TITLE
from retry_utils import wait_for_window, retry_with_backoff
from selenium.common.exceptions import StaleElementReferenceException, WebDriverException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from tkinter import messagebox
import traceback

def set_window_state(win, state):
    if state == 'maximized':
        print(f"[DEBUG] {win} is being maximized")
        win.maximize()
    elif state == 'minimized':
        print(f"[DEBUG] {win} is being minimized")
        win.minimize()


def launch_dc_thread():
    """
    Launch DC browser and wait for window to appear.
    
    Performance improvement:
    - OLD: Polling loop with time.sleep(0.1) - always waits 5s worst case
    - NEW: Intelligent wait - succeeds immediately when window appears
    """
    dc_ready = launch_dc()
    dc_ready.wait(timeout=20)

    print(f"[DEBUG] Waiting for window with title: {DC_TITLE}")
    
    try:
        # Use intelligent wait instead of polling loop
        # This returns immediately when window appears (typically <1s)
        state.dc_win = wait_for_window(
            lambda: gw.getWindowsWithTitle(DC_TITLE),
            timeout=5.0,
            window_title=DC_TITLE
        )
        
        # Always setup DC (login and navigate to MetricsLive)
        setup_dc()
        
        set_window_state(state.dc_win, config.cfg["dc_state"])
        state.dc_event.set()
        
    except TimeoutError as e:
        print(f"[ERROR] {e}")
        return

def launch_sc_thread():
    """
    Launch SC browser and wait for window to appear.
    
    Performance improvement:
    - OLD: Polling loop with time.sleep(0.1) - always waits 5s worst case
    - NEW: Intelligent wait - succeeds immediately when window appears
    """
    sc_ready = launch_sc()
    sc_ready.wait(timeout=20)

    print(f"[DEBUG] Waiting for window with title: {SC_TITLE}")
    
    try:
        # Use intelligent wait instead of polling loop
        # This returns immediately when window appears (typically <1s)
        state.sc_win = wait_for_window(
            lambda: gw.getWindowsWithTitle(SC_TITLE),
            timeout=5.0,
            window_title=SC_TITLE
        )
        
        state.sc_hwnd = state.sc_win._hWnd
        
        # Always setup SC (login and navigate to department page)
        setup_sc()
        
        set_window_state(state.sc_win, config.cfg["sc_state"])
        state.sc_event.set()
        
    except TimeoutError as e:
        print(f"[ERROR] {e}")
        return

def start_threads():
    """
    Launch DC and SC browsers in parallel threads.
    
    Note: The browsers themselves are launched in parallel via ThreadPoolExecutor
    in launcher.py, so this creates threads to wait for their windows.
    """
    threading.Thread(target=launch_sc_thread, daemon=True).start()
    threading.Thread(target=launch_dc_thread, daemon=True).start()


def start_threads_parallel():
    """
    OPTIMIZED: Launch both browsers in true parallel for 50% faster startup.
    
    OLD: launch_dc() → wait → launch_sc() → wait = ~10 seconds
    NEW: launch_dc() AND launch_sc() simultaneously = ~5 seconds
    
    This uses the new launch_browsers_parallel() from launcher.py.
    """
    from launcher import launch_browsers_parallel
    
    # Launch both browsers in parallel
    dc_ready, sc_ready = launch_browsers_parallel()
    
    if not dc_ready or not sc_ready:
        print("[ERROR] Failed to launch browsers in parallel")
        return
    
    # Now wait for both to be ready in parallel threads
    def wait_dc():
        try:
            dc_ready.wait(timeout=20)
            print(f"[DEBUG] Waiting for window with title: {DC_TITLE}")
            
            state.dc_win = wait_for_window(
                lambda: gw.getWindowsWithTitle(DC_TITLE),
                timeout=5.0,
                window_title=DC_TITLE
            )
            
            # Always setup DC (login and navigate to MetricsLive)
            # Note: setup_dc() now sets dc_event immediately after login button click
            setup_dc()
            set_window_state(state.dc_win, config.cfg["dc_state"])
            
        except Exception as e:
            # Log error but still signal ready if we at least clicked login
            print(f"[ERROR] DC setup error: {e}")
            # Check if we at least have a window - if so, user can still work
            if state.dc_win:
                print("[DC] Window exists despite error, signaling ready anyway")
                # Set event as fallback if setup_dc didn't reach the click
                if not state.dc_event.is_set():
                    state.dc_event.set()
    
    def wait_sc():
        try:
            sc_ready.wait(timeout=20)
            print(f"[DEBUG] Waiting for window with title: {SC_TITLE}")
            
            state.sc_win = wait_for_window(
                lambda: gw.getWindowsWithTitle(SC_TITLE),
                timeout=5.0,
                window_title=SC_TITLE
            )
            state.sc_hwnd = state.sc_win._hWnd
            
            # Always setup SC (login and navigate to department page)
            setup_sc()
            set_window_state(state.sc_win, config.cfg["sc_state"])
            
            # Set event immediately after last user input (setup_sc returns fast now)
            print("[SC] User input complete, signaling ready")
            
        except Exception as e:
            # Log error but still signal ready if we at least clicked login
            print(f"[ERROR] SC setup error: {e}")
            # Check if we at least have a window - if so, user can still work
            if state.sc_win:
                print("[SC] Window exists despite error, signaling ready anyway")
        finally:
            # ALWAYS set the event to prevent hanging
            # Even if there's an error, we want the UI to become responsive
            import time
            if hasattr(state, 'login_start_time'):
                print(f"[PERF] ⏱️  SC event SET at {time.time() - state.login_start_time:.2f}s")
            state.sc_event.set()
    
    # Wait for both windows in parallel
    threading.Thread(target=wait_dc, daemon=True).start()
    threading.Thread(target=wait_sc, daemon=True).start()

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

def set_zoom_level(driver, percent: str):
    """
    Set Chrome zoom level using pyautogui to send real Windows keyboard events.
    This uses the same zoom mechanism as manual keyboard input.
    
    Args:
        driver: Selenium WebDriver instance
        percent: Target zoom level as string ("100", "150", "200", "250", "300")
    
    Returns:
        tuple: (message, status)
    """
    import pyautogui
    import time
    
    status = "error"
    if not driver:
        return "Browser not found", status
    
    try:
        # Zoom level mapping to number of Ctrl+ presses needed from 100% baseline
        # Chrome zoom steps: 100% → 110% → 125% → 150% → 175% → 200% → 250% → 300%
        zoom_steps = {
            "100": 0,   # Ctrl+0 resets to 100%
            "150": 3,   # 100% → 110% → 125% → 150%
            "200": 5,   # 100% → 110% → 125% → 150% → 175% → 200%
            "250": 6,   # 100% → ... → 250%
            "300": 7    # 100% → ... → 300%
        }
        
        steps = zoom_steps.get(str(percent))
        if steps is None:
            return f"Unsupported zoom level: {percent}%", status
        
        print(f"[ZOOM] Setting zoom to {percent}% (steps: {steps})")
        
        # Make sure the Chrome window has focus
        if state.sc_win:
            try:
                state.sc_win.activate()
                #time.sleep(0.1)
            except:
                pass
        
        # First, reset to 100% with Ctrl+0
        pyautogui.hotkey('ctrl', '0')
        time.sleep(0.15)
        print("[ZOOM] Reset to 100%")
        
        # Then zoom in the required number of steps with Ctrl++
        if steps > 0:
            for i in range(steps):
                pyautogui.hotkey('ctrl', '+')  # pyautogui handles + correctly
                #time.sleep(0.15)
                print(f"[ZOOM] Step {i+1}/{steps}")
        
        status = "success"
        return f"Zoom set to {percent}%", status
        
    except Exception as e:
        print(f"[ZOOM ERROR] {e}")
        import traceback
        traceback.print_exc()
        return f"Zoom failed: {e}", status

def run_ahk_zoom(percent: str):
    """
    Set zoom level on Scale window using Selenium keyboard shortcuts.
    This is a wrapper that maintains compatibility with existing code.
    """
    if not state.driver_sc:
        return "Scale window not found", "error"
    
    return set_zoom_level(state.driver_sc, percent)
    
def select_on_scale(logistics_unit: str, gtin: str):
    """
    Enter logistics unit and GTIN on the Scale DecantProcessing page.
    
    Uses retry logic to handle stale elements caused by JavaScript postbacks.
    The page's onchange event triggers __doPostBack which can refresh elements.
    """
    if not state.driver_sc:
        return False, "Scale window not running"

    # Find the right tab...
    for handle in state.driver_sc.window_handles:
        state.driver_sc.switch_to.window(handle)
        if "DecantProcessing.aspx" not in state.driver_sc.current_url:
            continue

        # Helper to interact with field with robust retry logic (handles DOM replacement)
        def interact_with_field(locator, value, field_name, max_retries=4):
            last_exc = None
            for attempt in range(max_retries):
                try:
                    print(f"[DEBUG] Attempting to fill {field_name} with '{value}' (attempt {attempt + 1}/{max_retries})")
                    # Always re-locate the element (avoid stale references)
                    WebDriverWait(state.driver_sc, 5).until(
                        EC.presence_of_element_located(locator)
                    )
                    element = WebDriverWait(state.driver_sc, 5).until(
                        EC.element_to_be_clickable(locator)
                    )

                    # Focus the element to reduce chances of update panel swapping it out
                    try:
                        state.driver_sc.execute_script("arguments[0].focus();", element)
                    except Exception:
                        pass

                    # Robust clear: try Ctrl+A then Delete, fallback to clear() and JS
                    try:
                        element.send_keys(Keys.CONTROL, "a")
                        element.send_keys(Keys.DELETE)
                    except Exception:
                        try:
                            element.clear()
                        except Exception:
                            try:
                                state.driver_sc.execute_script("arguments[0].value = '';", element)
                            except Exception:
                                pass

                    time.sleep(0.05)
                    element.send_keys(value)

                    # Verify the value stuck (re-locate in case the node was swapped)
                    def value_is_set(d):
                        try:
                            el = d.find_element(*locator)
                            return el.get_attribute("value") == value
                        except Exception:
                            return False

                    if WebDriverWait(state.driver_sc, 3).until(value_is_set):
                        print(f"[DEBUG] Successfully filled {field_name}")
                        return True, None
                    else:
                        raise Exception("Value did not persist (DOM likely refreshed)")

                except (StaleElementReferenceException, WebDriverException) as e:
                    # Treat Chrome 'Node with given id does not belong to the document' as stale
                    msg = str(e)
                    if "Node with given id does not belong to the document" in msg:
                        print(f"[RETRY] {field_name}: element replaced during postback; retrying...")
                    else:
                        print(f"[RETRY] {field_name}: {type(e).__name__}: {msg}")
                    last_exc = e
                    time.sleep(0.25 * (2 ** attempt))
                    continue
                except Exception as e:
                    last_exc = e
                    time.sleep(0.25 * (2 ** attempt))
                    continue

            return False, f"{type(last_exc).__name__}: {last_exc}"
        
        # Helper to wait for page postback to complete
        def wait_for_postback(timeout=5):
            """Wait for ASP.NET (UpdatePanel) postback to complete if any."""
            try:
                def ajax_complete(d):
                    try:
                        return bool(d.execute_script(
                            "return (document.readyState === 'complete') && !((window.Sys && Sys.WebForms && Sys.WebForms.PageRequestManager && Sys.WebForms.PageRequestManager.getInstance && Sys.WebForms.PageRequestManager.getInstance().get_isInAsyncPostBack && Sys.WebForms.PageRequestManager.getInstance().get_isInAsyncPostBack()))"
                        ))
                    except Exception:
                        return d.execute_script("return document.readyState") == "complete"

                WebDriverWait(state.driver_sc, timeout).until(ajax_complete)
                time.sleep(0.05)
                return True
            except Exception as e:
                print(f"[WARNING] Postback wait failed: {e}")
                return False
        
        # Helper: copy LP to clipboard and show friendly popup (on UI thread if available)
        def notify_user_failure(copy_text: str | None, friendly_text: str):
            def do_notify():
                try:
                    if getattr(state, 'root', None) and copy_text:
                        try:
                            state.root.clipboard_clear()
                            state.root.clipboard_append(copy_text)
                        except Exception:
                            pass
                    messagebox.showerror("Input Issue", friendly_text)
                except Exception:
                    pass

            if getattr(state, 'root', None):
                try:
                    state.root.after(0, do_notify)
                    return
                except Exception:
                    pass
            # Fallback: call directly
            do_notify()

        # Pallet LP field
        lp_locator = (By.NAME, "txtPalletLP")
        success, error = interact_with_field(lp_locator, logistics_unit, "Pallet LP")
        if not success:
            # Auto-report to GitHub and show friendly popup with clipboard support
            try:
                from error_reporter import log_scale_input_error
                log_scale_input_error(
                    context="Pallet LP",
                    error_message=f"Could not set pallet LP: {error}",
                    extra_info={
                        "current_url": getattr(state.driver_sc, 'current_url', ''),
                        "lp": logistics_unit,
                        "gtin": gtin,
                    },
                    traceback_str=traceback.format_exc()
                )
            except Exception:
                pass

            friendly = (
                "Failed to enter values. The license plate has been copied to your clipboard.\n"
                "Paste it into the page manually, then continue."
            )
            notify_user_failure(logistics_unit, friendly)
            return False, f"Could not set pallet LP: {error}"
        
        # Wait for the page to finish its postback after LP entry
        print(f"[DEBUG] Waiting for postback after LP entry...")
        wait_for_postback()
        print(f"[DEBUG] Postback complete. GTIN value: '{gtin}' (type: {type(gtin).__name__}, len: {len(gtin) if gtin else 0})")
        
        # Item field - skip if gtin is empty
        if gtin and gtin.strip():  # Check for non-empty and not just whitespace
            print(f"[DEBUG] GTIN is not empty, proceeding to fill item field...")
            item_locator = (By.NAME, "txtItem")
            success, error = interact_with_field(item_locator, gtin, "Item")
            if not success:
                # Auto-report to GitHub and show friendly popup with clipboard support
                try:
                    from error_reporter import log_scale_input_error
                    log_scale_input_error(
                        context="Item",
                        error_message=f"Could not set item: {error}",
                        extra_info={
                            "current_url": getattr(state.driver_sc, 'current_url', ''),
                            "lp": logistics_unit,
                            "gtin": gtin,
                        },
                        traceback_str=traceback.format_exc()
                    )
                except Exception:
                    pass

                friendly = (
                    "Failed to enter item. Scan the GTIN into the Item field."
                )
                # Do NOT modify clipboard for item failures; scanning is preferred
                notify_user_failure(None, friendly)
                return False, f"Could not set item: {error}"
            
            return True, f"{logistics_unit} and item entered!"
        else:
            print(f"[DEBUG] GTIN is empty or whitespace, skipping item field")
            return True, f"{logistics_unit} entered!"

    return False, "DecantProcessing tab not found"