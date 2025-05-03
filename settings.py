# browser_control/settings.py

import os
import configparser

CONFIG_FILE = os.path.join(os.path.dirname(__file__), "settings.ini")

def load_settings():
    """
    Return a dict of saved settings (or defaults).
    """
    cfg = configparser.ConfigParser()
    if os.path.exists(CONFIG_FILE):
        cfg.read(CONFIG_FILE)
    s = cfg["Settings"] if "Settings" in cfg else {}
    return {
        # existing settings…
        "department": s.get("department", ""),
        "darkmode": s.getboolean("darkmode", False),
        "zoom_var": s.get("zoom_var", ""),
        "win_x": int(s.get("win_x", 0)),
        "win_y": int(s.get("win_y", 0)),
        # DC window geometry
        "dc_x": int(s.get("dc_x", 0)),
        "dc_y": int(s.get("dc_y", 0)),
        "dc_width": int(s.get("dc_width", 0)),
        "dc_height": int(s.get("dc_height", 0)),
        # SC window geometry
        "sc_x": int(s.get("sc_x", 0)),
        "sc_y": int(s.get("sc_y", 0)),
        "sc_width": int(s.get("sc_width", 0)),
        "sc_height": int(s.get("sc_height", 0)),
    }

def save_settings(department, darkmode, zoom_var, win_x, win_y):
    """
    Save the basic UI settings.
    """
    cfg = configparser.ConfigParser()
    if os.path.exists(CONFIG_FILE):
        cfg.read(CONFIG_FILE)
    if not cfg.has_section("Settings"):
        cfg.add_section("Settings")

    cfg.set("Settings", "department", department)
    cfg.set("Settings", "darkmode", str(darkmode))
    cfg.set("Settings", "zoom_var", zoom_var)
    cfg.set("Settings", "win_x", str(win_x))
    cfg.set("Settings", "win_y", str(win_y))

    with open(CONFIG_FILE, "w") as f:
        cfg.write(f)

def save_position(x: int, y: int):
    """
    Save the main UI window position.
    """
    cfg = configparser.ConfigParser()
    if os.path.exists(CONFIG_FILE):
        cfg.read(CONFIG_FILE)
    if not cfg.has_section("Settings"):
        cfg.add_section("Settings")

    cfg.set("Settings", "win_x", str(x))
    cfg.set("Settings", "win_y", str(y))

    with open(CONFIG_FILE, "w") as f:
        cfg.write(f)

def save_window_geometry(
    dc_x: int, dc_y: int, dc_w: int, dc_h: int,
    sc_x: int, sc_y: int, sc_w: int, sc_h: int
):
    """
    Save DC and SC window position & size.
    """
    cfg = configparser.ConfigParser()
    if os.path.exists(CONFIG_FILE):
        cfg.read(CONFIG_FILE)
    if not cfg.has_section("Settings"):
        cfg.add_section("Settings")

    # DC geometry
    cfg.set("Settings", "dc_x", str(dc_x))
    cfg.set("Settings", "dc_y", str(dc_y))
    cfg.set("Settings", "dc_width", str(dc_w))
    cfg.set("Settings", "dc_height", str(dc_h))
    # SC geometry
    cfg.set("Settings", "sc_x", str(sc_x))
    cfg.set("Settings", "sc_y", str(sc_y))
    cfg.set("Settings", "sc_width", str(sc_w))
    cfg.set("Settings", "sc_height", str(sc_h))

    with open(CONFIG_FILE, "w") as f:
        cfg.write(f)