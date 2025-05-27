# main.py

import tkinter as tk
import threading
from browser_control.ui import show_splash

def build_ui():
    from tkinter import ttk
    from browser_control.tray import setup_tray
    from browser_control import tab_home, tab_settings, state, ui
    from browser_control.settings import save_position
    from browser_control import config
    from browser_control.constants import VERSION

    root = tk.Tk()
    state.root = root
    state.department_var = tk.StringVar(master=root, value=config.cfg["department"])
    state.zoom_var = tk.StringVar(master=root, value=config.cfg["zoom_var"])

    # Set up tray
    tray_icon = setup_tray()

    def on_close_window():
        save_position(root.winfo_x(), root.winfo_y())
        tray_icon.visible = False
        tray_icon.stop()
        root.destroy()

    # Window config
    root.protocol("WM_DELETE_WINDOW", on_close_window)
    root.geometry(f"+{config.cfg['win_x']}+{config.cfg['win_y']}")
    root.title(f"Jasco v{VERSION}")
    root.attributes("-topmost", True)
    root.resizable(False, False)
    root.after(100, lambda: root.focus_force())
    root.configure(bg="#2b2b2b")

    # Apply theming
    ui.apply_theme()

    # Create notebook
    notebook = ttk.Notebook(root)
    state.notebook = notebook
    notebook.pack(fill=tk.BOTH, expand=True)

    # Build tabs
    home_tab = tab_home.build_home_tab(notebook, msg="Enter credentials")
    settings_tab = tab_settings.build_settings_tab(notebook)

    # Add tabs to notebook
    notebook.add(home_tab, text="Home")
    notebook.add(settings_tab, text="Settings")
        
    root.mainloop()

def start():
    splash = show_splash()

    def load_heavy_stuff():
        # Import everything here (even if unused in this function) during splash screen so python caches it for later use
        import win32event, win32api, winerror, os, sys, configparser, requests, threading, time, pygetwindow, win32gui, subprocess, tkinter.font
        from threading import Event
        from ldap3 import Connection, NTLM
        from tkinter import ttk
        from tkinter import messagebox
        from pystray import Icon, Menu, MenuItem
        from PIL import Image, ImageDraw
        from selenium import webdriver
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait, Select
        from selenium.webdriver.support import expected_conditions
        from selenium.webdriver.chrome.service import Service
        from selenium.common.exceptions import StaleElementReferenceException
        from webdriver_manager.chrome import ChromeDriverManager
        from browser_control import bookmarks, chrome, config, constants, launcher, settings, state, tab_home, tab_settings, tab_tools, tray, ui, utils

        state.update_available = utils.update_available()

        config.cfg = settings.load_settings()

        state.driver_path = ChromeDriverManager().install()

        splash.after(0, on_load_complete)

    def on_load_complete():
        from browser_control.utils import ensure_single_instance
        splash.destroy()
        ensure_single_instance()
        build_ui()

    threading.Thread(target=load_heavy_stuff, daemon=True).start()
    splash.mainloop()

if __name__ == "__main__":
    start()