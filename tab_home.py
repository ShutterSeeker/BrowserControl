# tab_home.py
# Home tab with login and browser control

# Standard library imports
import tkinter as tk
from tkinter import ttk, messagebox
import tkinter.font as tkfont
import threading
import os
import shutil
import json
import webbrowser
import subprocess
from functools import partial

# Third-party imports
import win32gui
import requests

# Local imports
import state
import config
import tab_tools
from chrome import start_threads_parallel, reorganize_windows, run_ahk_zoom
from utils import validate_credentials, flash_message, get_path
from constants import USER_FILE
from updater import get_latest_release_info, install_update_direct

def disable_all_clicks():
    if state.click_blocker is not None:
        return  # already exists

    blocker = tk.Frame(state.root, bg="", highlightthickness=0, bd=0)
    blocker.place(relx=0, rely=0, relwidth=1, relheight=1)

    for seq in ("<ButtonPress>", "<ButtonRelease>", "<Motion>"):
        blocker.bind(seq, lambda e: "break")

    state.click_blocker = blocker

def enable_all_clicks():
    if state.click_blocker:
        state.click_blocker.destroy()
        state.click_blocker = None

def close_chrome():
    """Close both Chrome windows. This function should be called in a background thread."""
    def close_dc():
        if state.driver_dc:
            try: 
                state.driver_dc.quit()
            except: 
                pass
        state.driver_dc = None
        state.dc_event.clear()
        state.dc_win = None

    def close_sc():
        if state.driver_sc:
            try: 
                state.driver_sc.quit()
            except: 
                pass
        state.driver_sc = None
        state.sc_event.clear()
        state.sc_win = None
        state.sc_hwnd = None

    # Close both in parallel for speed
    t1 = threading.Thread(target=close_dc, daemon=True)
    t2 = threading.Thread(target=close_sc, daemon=True)

    t1.start()
    t2.start()
    
    # Wait for both to finish (but this should be in a background thread already)
    t1.join(timeout=5)  # Don't wait forever
    t2.join(timeout=5)

def logout(parent, frame):
    state.username = None
    state.password = None
    state.logged_in = False  # Clear logged in state

    # Close Chrome in background (non-blocking)
    def close_async():
        close_chrome()
    
    threading.Thread(target=close_async, daemon=True).start()

     # Rebuild login screen immediately (don't wait for Chrome to close)
    parent.forget(frame)
    if state.tools_frame:
        try:
            parent.forget(state.tools_frame)
        except tk.TclError:
            pass  # Already removed
        state.tools_frame = None  # Clear the reference
    
    # Refresh settings tab to hide user-specific settings
    if state.settings_frame and hasattr(state.settings_frame, 'load_user_settings'):
        state.settings_frame.load_user_settings()
    
    new_tab = build_home_tab(parent, "Logout successful!")
    parent.insert(0, new_tab, text="Home")
    parent.select(new_tab)
    
