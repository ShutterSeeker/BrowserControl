#tray.py

import threading
from pystray import Icon, Menu, MenuItem
from PIL import Image, ImageDraw
from browser_control.settings import get_path
from browser_control import state

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
    
def setup_tray():
    def on_quit(icon, item):
        icon.stop()
        state.root.destroy()

    tray_icon = Icon(
        "Browser Control",
        create_image(),
        title="Browser Control",
        menu=Menu(MenuItem("Quit", on_quit))
    )

    threading.Thread(target=tray_icon.run, daemon=True).start()
    return tray_icon