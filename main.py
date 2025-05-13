# browser_control/main.py

import sys
import os
import tkinter as tk
import win32event
import win32api
import winerror
import ctypes
from tkinter import ttk
import subprocess
from browser_control.settings import load_settings, save_settings_click, save_position, resource_path
from browser_control.launcher import launch_app, close_app, pass_window_geometry
import browser_control.launcher as launcher
from browser_control.tools_tab import create_tools_tab
import pystray
from PIL import Image, ImageDraw
import threading
import requests


VERSION = "1.2.1"

def check_for_update():
    try:
        response = requests.get("https://api.github.com/repos/ShutterSeeker/BrowserControl/releases/latest", timeout=5)
        if response.status_code == 200:
            data = response.json()
            latest_version = data.get("tag_name", "").lstrip("v")
            if latest_version > VERSION:
                return f"New version available: v{latest_version}", True
            else:
                return "You are on the latest version.", False
        else:
            return "Failed to check for updates.", False
    except Exception as e:
        return f"Update check error: {e}", False


def get_path(file):
    # if frozen (running as EXE), look next to the EXE
    if getattr(sys, "frozen", False):
        return os.path.join(os.path.dirname(sys.executable), file)
    # else (running from source), load the one in browser_control/
    return resource_path(file)

# Helper to run AHK zoom control
def run_ahk_zoom(percent: str) -> str:
    hwnd = launcher.scale_hwnd
    if not hwnd:
        return "Scale window not found"
    exe_path = get_path("zoom_control.exe")
    if not os.path.isfile(exe_path):
        return "Zoom control executable not found"
    loops_map = {"100":2, "150":3, "200":5, "250":6, "300":7}
    key = percent.strip().rstrip('%')
    count = loops_map.get(key)
    if count is None:
        return "Unsupported zoom level"
    try:
        subprocess.run([exe_path, str(hwnd), str(count)], check=True)
        return f"Zoom set to {key}%"
    except subprocess.CalledProcessError as e:
        return f"Zoom failed (exit {e.returncode})"
    except Exception as e:
        return f"Zoom failed ({e})"

DEPARTMENTS = [
    "Packing", "DECANT.WS.1", "DECANT.WS.2", "DECANT.WS.3",
    "DECANT.WS.4", "DECANT.WS.5", "PalletizingStation1",
    "PalletizingStation2", "PalletizingStation3",
]
ZOOM_OPTIONS = ["150", "200", "250", "300"]