def show_main_ui(parent, frame):

    msg_var = tk.StringVar()

    # Make 3 columns for centering
    for i in range(3):
        frame.columnconfigure(i, weight=1)

    # Top labels centered
    msg_lbl = tk.Label(frame, textvariable=msg_var, bg="#2b2b2b", fg="white")
    msg_lbl.grid(row=0, column=0, columnspan=3, pady=(10, 2), sticky="n")
    tk.Label(frame, textvariable=state.department_var, bg="#2b2b2b", fg="white").grid(row=1, column=0, columnspan=3, pady=(0, 10), sticky="n")


    def on_logout(parent, frame):
        if messagebox.askyesno("Confirm Logout", "This will close chrome. Are you sure you want to log out?"):
            msg_var.set("Logging out...")
            logout(parent, frame)

    # Buttons
    logout_btn = ttk.Button(frame, text="Logout", command=lambda: on_logout(parent, frame))
    logout_btn.grid(row=2, column=1, padx=5, pady=(10, 0))
    logout_btn.state(['disabled'])

    def on_reorganize():
        response, status = reorganize_windows()
        flash_message(msg_lbl, msg_var, response, status)

    reorganize_btn = ttk.Button(frame, text="Reorganize", command=on_reorganize)
    reorganize_btn.grid(row=2, column=2, padx=5, pady=(10, 0))
    reorganize_btn.state(['disabled'])

    def on_run_ahk_zoom(zoom):
        response, status = run_ahk_zoom(zoom)
        flash_message(msg_lbl, msg_var, response, status)

    zoom_btn_100 = ttk.Button(frame, text="100%", command=lambda: on_run_ahk_zoom("100"))
    zoom_btn_100.grid(row=3, column=1, padx=5, pady=(10, 0))
    zoom_btn_100.state(['disabled'])

    zoom_btn_custom = ttk.Button(frame, text=f"{state.zoom_var.get()}%", command=lambda: on_run_ahk_zoom(state.zoom_var.get()))
    zoom_btn_custom.grid(row=3, column=2, padx=5, pady=(10, 0))
    zoom_btn_custom.state(['disabled'])

    def update_zoom_button_text(*_):
        zoom_btn_custom.config(text=f"{state.zoom_var.get()}%")

    state.zoom_var.trace_add("write", update_zoom_button_text)


    def wait_for_both():
        """
        Wait for both DC and SC events to be set using threading.
        This is more responsive than polling - triggers immediately when both are ready.
        """
        import time
        start_wait_time = time.time()
        
        def check_ready():
            # Use threading.Event.wait() with timeout for instant response
            # Wait for DC event (20 second timeout)
            if hasattr(state, 'login_start_time'):
                print(f"[PERF] ⏱️  Waiting for DC event... (at {time.time() - state.login_start_time:.2f}s)")
            
            dc_success = state.dc_event.wait(timeout=20)
            if not dc_success:
                print("[WARN] DC event timeout")
                state.root.after(0, handle_launch_failure)
                return
            
            dc_ready_time = time.time()
            if hasattr(state, 'login_start_time'):
                print(f"[PERF] ⏱️  DC event RECEIVED at {dc_ready_time - state.login_start_time:.2f}s from login press")
            
            # Wait for SC event (20 second timeout)
            if hasattr(state, 'login_start_time'):
                print(f"[PERF] ⏱️  DC done, now waiting for SC event... (at {time.time() - state.login_start_time:.2f}s)")
            
            sc_success = state.sc_event.wait(timeout=20)
            if not sc_success:
                print("[WARN] SC event timeout")
                state.root.after(0, handle_launch_failure)
                return
            
            sc_ready_time = time.time()
            if hasattr(state, 'login_start_time'):
                print(f"[PERF] ⏱️  SC event RECEIVED at {sc_ready_time - state.login_start_time:.2f}s from login press")
            
            # Both ready! Update UI immediately
            if hasattr(state, 'login_start_time'):
                total_time = time.time() - state.login_start_time
                print(f"[PERF] ⏱️  'Ready!' displayed in {total_time:.2f}s from login button press")
            state.root.after(0, on_both_ready)
        
        def on_both_ready():
            """Called when both browsers are ready - runs on UI thread"""
            state.relaunched = False
            enable_all_clicks()

            # Show "Ready!" message FIRST (don't wait for Tools tab to build)
            flash_message(msg_lbl, msg_var, "Ready!", status='success')

            # Enable all buttons immediately
            for widget in frame.winfo_children():
                if isinstance(widget, ttk.Button):
                    widget.state(['!disabled'])
            
            # Build Tools tab in background (non-blocking)
            def build_tools_async():
                try:
                    print("[PERF] ⏱️  Building Tools tab in background...")
                    tools_tab = tab_tools.build_tools_tab()
                    # Schedule adding the tab on UI thread
                    state.root.after(0, lambda: state.notebook.add(tools_tab, text="Tools"))
                    print("[PERF] ⏱️  Tools tab added")
                except Exception as e:
                    print(f"[ERROR] Failed to build Tools tab: {e}")
            
            threading.Thread(target=build_tools_async, daemon=True).start()
        
        def handle_launch_failure():
            """Handle browser launch failure - runs on UI thread"""
            if not state.relaunched:
                state.relaunched = True
                print("[WARN] One or both windows failed to launch. Attempting relaunch.")
                state.should_abort = True
                state.root.after(100, close_chrome)  # shut down any launched windows
                enable_all_clicks()
                flash_message(msg_lbl, msg_var, "Failed. Attempting relaunch...", status='error')
                profile_path = get_path("profiles")
                if os.path.isdir(profile_path):
                    shutil.rmtree(profile_path)
                    print(f"Deleted folder: {profile_path}")
                else:
                    print(f"Nothing found at: {profile_path}")
                state.should_abort = False
                disable_all_clicks()
                start_threads_parallel()  # relaunch everything (50% faster with parallel launch!)
                wait_for_both()  # Try again
            else:
                # Second failure - give up
                state.relaunched = False
                print("[WARN] One or both windows failed to relaunch.")
                state.should_abort = True
                state.root.after(100, close_chrome)  # shut down any launched windows
                enable_all_clicks()
                profile_path = get_path("profiles")
                if os.path.isdir(profile_path):
                    shutil.rmtree(profile_path)
                    print(f"Deleted folder: {profile_path}")
                else:
                    print(f"Nothing found at: {profile_path}")
                state.should_abort = False
                tools_tab = tab_tools.build_tools_tab()
                state.notebook.add(tools_tab, text="Tools")

                flash_message(msg_lbl, msg_var, "Failed to launch", status='error')

                for widget in frame.winfo_children(): # Enable all buttons
                    if isinstance(widget, ttk.Button):
                        widget.state(['!disabled'])
        
        # Run the check in a background thread so it doesn't block the UI
        threading.Thread(target=check_ready, daemon=True).start()

    msg_var.set("Launching Chrome...")
    wait_for_both()

    return frame

