#settings.py
import os, sys, configparser, pygetwindow as gw
from browser_control.constants import CONFIG_FILE, SECTION, DEFAULTS
from browser_control import config
from browser_control import state
from browser_control.utils import get_path

settings_path = get_path(CONFIG_FILE)

def save_settings():

    # Use existing values from memory
    department = config.cfg.get("department", "")
    zoom_var = config.cfg.get("zoom_var", "")
    darkmode = config.cfg.get("darkmode", "")

    # Load existing settings.ini
    parser = configparser.ConfigParser()
    if os.path.exists(settings_path):
        parser.read(settings_path)

    if not parser.has_section(SECTION):
        parser.add_section(SECTION)

    # Only update the 3 keys you care about
    parser[SECTION]['department'] = department
    parser[SECTION]['zoom_var'] = zoom_var
    parser[SECTION]['darkmode'] = darkmode

    with open(settings_path, 'w') as configfile:
        parser.write(configfile)

def load_settings():
    config = configparser.ConfigParser()
    # read existing config; missing file is okay
    if os.path.exists(settings_path):
        config.read(settings_path)
    # ensure the section exists
    if not config.has_section(SECTION):
        config.add_section(SECTION)
    section = config[SECTION]
    # populate defaults for missing keys
    for key, val in DEFAULTS.items():
        if key not in section:
            section[key] = val
    return section

def save_position(x, y):

    # Update in-memory config
    config.cfg['win_x'] = str(x)
    config.cfg['win_y'] = str(y)

    # Use a different name for the parser instance
    parser = configparser.ConfigParser()
    if os.path.exists(settings_path):
        parser.read(settings_path)

    if not parser.has_section(SECTION):
        parser.add_section(SECTION)

    parser[SECTION]['win_x'] = str(x)
    parser[SECTION]['win_y'] = str(y)

    with open(settings_path, 'w') as configfile:
        parser.write(configfile)

def get_window_state(driver, exclude_window=None):
    try:
        tolerance = 2
        pos = driver.get_window_position()
        size = driver.get_window_size()
        target = (pos['x'], pos['y'], size['width'], size['height'])

        for w in gw.getWindowsWithTitle('Google Chrome'):
            if exclude_window and w == exclude_window:
                continue

            # Allow for slight mismatch
            if (abs(w.left - target[0]) <= tolerance and
                abs(w.top - target[1]) <= tolerance and
                abs(w.width - target[2]) <= tolerance and
                abs(w.height - target[3]) <= tolerance):

                if w.isMinimized:
                    return 'minimized', w
                elif w.isMaximized:
                    return 'maximized', w
                else:
                    return 'normal', w

        print(f"[DEBUG] can't find matching Chrome window — assuming minimized")
        return 'minimized', None  # Fallback

    except Exception as e:
        print(f"[DEBUG] get_window_state error: {e}")
        return 'unknown', None
 
def save_window_geometry():

    if not state.driver_dc or not state.driver_sc:
        return "Window(s) not found"

    # Get positions and sizes
    dc_pos = state.driver_dc.get_window_position()
    dc_size = state.driver_dc.get_window_size()
    sc_pos = state.driver_sc.get_window_position()
    sc_size = state.driver_sc.get_window_size()

    # Determine window state
    dc_state, dc_win = get_window_state(state.driver_dc)
    sc_state, _ = get_window_state(state.driver_sc, exclude_window=dc_win)

    # Save DC geometry if normal
    if dc_state == "normal":
        config.cfg["dc_x"] = str(dc_pos["x"])
        config.cfg["dc_y"] = str(dc_pos["y"])
        config.cfg["dc_width"] = str(dc_size["width"])
        config.cfg["dc_height"] = str(dc_size["height"])

    # Save SC geometry if normal
    if sc_state == "normal":
        config.cfg["sc_x"] = str(sc_pos["x"])
        config.cfg["sc_y"] = str(sc_pos["y"])
        config.cfg["sc_width"] = str(sc_size["width"])
        config.cfg["sc_height"] = str(sc_size["height"])

    # Always save state
    config.cfg["dc_state"] = dc_state
    config.cfg["sc_state"] = sc_state

    # Load + update .ini
    parser = configparser.ConfigParser()
    if os.path.exists(settings_path):
        parser.read(settings_path)
    if not parser.has_section(SECTION):
        parser.add_section(SECTION)

    for key in config.cfg:
        parser[SECTION][key] = config.cfg[key]

    with open(settings_path, "w") as configfile:
        parser.write(configfile)