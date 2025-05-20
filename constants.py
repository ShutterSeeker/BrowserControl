#constants.py

VERSION = "2.0.0"
DC_TITLE = "DC - Google Chrome"
SC_TITLE = "SC - Google Chrome"
MUTEX_NAME = "BrowserControlMutex"
UPDATE_CHECK_URL = "https://api.github.com/repos/ShutterSeeker/BrowserControl/releases/latest"
RF_URL = "https://scale20.byjasco.com/RF/SignonMenuRF.aspx"
DECANT_URL = "https://scale20.byjasco.com/RF/DecantProcessing.aspx"
SLOTSTAX_URL = "https://scale20.byjasco.com/RF/PalletCompleteRF.aspx"
PACKING_URL = "https://scale20.byjasco.com/scale/trans/packing"
LABOR_URL = "https://scale20.byjasco.com/RF/JPCILaborTrackingRF.aspx"
CONFIG_FILE = "settings.ini"
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
    'dc_link' : 'https://dc.byjasco.com/LiveMetrics',
    'sc_link' : 'https://scale20.byjasco.com/RF/SignonMenuRF.aspx',
    'dc_state' : 'normal',
    'sc_state' : 'normal'
}