def build_home_tab(parent, msg):

    user_path = get_path(USER_FILE)

    def load_usernames():
        if os.path.exists(user_path):
            try:
                with open(user_path, "r") as f:
                    return json.load(f)
            except:
                return []
        return []

    def save_usernames(usernames):
        with open(user_path, "w") as f:
            json.dump(usernames, f)

    def remember_username(username):
        usernames = load_usernames()
        # Store username in lowercase
        username_lower = username.lower()
        # Check if it already exists (case-insensitive)
        if not any(u.lower() == username_lower for u in usernames):
            usernames.append(username_lower)
            save_usernames(usernames)

    def remove_username(username):
        usernames = load_usernames()
        if username in usernames:
            usernames.remove(username)
            save_usernames(usernames)

    class AutoSuggestEntry(tk.Entry):
        def __init__(self, master, **kwargs):
            super().__init__(master, **kwargs)
            self.suggestions = load_usernames()
            self.popup = None
            self.mousewheel_binding = None
            self.bind("<KeyRelease>", self.on_key_release)
            self.bind("<FocusIn>", self.show_suggestions)
            self.bind("<FocusOut>", lambda e: self.master.after(150, self.hide_popup))  # delay so clicks can register
        
        def on_key_release(self, event=None):
            # Convert to lowercase as user types
            current_pos = self.index(tk.INSERT)
            current_text = self.get()
            lowercase_text = current_text.lower()
            
            if current_text != lowercase_text:
                self.delete(0, tk.END)
                self.insert(0, lowercase_text)
                self.icursor(current_pos)
            
            self.show_suggestions(event)

        def show_suggestions(self, event=None):
            if self.popup:
                self.popup.destroy()

            val = self.get().lower()
            # Normalize all usernames to lowercase for display
            matches = [u.lower() for u in self.suggestions if val in u.lower()]

            if not matches:
                return

            self.popup = tk.Toplevel(self)
            self.popup.attributes("-topmost", True)
            self.popup.overrideredirect(True)  # no title bar
            self.popup.configure(bg="white", bd=1, relief="solid")

            # Calculate dimensions
            row_height = 33
            max_visible_rows = 10  # Maximum rows to show before scrolling
            visible_rows = min(len(matches), max_visible_rows)
            popup_height = row_height * visible_rows
            
            font = tkfont.Font(font=self.cget("font"))
            longest_text = max(matches, key=lambda s: len(s))
            text_width_px = font.measure(longest_text)
            popup_width = text_width_px + 80

            # Get screen dimensions
            screen_width = self.winfo_screenwidth()
            screen_height = self.winfo_screenheight()
            
            # Calculate initial position (below the entry)
            x = self.winfo_rootx() + 30  # shift right of the entry
            y_below = self.winfo_rooty() + self.winfo_height() + 2  # position below entry
            y_above = self.winfo_rooty() - popup_height - 2  # position above entry
            
            # Check if popup would go off bottom of screen
            space_below = screen_height - y_below
            if y_below + popup_height > screen_height:
                space_above = self.winfo_rooty() - 2
                # Position above entry if there's more space above than below
                if y_above >= 0 and space_above >= space_below:
                    y = max(0, y_above)  # Above, but not off top of screen
                else:
                    # Not enough room above, adjust height to fit below
                    y = y_below
                    available_height = space_below - 10  # 10px margin
                    popup_height = min(popup_height, available_height)
            else:
                y = y_below
            
            # Ensure x doesn't go off right edge of screen
            if x + popup_width > screen_width:
                x = screen_width - popup_width - 10

            self.popup.geometry(f"{popup_width}x{popup_height}+{x}+{y}")

            # Create canvas with scrollbar if needed
            if len(matches) > max_visible_rows:
                canvas = tk.Canvas(self.popup, bg="#2b2b2b", highlightthickness=0)
                scrollbar = tk.Scrollbar(self.popup, orient="vertical", command=canvas.yview)
                scrollable_frame = tk.Frame(canvas, bg="#2b2b2b")
                
                scrollable_frame.bind(
                    "<Configure>",
                    lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
                )
                
                canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
                canvas.configure(yscrollcommand=scrollbar.set)
                
                canvas.pack(side="left", fill="both", expand=True)
                scrollbar.pack(side="right", fill="y")
                
                container = scrollable_frame
                
                # Enable mousewheel scrolling
                def on_mousewheel(event):
                    canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
                
                # Store the binding so we can clean it up later
                self.mousewheel_binding = on_mousewheel
                self.winfo_toplevel().bind_all("<MouseWheel>", self.mousewheel_binding)
            else:
                container = self.popup

            for user in matches:
                row = tk.Frame(container, bg="#2b2b2b")
                row.pack(fill="x")

                lbl = tk.Label(row, text=user, font=30, pady=5, anchor="w", bg="#2b2b2b", fg="white")
                lbl.pack(fill="both", expand=True, side="left")

                del_lbl = tk.Label(row, text="x", fg="red", bg="#2b2b2b", cursor="hand2")
                del_lbl.pack(side="right", padx=5)
                del_lbl.bind("<Button-1>", partial(self.delete_user, user))

                def on_enter(e, r=row, l=lbl, d=del_lbl):
                    r.configure(bg="#7B7B7B")
                    l.configure(bg="#7B7B7B")
                    d.configure(bg="#7B7B7B")


                def on_leave(e, r=row, l=lbl, d=del_lbl):
                    r.configure(bg="#2b2b2b")
                    l.configure(bg="#2b2b2b")
                    d.configure(bg="#2b2b2b")

                row.bind("<Enter>", on_enter)
                row.bind("<Leave>", on_leave)
                lbl.bind("<Enter>", on_enter)
                lbl.bind("<Leave>", on_leave)
                lbl.bind("<Button-1>", partial(self.select_user, user))


        def hide_popup(self):
            if self.popup:
                # Clean up mousewheel binding if it exists
                if self.mousewheel_binding:
                    try:
                        self.winfo_toplevel().unbind_all("<MouseWheel>")
                    except tk.TclError:
                        # Widget may have been destroyed already
                        pass
                    self.mousewheel_binding = None
                
                self.popup.destroy()
                self.popup = None

        def select_user(self, username, event=None):
            self.delete(0, tk.END)
            self.insert(0, username)
            self.hide_popup()
            password_entry.focus_set()

        def delete_user(self, username, event=None):
            # Find the original username in suggestions (might have different case)
            original_username = None
            for u in self.suggestions:
                if u.lower() == username.lower():
                    original_username = u
                    break
            
            if original_username:
                remove_username(original_username)
                self.suggestions = load_usernames()
                self.show_suggestions()


    frame = tk.Frame(parent, bg="#2b2b2b", padx=20, pady=20)
    # Feedback label
    msg_var = tk.StringVar(value=msg)
    msg_lbl = tk.Label(frame, textvariable=msg_var, fg="white", bg="#2b2b2b")
    msg_lbl.grid(row=0, column=0, columnspan=2, pady=(0, 15))
    flash_message(msg_lbl, msg_var, msg, "success")

    # Username + Password
    tk.Label(frame, text="Username:", bg="#2b2b2b", fg="white").grid(row=1, column=0, sticky="e", pady=5)
    tk.Label(frame, text="Password:", bg="#2b2b2b", fg="white").grid(row=2, column=0, sticky="e", pady=5)

    username_entry = AutoSuggestEntry(frame)
    username_entry.grid(row=1, column=1, pady=5, sticky="e")
    password_entry = ttk.Entry(frame, show="*")
    password_entry.grid(row=2, column=1, pady=5, sticky="e")

    def on_login_submit():
        username = username_entry.get()
        password = password_entry.get()
        print(username)

        if validate_credentials(username, password):
            remember_username(username)
            state.username = username
            state.password = password
            state.logged_in = True  # Set logged in state
            
            # Fetch user settings BEFORE launching browsers
            user_theme = "dark"  # Default to dark mode
            user_zoom = "200"    # Default zoom
            
            # OPTIMIZATION: Check cache first (pre-loaded during splash screen)
            if username in state.user_settings_cache:
                cached_settings = state.user_settings_cache[username]
                user_theme = cached_settings.get("theme", "dark")
                user_zoom = cached_settings.get("zoom", "200")
                print(f"[LOGIN] ✓ Loaded user settings from CACHE: theme={user_theme}, zoom={user_zoom}")
            else:
                # Cache miss - user may have been added after app launch
                # Fallback to API call
                print(f"[LOGIN] User '{username}' not in cache, fetching from API...")
                try:
                    from constants import IP, PORT
                    resp = requests.post(
                        f"http://{IP}:{PORT}/get_user_settings",
                        json={"username": username},
                        timeout=5
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    
                    # Update with user settings from database
                    user_zoom = data.get("zoom", "200")
                    user_theme = data.get("theme", "dark")
                    
                    # Store in cache for next time
                    state.user_settings_cache[username] = {
                        "theme": user_theme,
                        "zoom": user_zoom
                    }
                    
                    print(f"[LOGIN] ✓ Loaded user settings from API: theme={user_theme}, zoom={user_zoom}")
                except Exception as e:
                    print(f"[WARNING] Failed to load user settings from API, using defaults (dark mode): {e}")
            
            # ALWAYS set these in config, even if all lookups fail (use defaults)
            state.zoom_var.set(user_zoom)
            config.cfg["zoom_var"] = user_zoom
            config.cfg["theme"] = user_theme
            print(f"[LOGIN] Applied theme to config.cfg: theme={config.cfg['theme']}, zoom={config.cfg['zoom_var']}")
            print(f"[LOGIN] DEBUG: config.cfg type: {type(config.cfg)}")
            print(f"[LOGIN] DEBUG: config.cfg.get('theme'): {config.cfg.get('theme', 'NOT_FOUND')}")
            print(f"[LOGIN] DEBUG: config.cfg id: {id(config.cfg)}")
            print(f"[LOGIN] DEBUG: config.cfg contents: {dict(config.cfg)}")
            
            # Start performance timer
            import time
            state.login_start_time = time.time()
            print(f"[PERF] ⏱️  Starting browser launch timer at login button press")
            
            hide_login_form()
            show_main_ui(parent, frame)
            start_threads_parallel()  # Use optimized parallel launch (50% faster!)
            state.root.after(100, disable_all_clicks)
            
            # Refresh settings tab to show user-specific settings
            if state.settings_frame and hasattr(state.settings_frame, 'load_user_settings'):
                state.root.after(200, state.settings_frame.load_user_settings)
        else:
            flash_message(msg_lbl, msg_var, "Invalid username or password", "error")
            password_entry.focus_set()

    # Buttons
    button_container = tk.Frame(frame, bg="#2b2b2b")
    button_container.grid(row=3, column=0, columnspan=2, pady=(15, 0))
    button_container.columnconfigure(0, weight=1)
    button_container.columnconfigure(1, weight=1)

    submit_btn = ttk.Button(button_container, text="Login", command=on_login_submit)

    if state.update_available:
        def auto_update():
            """Download and install update automatically (with fallback)"""
            # Disable buttons during update
            update_btn.config(state="disabled", text="Downloading...")
            submit_btn.config(state="disabled")
            
            def download_and_install():
                try:
                    # Get release info
                    release_info = get_latest_release_info()
                    if not release_info:
                        state.root.after(0, lambda: messagebox.showerror("Update Failed", "Could not fetch update information."))
                        state.root.after(0, lambda: update_btn.config(state="normal", text="Update"))
                        state.root.after(0, lambda: submit_btn.config(state="normal"))
                        return
                    
                    # Direct exe replacement via PowerShell
                    if release_info.get('exe_url'):
                        state.root.after(0, lambda: update_btn.config(text="Downloading..."))
                        
                        if install_update_direct(release_info['exe_url']):
                            # Exit silently to allow PowerShell script to proceed
                            def exit_app():
                                # Force exit immediately without dialog
                                import sys
                                sys.exit(0)
                            
                            state.root.after(0, exit_app)
                            return
                    
                    # Update failed
                    state.root.after(0, lambda: messagebox.showerror(
                        "Update Failed",
                        "Could not install update.\n\n"
                        "Please download manually from:\n"
                        "https://github.com/ShutterSeeker/BrowserControl/releases"
                    ))
                    state.root.after(0, lambda: update_btn.config(state="normal", text="Update"))
                    state.root.after(0, lambda: submit_btn.config(state="normal"))
                
                except Exception as e:
                    state.root.after(0, lambda: messagebox.showerror("Update Failed", f"An error occurred: {str(e)}"))
                    state.root.after(0, lambda: update_btn.config(state="normal", text="Update"))
                    state.root.after(0, lambda: submit_btn.config(state="normal"))
            
            # Run download in background thread
            threading.Thread(target=download_and_install, daemon=True).start()

        update_btn = ttk.Button(button_container, text="Update", command=auto_update, style="Update.TButton")
        update_btn.grid(row=0, column=0, padx=(0, 5))

        submit_btn.grid(row=0, column=1, padx=(5, 0))
    else:
        submit_btn.grid(row=0, column=0, columnspan=2)
    
    # Show connection warning if update check failed
    if hasattr(state, 'update_message') and ("Connection failed" in state.update_message or "Update check failed" in state.update_message):
        warning_label = tk.Label(
            frame,
            text=f"⚠️ {state.update_message}",
            font=("Segoe UI", 9),
            bg="#2b2b2b",
            fg="#ffaa00",
            wraplength=400,
            justify="center"
        )
        warning_label.grid(row=4, column=0, columnspan=2, pady=(10, 0))


    def hide_login_form():
        username_entry.grid_remove()
        password_entry.grid_remove()
        msg_lbl.grid_remove()
        submit_btn.grid_remove()

        for widget in frame.grid_slaves():
            if isinstance(widget, tk.Label) and widget.cget("text") in ("Username:", "Password:"):
                widget.grid_remove()

    def is_osk_in_foreground():
        hwnd = win32gui.GetForegroundWindow()
        return "on-screen keyboard" in win32gui.GetWindowText(hwnd).lower()

    def get_osk_hwnd():
        osk_hwnd = None
        def callback(hwnd, _):
            nonlocal osk_hwnd
            if "on-screen keyboard" in win32gui.GetWindowText(hwnd).lower():
                osk_hwnd = hwnd
        win32gui.EnumWindows(callback, None)
        return osk_hwnd
    
    def wait_until_osk_has_focus():
        if not is_osk_in_foreground():
            print("[DEBUG] Waiting for focus")
            frame.after(100, wait_until_osk_has_focus)
        else:
            frame.after(200, lambda: username_entry.focus_force())
            frame.after(800, lambda: username_entry.focus_force())

    def revive_osk(hwnd):
        if win32gui.IsIconic(hwnd):
            print("OSK is minimized, launching again to revive.")
            subprocess.Popen("osk.exe", shell=True)
            frame.after(100, wait_until_osk_has_focus)
        else:
            print("OSK is already visible, focusing username.")
            frame.after(100, lambda: username_entry.focus_force())

    def revive_and_refocus():
        hwnd = get_osk_hwnd()
        if hwnd:
            revive_osk(hwnd)
        else:
            frame.after(100, lambda: username_entry.focus_force())

    frame.after(200, revive_and_refocus)
    frame.bind_all("<Return>", lambda event: on_login_submit())
    return frame