def build_ui():

    mutex_name = "BrowserControlMutex"
    mutex = win32event.CreateMutex(None, False, mutex_name)

    # If the mutex already exists, it means another instance is running
    if win32api.GetLastError() == winerror.ERROR_ALREADY_EXISTS:
        ctypes.windll.user32.MessageBoxW(0, "Browser Control is already running.", "Instance Check", 0x0 | 0x40)
        sys.exit(0)

    cfg = load_settings()

    tray_icon = None

    def create_image():
        icon_path = get_path("jasco.ico")
        try:
            return Image.open(icon_path)
        except Exception as e:
            print(f"[WARN] Failed to load icon: {e}")
            # fallback: simple circle
            image = Image.new("RGB", (64, 64), "black")
            draw = ImageDraw.Draw(image)
            draw.ellipse((16, 16, 48, 48), fill="white")
            return image

    def on_quit_tray(icon, item):
        icon.stop()
        root.quit()

    def setup_tray():
        nonlocal tray_icon
        tray_icon = pystray.Icon(
            "Browser Control",
            create_image(),
            title="Browser Control",
            menu=pystray.Menu(pystray.MenuItem("Quit", on_quit_tray))
        )
        threading.Thread(target=tray_icon.run, daemon=True).start()

    
    root = tk.Tk()
    setup_tray()

    # Style for dark-themed tabs and buttons
    style = ttk.Style()
    style.theme_use("clam")
    style.configure("TNotebook", background="#2b2b2b", borderwidth=0)
    style.configure("TNotebook.Tab", background="#1f1f1f", foreground="white", padding=[10,5])
    style.map("TNotebook.Tab", background=[("selected","#2b2b2b")], foreground=[("selected","white")])
    style.configure("TButton", background="white", foreground="black", font=("Segoe UI", 10))
    style.map("TButton", background=[("active","#e0e0e0")])
    style.configure("Update.TButton",
        background="#ffff88",       # light yellow
        foreground="black",
        bordercolor="#ccaa00",      # dark yellow border (used on Windows)
        focusthickness=2,
        relief="solid",
        padding=6
    )

    # Appearance on hover update
    style.map("Update.TButton",
        background=[("active", "#ffeb3b")],
        bordercolor=[("active", "#b38f00")]
    )

    # Default font for all widgets
    default_font = ("Segoe UI", 10)
    root.option_add("*Font", default_font)

    def on_close_window():
        save_position(root.winfo_x(), root.winfo_y())
        if tray_icon:
            tray_icon.stop()
        root.destroy()

    def minimize_window():
        root.overrideredirect(False)
        root.iconify()
        def restore_override(event=None):
            if root.state() == "normal":
                root.overrideredirect(True)
                root.unbind("<Map>")
            else:
                root.after(100, restore_override)
        root.bind("<Map>", restore_override)

    root.protocol("WM_DELETE_WINDOW", on_close_window)
    root.overrideredirect(True)
    root.geometry(f"+{cfg['win_x']}+{cfg['win_y']}")
    root.title("Browser Control")
    root.attributes("-topmost", True)
    root.configure(bg="#2b2b2b")

    # Title bar
    title_bar = tk.Frame(root, bg="#1f1f1f", height=30)
    title_bar.pack(fill=tk.X)
    title_label = tk.Label(title_bar, text=f"Browser Control v{VERSION}", bg="#1f1f1f", fg="white")
    title_label.pack(side=tk.LEFT, padx=5)
    title_label.bind("<ButtonPress-1>", lambda e: setattr(root, '_drag', (e.x, e.y)))
    title_label.bind("<B1-Motion>", lambda e: root.geometry(f"+{root.winfo_x() + e.x - root._drag[0]}+{root.winfo_y() + e.y - root._drag[1]}"))

    close_btn = tk.Button(title_bar, text="✕", font=("Segoe UI", 14), command=on_close_window, bg="#1f1f1f", fg="white", bd=0, padx=5)
    close_btn.pack(side=tk.RIGHT)
    close_btn.bind("<Enter>", lambda e: close_btn.config(bg="red"))
    close_btn.bind("<Leave>", lambda e: close_btn.config(bg="#1f1f1f"))
    minimize_btn = tk.Button(title_bar, text="__", font=("Segoe UI", 14, "bold"), command=minimize_window, bg="#1f1f1f", fg="white", bd=0, padx=5)
    minimize_btn.pack(side=tk.RIGHT)
    #minimize_btn.pack(side=tk.RIGHT, pady=5, ipadx=8)
    minimize_btn.bind("<Enter>", lambda e: minimize_btn.config(bg="#333333"))
    minimize_btn.bind("<Leave>", lambda e: minimize_btn.config(bg="#1f1f1f"))
    title_bar.bind("<ButtonPress-1>", lambda e: setattr(root, '_drag', (e.x, e.y)))
    title_bar.bind("<B1-Motion>", lambda e: root.geometry(f"+{root.winfo_x() + e.x - root._drag[0]}+{root.winfo_y() + e.y - root._drag[1]}"))

    # Notebook
    notebook = ttk.Notebook(root)
    notebook.pack(fill=tk.BOTH, expand=True)
    home_frame = tk.Frame(notebook, bg="#2b2b2b", padx=10, pady=10)
    settings_frame = tk.Frame(notebook, bg="#2b2b2b", padx=10, pady=10)
    notebook.add(home_frame, text="Home")
    notebook.add(settings_frame, text="Settings")

    # Shared vars
    error_var = tk.StringVar(value="Welcome")
    department_var = tk.StringVar(value=cfg["department"])  
    zoom_var = tk.StringVar(value=cfg["zoom_var"] or "Off")
    dark_var = tk.BooleanVar(value=cfg["darkmode"])
    update_var = tk.StringVar(value="")
    is_update_available = tk.BooleanVar(value=False)

    # Animation state
    anim_after_id = None
    dot_count = 0

    def animate_spinner():
        spinner_chars = ['|', '/', '–', '\\']
        nonlocal dot_count, anim_after_id
        dot_count = (dot_count + 1) % len(spinner_chars)
        error_var.set(f"Launching chrome {spinner_chars[dot_count]}")
        anim_after_id = root.after(200, animate_spinner)

    def stop_animation():
        nonlocal anim_after_id
        if anim_after_id:
            root.after_cancel(anim_after_id)
            anim_after_id = None

    def check_ready():
        if launcher.scale_hwnd:
            stop_animation()
            error_var.set("Ready!")
            launch_btn.state(['!disabled'])
        else:
            root.after(200, check_ready)
            
    def on_department_change(*args):
        # Remove the old Tools tab if it exists
        for i in range(notebook.index("end")):
            if notebook.tab(i, "text") == "Tools":
                notebook.forget(i)
                break
        create_tools_tab(notebook, department_var)

    department_var.trace_add("write", on_department_change)

    # HOME: center labels across 3 columns
    for i in range(3): home_frame.columnconfigure(i, weight=1)
    tk.Label(home_frame, textvariable=error_var, bg="#2b2b2b", fg="white").grid(row=0, column=0, columnspan=3, sticky="ew")
    tk.Label(home_frame, textvariable=department_var, bg="#2b2b2b", fg="white").grid(row=1, column=0, columnspan=3, sticky="ew", pady=(5,10))

    # Launch on its own row
    launch_btn = ttk.Button(home_frame, text="Launch", command=lambda: None)
    launch_btn.grid(row=2, column=0, columnspan=3, pady=(0,10))
    def on_launch_toggle():
        nonlocal anim_after_id
        launch_btn.state(['disabled'])
        animate_spinner()
        launch_app(department_var, dark_var, zoom_var)
        check_ready()
        launch_btn.config(text='Close', command=on_close_app)

    def on_close_app():
        stop_animation()
        close_app()
        launch_btn.config(text='Launch', command=on_launch_toggle)
        error_var.set("Closed")
        launch_btn.state(['!disabled'])

    launch_btn.config(command=on_launch_toggle)

    # Zoom buttons below
    zoom_btn_100 = ttk.Button(home_frame, text="100%", command=lambda: error_var.set(run_ahk_zoom("100")))
    zoom_btn_100.grid(row=3, column=1, sticky="e", padx=5)
    zoom_btn_custom = ttk.Button(home_frame, text=f"{zoom_var.get()}%", command=lambda: error_var.set(run_ahk_zoom(zoom_var.get())))
    zoom_btn_custom.grid(row=3, column=2, sticky="e", padx=5)
    # add this trace to auto‑update the button text whenever zoom_var changes:
    zoom_var.trace_add('write', lambda *args: zoom_btn_custom.config(text=f"{zoom_var.get()}%"))

    # SETTINGS tab
    tk.Label(settings_frame, text="Location", bg="#2b2b2b", fg="white").grid(row=0, column=0, sticky="w", pady=5)
    ttk.Combobox(settings_frame, textvariable=department_var, values=DEPARTMENTS, state="readonly").grid(row=0, column=1, sticky="ew", padx=5)
    tk.Label(settings_frame, text="Zoom %", bg="#2b2b2b", fg="white").grid(row=1, column=0, sticky="w", pady=5)
    ttk.Combobox(settings_frame, textvariable=zoom_var, values=ZOOM_OPTIONS, state="readonly").grid(row=1, column=1, sticky="ew", padx=5)
    tk.Checkbutton(settings_frame, text="Dark Mode (Decant)", variable=dark_var, bg="#2b2b2b", fg="white", selectcolor="#2b2b2b").grid(row=2, column=0, columnspan=2, pady=5)
    def on_save_settings():
        save_settings_click(department_var.get(), dark_var.get(), zoom_var.get())
        pass_window_geometry()
        error_var.set("Settings saved")

    # Buttons
    save_btn = ttk.Button(settings_frame, text="Save Settings", command=on_save_settings)

    msg, needs_update = check_for_update()
    update_var.set(msg)
    is_update_available.set(needs_update)

    if is_update_available.get():
        def open_update_page():
            import webbrowser
            webbrowser.open("https://github.com/ShutterSeeker/BrowserControl/releases/latest")

        # Create a sub-frame for button alignment
        button_frame = tk.Frame(settings_frame, bg="#2b2b2b")
        button_frame.grid(row=3, column=0, columnspan=2, pady=10)

        save_btn = ttk.Button(button_frame, text="Save Settings", command=on_save_settings)
        update_btn = ttk.Button(button_frame, text="Update", command=open_update_page, style="Update.TButton")

        save_btn.grid(row=0, column=0, padx=5, sticky="ew")
        update_btn.grid(row=0, column=1, padx=5, sticky="ew")

        settings_frame.columnconfigure(0, weight=1)
        settings_frame.columnconfigure(1, weight=1)
    else:
        save_btn.grid(row=3, column=0, columnspan=2, pady=10)
        settings_frame.columnconfigure(0, weight=1)


    create_tools_tab(notebook, department_var)

    def pulse_settings_tab():
        if is_update_available.get():
            idx = notebook.index(settings_frame)
            label = notebook.tab(idx, option="text")
            if label.endswith("⚠"):
                notebook.tab(idx, text="Settings      ")
            else:
                notebook.tab(idx, text="Settings ⚠")
            root.after(2000, pulse_settings_tab)


    if is_update_available.get():
        pulse_settings_tab()

    # Then start the mainloop
    root.mainloop()

if __name__ == "__main__":
    build_ui()