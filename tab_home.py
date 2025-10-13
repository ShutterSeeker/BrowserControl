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

# Local imports
import state
import tab_tools
from chrome import start_threads_parallel, reorganize_windows, run_ahk_zoom
from utils import validate_credentials, flash_message, get_path
from constants import USER_FILE, UPDATE_CHECK_URL

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


    def wait_for_both(attempt=1):
        if state.dc_event.is_set() and state.sc_event.is_set():
            state.relaunched = False
            enable_all_clicks()

            tools_tab = tab_tools.build_tools_tab()
            state.notebook.add(tools_tab, text="Tools")

            flash_message(msg_lbl, msg_var, "Ready!", status='success')

            for widget in frame.winfo_children(): # Enable all buttons
                if isinstance(widget, ttk.Button):
                    widget.state(['!disabled'])
        elif attempt > 200 and state.relaunched == False:  # ~20 seconds total (200 * 100ms)
            state.relaunched = True
            print("[WARN] One or both windows failed to launch. Attempting relaunch.")
            state.should_abort = True
            state.root.after(100, close_chrome())  # shut down any launched windows
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
            wait_for_both()
        elif attempt > 200:
            state.relaunched = False
            print("[WARN] One or both windows failed to relaunch.")
            state.should_abort = True
            state.root.after(100, close_chrome())  # shut down any launched windows
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
        else:
            state.root.after(100, lambda: wait_for_both(attempt + 1))

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
        if username not in usernames:
            usernames.append(username)
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
            self.bind("<KeyRelease>", self.show_suggestions)
            self.bind("<FocusIn>", self.show_suggestions)
            self.bind("<FocusOut>", lambda e: self.master.after(150, self.hide_popup))  # delay so clicks can register

        def show_suggestions(self, event=None):
            if self.popup:
                self.popup.destroy()

            val = self.get().lower()
            matches = [u for u in self.suggestions if val in u.lower()]

            if not matches:
                return

            self.popup = tk.Toplevel(self)
            self.popup.attributes("-topmost", True)
            self.popup.overrideredirect(True)  # no title bar
            self.popup.configure(bg="white", bd=1, relief="solid")

            # Position relative to screen
            x = self.winfo_rootx() + 30  # shift right of the entry
            y = self.winfo_rooty() + 18  # shift below the entry
            row_height = 33
            popup_height = row_height * len(matches)
            font = tkfont.Font(font=self.cget("font"))
            longest_text = max(matches, key=lambda s: len(s))  # or max width
            text_width_px = font.measure(longest_text)

            self.popup.geometry(f"{text_width_px + 80}x{popup_height}+{x}+{y}")

            for user in matches:
                row = tk.Frame(self.popup, bg="#2b2b2b")
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
                self.popup.destroy()
                self.popup = None

        def select_user(self, username, event=None):
            self.delete(0, tk.END)
            self.insert(0, username)
            self.hide_popup()
            password_entry.focus_set()

        def delete_user(self, username, event=None):
            remove_username(username)
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
            hide_login_form()
            show_main_ui(parent, frame)
            start_threads_parallel()  # Use optimized parallel launch (50% faster!)
            state.root.after(100, disable_all_clicks)
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
        def open_update_page():
            webbrowser.open(UPDATE_CHECK_URL)

        update_btn = ttk.Button(button_container, text="Update", command=open_update_page, style="Update.TButton")
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