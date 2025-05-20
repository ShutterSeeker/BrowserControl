# tab_home_login.py

from tkinter import ttk, messagebox
import tkinter as tk
import time, threading, os, shutil, webbrowser
from browser_control.utils import validate_credentials, flash_message
from browser_control import state, tab_tools
from browser_control.chrome import start_threads, reorganize_windows, run_ahk_zoom
from browser_control.utils import get_path

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
    def close_dc():
        if state.driver_dc:
            try: state.driver_dc.quit()
            except: pass
        state.driver_dc = None
        state.dc_event.clear()
        state.driver_dc = None
        state.dc_win = None


    def close_sc():
        if state.driver_sc:
            try: state.driver_sc.quit()
            except: pass
        state.driver_sc = None
        state.sc_event.clear()
        state.driver_sc = None
        state.sc_win = None
        state.sc_hwnd = None


    t1 = threading.Thread(target=close_dc, daemon=True)
    t2 = threading.Thread(target=close_sc, daemon=True)

    t1.start()
    t2.start()
    t1.join()
    t2.join()

def logout(parent, frame):
    state.username = None
    state.password = None

    state.root.after(100, lambda: close_chrome())

     # Rebuild login screen
    parent.forget(frame)
    parent.forget(state.tools_frame)
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
        elif attempt > 100 and state.relaunched == False:  # ~20 seconds total (200 * 100ms)
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
            start_threads()  # relaunch everything
            wait_for_both()
        elif attempt > 100:
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
    frame = tk.Frame(parent, bg="#2b2b2b", padx=20, pady=20)
    # Feedback label
    msg_var = tk.StringVar(value=msg)
    msg_lbl = tk.Label(frame, textvariable=msg_var, fg="white", bg="#2b2b2b")
    msg_lbl.grid(row=0, column=0, columnspan=2, pady=(0, 15))
    flash_message(msg_lbl, msg_var, msg, "success")

    # Username + Password
    tk.Label(frame, text="Username:", bg="#2b2b2b", fg="white").grid(row=1, column=0, sticky="e", pady=5)
    tk.Label(frame, text="Password:", bg="#2b2b2b", fg="white").grid(row=2, column=0, sticky="e", pady=5)

    username_var = tk.StringVar()
    password_var = tk.StringVar()

    username_entry = ttk.Entry(frame, textvariable=username_var)
    password_entry = ttk.Entry(frame, textvariable=password_var, show="*")

    username_entry.grid(row=1, column=1, pady=5, sticky="w")
    password_entry.grid(row=2, column=1, pady=5, sticky="w")

    def on_login_submit():
        username = username_var.get()
        password = password_var.get()

        if validate_credentials(username, password):
            state.username = username
            state.password = password
            hide_login_form()
            show_main_ui(parent, frame)
            start_threads()
            state.root.after(100, disable_all_clicks)
        else:
            flash_message(msg_lbl, msg_var, "Invalid username or password", "error")
            password_var.set("")
            password_entry.focus_set()

    # Buttons
    button_container = tk.Frame(frame, bg="#2b2b2b")
    button_container.grid(row=3, column=0, columnspan=2, pady=(15, 0))
    button_container.columnconfigure(0, weight=1)
    button_container.columnconfigure(1, weight=1)

    submit_btn = ttk.Button(button_container, text="Login", command=on_login_submit)

    if state.update_available:
        def open_update_page():
            webbrowser.open("https://github.com/ShutterSeeker/BrowserControl/releases/latest")

        update_btn = ttk.Button(button_container, text="Update", command=open_update_page, style="Update.TButton")
        update_btn.grid(row=0, column=0, padx=(0, 5))

        submit_btn.grid(row=0, column=1, padx=(5, 0))
    else:
        submit_btn.grid(row=0, column=0, columnspan=2)


    def hide_login_form():
        username_entry.grid_remove()
        password_entry.grid_remove()
        msg_lbl.grid_remove()
        submit_btn.grid_remove()

        for widget in frame.grid_slaves():
            if isinstance(widget, tk.Label) and widget.cget("text") in ("Username:", "Password:"):
                widget.grid_remove()

    
    frame.after(200, lambda: username_entry.focus_set())
    frame.bind_all("<Return>", lambda event: on_login_submit())
    return frame