# browser_control/settings.py

import os, sys
import configparser

def resource_path(rel_path):
    # when frozen by PyInstaller, files are unpacked to _MEIPASS
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel_path)

def get_settings_path():
    # if frozen (running as EXE), look next to the EXE
    if getattr(sys, "frozen", False):
        return os.path.join(os.path.dirname(sys.executable), "settings.ini")
    # else (running from source), load the one in browser_control/
    return resource_path("settings.ini")

CONFIG_FILE = get_settings_path()
SECTION = "Settings"

# Default values for all expected settings
DEFAULTS = {
    'department': 'DECANT.WS.5',
    'zoom_var': '200',
    'darkmode': 'True',
    'win_x': '41',
    'win_y': '1210',
    'dc_x': '1747',
    'dc_y': '0',
    'dc_width': '516',
    'dc_height': '1471',
    'sc_x': '-7',
    'sc_y': '0',
    'sc_width': '1768',
    'sc_height': '1471'
}


def load_settings():
    """
    Load settings from the INI file and return the SectionProxy for the Settings section.
    Ensures all default keys exist so get(), getboolean(), getint() won't KeyError.
    """
    config = configparser.ConfigParser()
    # read existing config; missing file is okay
    if os.path.exists(CONFIG_FILE):
        config.read(CONFIG_FILE)
    # ensure the section exists
    if not config.has_section(SECTION):
        config.add_section(SECTION)
    section = config[SECTION]
    # populate defaults for missing keys
    for key, val in DEFAULTS.items():
        if key not in section:
            section[key] = val
    return section


def save_settings(department, darkmode, zoom_var, win_x, win_y,
                  dc_x, dc_y, dc_width, dc_height,
                  sc_x, sc_y, sc_width, sc_height,
                  dc_state, sc_state):
    config = configparser.ConfigParser()
    if os.path.exists(CONFIG_FILE):
        config.read(CONFIG_FILE)
    if not config.has_section(SECTION):
        config.add_section(SECTION)

    config.set(SECTION, 'department', department)
    config.set(SECTION, 'darkmode', str(darkmode))
    config.set(SECTION, 'zoom_var', zoom_var)
    config.set(SECTION, 'win_x', str(win_x))
    config.set(SECTION, 'win_y', str(win_y))
    config.set(SECTION, 'dc_x', str(dc_x))
    config.set(SECTION, 'dc_y', str(dc_y))
    config.set(SECTION, 'dc_width', str(dc_width))
    config.set(SECTION, 'dc_height', str(dc_height))
    config.set(SECTION, 'sc_x', str(sc_x))
    config.set(SECTION, 'sc_y', str(sc_y))
    config.set(SECTION, 'sc_width', str(sc_width))
    config.set(SECTION, 'sc_height', str(sc_height))
    config.set(SECTION, 'dc_state', dc_state)
    config.set(SECTION, 'sc_state', sc_state)

    with open(CONFIG_FILE, 'w') as f:
        config.write(f)



def save_position(x, y):
    """
    Save just the main UI window position.
    """
    # reuse save_settings to persist geometry changes
    cfg = load_settings()
    save_settings(
        cfg.get('department'),
        cfg.getboolean('darkmode'),
        cfg.get('zoom_var'),
        x, y,
        cfg.getint('dc_x'), cfg.getint('dc_y'), cfg.getint('dc_width'), cfg.getint('dc_height'),
        cfg.getint('sc_x'), cfg.getint('sc_y'), cfg.getint('sc_width'), cfg.getint('sc_height'),
        cfg.get('dc_state'), cfg.get('sc_state')
    )


def save_window_geometry(dc_x, dc_y, dc_w, dc_h,
                         sc_x, sc_y, sc_w, sc_h,
                         dc_state, sc_state):
    cfg = load_settings()
    save_settings(
        cfg.get('department'),
        cfg.getboolean('darkmode'),
        cfg.get('zoom_var'),
        cfg.getint('win_x'), cfg.getint('win_y'),
        dc_x, dc_y, dc_w, dc_h,
        sc_x, sc_y, sc_w, sc_h,
        dc_state, sc_state
    )

def save_settings_click(department, darkmode, zoom_var):
    """
    Save DC and SC window position & size.
    """
    # reuse save_settings to persist geometry changes
    cfg = load_settings()
    save_settings(
        department,
        darkmode,
        zoom_var,
        cfg.getint('win_x'), cfg.getint('win_y'),
        cfg.getint('dc_x'), cfg.getint('dc_y'), cfg.getint('dc_width'), cfg.getint('dc_height'),
        cfg.getint('sc_x'), cfg.getint('sc_y'), cfg.getint('sc_width'), cfg.getint('sc_height'),
        cfg.get('dc_state'), cfg.get('sc_state')
    )