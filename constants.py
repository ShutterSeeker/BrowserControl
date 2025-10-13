#constants.py

VERSION = "2.0.2"
DC_TITLE = "DC - Google Chrome"
SC_TITLE = "SC - Google Chrome"
MUTEX_NAME = "BrowserControlMutex"

# GitHub Configuration
UPDATE_CHECK_URL = "https://api.github.com/repos/ShutterSeeker/BrowserControl/releases/latest"
USERSCRIPTS_REPO = "ShutterSeeker/scaleplus-userscripts"
USERSCRIPTS_BRANCH = "main"

# Userscript Configuration
# Add/remove userscripts here - they will auto-update from GitHub
USERSCRIPTS = [
    "OnContainerCloseCopy.user.js",
    "RFEnhance.user.js",
    # Add more userscripts as needed:
    # "AnotherScript.user.js",
]

# Scale URLs - Base domains
SCALE_PROD = "https://scale20.byjasco.com"
SCALE_QA = "https://scaleqa.byjasco.com"
DC_URL = "https://dc.byjasco.com"

# Scale URLs - Production
RF_URL = f"{SCALE_PROD}/RF/SignonMenuRF.aspx"
DECANT_URL = f"{SCALE_PROD}/RF/DecantProcessing.aspx"
SLOTSTAX_URL = f"{SCALE_PROD}/RF/PalletCompleteRF.aspx"
PACKING_URL = f"{SCALE_PROD}/scale/trans/packing"
CLOSECONTAINER_URL = f"{SCALE_PROD}/scale/trans/closecontainer"
LABOR_URL = f"{SCALE_PROD}/RF/JPCILaborTrackingRF.aspx"

# File Paths
USER_FILE = "usernames.json"
CONFIG_FILE = "settings.ini"
USERSCRIPTS_DIR = "userscripts"

# Config
SECTION = "Settings"
IP = "10.110.2.145"
PORT = "5000"
ZOOM_OPTIONS = ["150", "200", "250", "300"]
DEPARTMENTS = [
    "Packing", "DECANT.WS.1", "DECANT.WS.2", "DECANT.WS.3",
    "DECANT.WS.4", "DECANT.WS.5", "PalletizingStation1",
    "PalletizingStation2", "PalletizingStation3",
]
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
    'sc_height': '1471',
    'dc_link' : f'{DC_URL}/LiveMetrics',
    'sc_link' : RF_URL,
    'dc_state' : 'normal',
    'sc_state' : 'normal'
}