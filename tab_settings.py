import tkinter as tk
from tkinter import ttk
import config, state
import requests
import threading
from constants import DEPARTMENTS, ZOOM_OPTIONS, IP, PORT
from settings import save_settings, save_window_geometry
from utils import flash_message
from tab_tools import build_tools_tab
from updater import check_and_prompt_update, install_update_direct

def build_settings_tab(parent):
    frame = tk.Frame(parent, bg="#2b2b2b", padx=10, pady=10)

    # Top message label
    msg_var = tk.StringVar(value="Change settings below")
    msg_lbl = tk.Label(frame, textvariable=msg_var, fg="white", bg="#2b2b2b")
    msg_lbl.grid(row=0, column=0, columnspan=2, pady=(0, 5), sticky="ew")

    # Bound variables from config (computer-level)
    department_var = state.department_var
    
    # User-specific settings (if logged in)
    user_zoom_var = tk.StringVar()
    user_dark_var = tk.BooleanVar()
    
    # Flag to prevent auto-save during initial load
    loading_user_settings = {'value': False}

    # Department dropdown (computer-level)
    tk.Label(frame, text="Location", bg="#2b2b2b", fg="white").grid(row=1, column=0, sticky="w", pady=5)
    dept_cb = ttk.Combobox(frame, textvariable=department_var, values=DEPARTMENTS, state="readonly")
    dept_cb.grid(row=1, column=1, sticky="ew", padx=5)

    # User-specific settings section (created dynamically after login)
    user_settings_frame = None
    zoom_cb = None
    dark_cb = None
    
    # Check for updates button (shown only when not logged in)
    check_updates_btn = None

    # Load user settings UI (data already loaded at login time)
    def load_user_settings():
        nonlocal user_settings_frame, zoom_cb, dark_cb, check_updates_btn
        
        if not state.logged_in or not state.username:
            # Remove user settings if they exist
            if user_settings_frame:
                user_settings_frame.destroy()
                user_settings_frame = None
                zoom_cb = None
                dark_cb = None
            
            # Show check for updates button when not logged in
            if check_updates_btn:
                check_updates_btn.grid()
            return
            
        # Read from already-populated state/config (loaded at login time)
        # IMPORTANT: Set values WITHOUT triggering trace callbacks
        loading_user_settings['value'] = True
        
        try:
            # Set values without triggering saves
            user_zoom_var.set(state.zoom_var.get())
            user_dark_var.set(config.cfg.get("theme", "dark") == "dark")
            print(f"[SETTINGS] Loaded UI: theme={config.cfg.get('theme')}, zoom={state.zoom_var.get()}")
        finally:
            loading_user_settings['value'] = False
        
        # Create user settings controls if they don't exist
        if not user_settings_frame:
            user_settings_frame = tk.Frame(frame, bg="#2b2b2b")
            user_settings_frame.grid(row=2, column=0, columnspan=2, pady=(10, 0), sticky="ew")
            
            # Zoom dropdown (user-level)
            zoom_frame = tk.Frame(user_settings_frame, bg="#2b2b2b")
            zoom_frame.pack(fill="x", pady=5)
            tk.Label(zoom_frame, text="Zoom %", bg="#2b2b2b", fg="white").pack(side="left", padx=(0, 10))
            zoom_cb = ttk.Combobox(zoom_frame, textvariable=user_zoom_var, values=ZOOM_OPTIONS, state="readonly", width=10)
            zoom_cb.pack(side="left")
            
            # Dark mode checkbox (user-level)
            dark_cb = tk.Checkbutton(
                user_settings_frame, text="Dark mode",
                variable=user_dark_var,
                bg="#2b2b2b", fg="white", selectcolor="#2b2b2b"
            )
            dark_cb.pack(pady=5)
        
        # Hide check for updates button when logged in
        if check_updates_btn:
            check_updates_btn.grid_remove()
    
    # Apply theme changes to live browser sessions
    def apply_theme_to_browsers(theme):
        """
        Apply theme changes to both DC and SC browsers immediately.
        - DC: Update localStorage 'theme' and refresh page
        - SC: Update sessionStorage 'rfDarkMode' to 'enabled' or 'disabled'
        """
        try:
            # Update DC browser (localStorage + refresh)
            if state.driver_dc:
                try:
                    state.driver_dc.execute_script(f"localStorage.setItem('theme', '{theme}');")
                    state.driver_dc.refresh()
                    print(f"[SETTINGS] Applied theme '{theme}' to DC and refreshed")
                except Exception as e:
                    print(f"[WARNING] Failed to apply theme to DC: {e}")
            
            # Update SC browser (sessionStorage + remove ?darkmode from URL)
            if state.driver_sc:
                try:
                    rf_dark_mode = 'enabled' if theme == 'dark' else 'disabled'
                    state.driver_sc.execute_script(f"sessionStorage.setItem('rfDarkMode', '{rf_dark_mode}');")
                    
                    # Remove ?darkmode from URL if present (userscript resets cache on this param)
                    current_url = state.driver_sc.current_url
                    if '?darkmode' in current_url:
                        clean_url = current_url.replace('?darkmode', '')
                        state.driver_sc.get(clean_url)
                        print(f"[SETTINGS] Removed ?darkmode from URL and navigated to: {clean_url}")
                    else:
                        state.driver_sc.refresh()
                    
                    print(f"[SETTINGS] Applied rfDarkMode '{rf_dark_mode}' to SC")
                except Exception as e:
                    print(f"[WARNING] Failed to apply theme to SC: {e}")
                    
        except Exception as e:
            print(f"[ERROR] Failed to apply theme to browsers: {e}")
    
    # Save user settings to database
    def save_user_settings():
        if not state.logged_in or not state.username:
            return
            
        try:
            theme = "dark" if user_dark_var.get() else "light"
            zoom = user_zoom_var.get()
            
            resp = requests.post(
                f"http://{IP}:{PORT}/update_user_settings",
                json={"username": state.username, "theme": theme, "zoom": zoom},
                timeout=5
            )
            resp.raise_for_status()
            
            # Update runtime config and state
            state.zoom_var.set(zoom)
            config.cfg["theme"] = theme
            config.cfg["zoom_var"] = zoom
            
            # Update cache so next login uses new settings
            state.user_settings_cache[state.username] = {
                "theme": theme,
                "zoom": zoom
            }
            
            # Apply theme changes to live browser sessions
            apply_theme_to_browsers(theme)
            
            flash_message(msg_lbl, msg_var, "User settings saved", status='success')
        except Exception as e:
            flash_message(msg_lbl, msg_var, f"Error saving user settings", status='error')
            print(f"[ERROR] Failed to save user settings: {e}")

    # Auto-update department (computer-level)
    def update_department(*_):
        try:
            if config.cfg["department"] != department_var.get():
                config.cfg["department"] = department_var.get()
                # Only rebuild Tools tab if it exists and is currently in the notebook
                if state.tools_frame:
                    try:
                        # Check if the tools_frame is still managed by the notebook
                        if state.tools_frame in state.notebook.tabs():
                            state.notebook.forget(state.tools_frame)
                            tools_tab = build_tools_tab()
                            state.notebook.add(tools_tab, text="Tools")
                    except tk.TclError:
                        # Tools tab was already removed (e.g., after logout)
                        # Just update the config without rebuilding the tab
                        pass
            save_settings()
            flash_message(msg_lbl, msg_var, "Location updated", status='success')
        except Exception as e:
            flash_message(msg_lbl, msg_var, "Error saving location", status='error')
            print(f"[ERROR] Save settings error: {e}")

    # Auto-update user settings (user-level)
    def update_user_cfg(*_):
        # Don't save if we're just loading initial values
        if not loading_user_settings['value']:
            save_user_settings()

    department_var.trace_add("write", update_department)
    user_zoom_var.trace_add("write", update_user_cfg)
    user_dark_var.trace_add("write", update_user_cfg)

    def on_save_window_geometry():
        try:
            save_window_geometry()
            flash_message(msg_lbl, msg_var, "Position saved!", status='success')
        except:
            flash_message(msg_lbl, msg_var, "Error saving window position", status='error')

    ttk.Button(frame, text="Save position", command=on_save_window_geometry).grid(row=4, column=0, columnspan=2, pady=5)
    
    # Check for updates button (only shown when not logged in)
    def on_check_for_updates():
        """Check for updates and auto-install if found"""
        nonlocal check_updates_btn
        
        # Disable button during check
        check_updates_btn.config(state="disabled", text="Checking...")
        
        def check_and_install():
            try:
                # Check for updates
                update_available, result = check_and_prompt_update()
                
                if update_available:
                    # Update is available - show status and start download
                    state.root.after(0, lambda: check_updates_btn.config(text="Downloading..."))
                    state.root.after(0, lambda: flash_message(msg_lbl, msg_var, f"Update found: v{result['version']}", status='success'))
                    
                    # Install the update
                    if install_update_direct(result['exe_url']):
                        # Exit silently to allow PowerShell script to proceed
                        def exit_app():
                            import sys
                            sys.exit(0)
                        
                        state.root.after(0, exit_app)
                        return
                    else:
                        # Installation failed
                        state.root.after(0, lambda: flash_message(msg_lbl, msg_var, "Update installation failed", status='error'))
                        state.root.after(0, lambda: check_updates_btn.config(state="normal", text="Check for updates"))
                else:
                    # No update available or error
                    state.root.after(0, lambda: flash_message(msg_lbl, msg_var, result, status='normal'))
                    state.root.after(0, lambda: check_updates_btn.config(state="normal", text="Check for updates"))
                    
            except Exception as e:
                state.root.after(0, lambda: flash_message(msg_lbl, msg_var, f"Update check failed: {str(e)}", status='error'))
                state.root.after(0, lambda: check_updates_btn.config(state="normal", text="Check for updates"))
        
        # Run check in background thread
        threading.Thread(target=check_and_install, daemon=True).start()
    
    check_updates_btn = ttk.Button(frame, text="Check for updates", command=on_check_for_updates)
    check_updates_btn.grid(row=5, column=0, columnspan=2, pady=5)
    
    # Hide the button initially if user is logged in
    if state.logged_in:
        check_updates_btn.grid_remove()

    frame.columnconfigure(0, weight=1)
    frame.columnconfigure(1, weight=1)
    
    # Store reference for refreshing after login
    state.settings_frame = frame
    frame.load_user_settings = load_user_settings
    
    # Load user settings if already logged in
    load_user_settings()

    return frame