# browser_control/bookmarks.py

import os
import sys
import time
import uuid
import json
from utils import resource_path


def get_profile_data_path(profile: str, filename: str) -> str:
    """
    Returns the absolute path to a file under a Chrome profile's Default folder:
    - Frozen EXE: <exe-folder>/profiles/{profile}/Default/{filename}
    - Source run: browser_control/profiles/{profile}/Default/{filename}
    """
    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(sys.executable)
        return os.path.join(exe_dir, "profiles", profile, "Default", filename)
    # running from source: resource_path will locate under package
    rel_path = os.path.join("profiles", profile, "Default", filename)
    return resource_path(rel_path)


def show_bookmarks_bar(profile: str) -> None:
    """
    Ensures the bookmarks bar is visible for the given profile by patching Preferences.
    """
    prefs_fp = get_profile_data_path(profile, "Preferences")
    # Load existing preferences or start fresh
    prefs = {}
    if os.path.exists(prefs_fp):
        try:
            with open(prefs_fp, "r", encoding="utf-8") as f:
                prefs = json.load(f)
        except json.JSONDecodeError:
            prefs = {}
    # Modify bookmark bar setting
    bb = prefs.setdefault("bookmark_bar", {})
    bb["show_on_all_tabs"] = True
    # Ensure directory exists
    os.makedirs(os.path.dirname(prefs_fp), exist_ok=True)
    # Write back preferences
    with open(prefs_fp, "w", encoding="utf-8") as f:
        json.dump(prefs, f, indent=2)


def generate_bookmarks(department: str):
    """
    Create Chrome bookmark files and ensure the bookmarks bar is shown
    for both ScaleProfile and LiveMetricsProfile based on department.
    """
    # Common link for both profiles
    base_links = [{"name": "RF", "url": "https://scale20.byjasco.com/RF/SignonMenuRF.aspx"}]

    # Extras for ScaleProfile
    scale_extras = []
    if department.startswith("DECANT.WS"):
        scale_extras += [
            {"name": "Inventory", "url": "https://scale20.byjasco.com/scale/insights/2723"},
            {"name": "Transaction history", "url": "https://scale20.byjasco.com/scale/insights/2783"},
        ]
    if department.startswith("PalletizingStation"):
        scale_extras += [
            {"name": "Shipping container", "url": "https://scale20.byjasco.com/scale/insights/4026"},
            {"name": "DIF incoming", "url": f"https://scale20.byjasco.com/scale/insights/80019?selectRows=Y&filters=DATA%E2%96%88%25{department}%25,MESSAGE_TYPE%E2%96%88PalletToteArrival"},
        ]
    if department == "Packing":
        scale_extras += [
            {"name": "Packing", "url": "https://scale20.byjasco.com/scale/trans/packing"},
            {"name": "Close container", "url": "https://scale20.byjasco.com/scale/trans/closecontainer"},
            {"name": "Transaction history", "url": "https://scale20.byjasco.com/scale/insights/2783"},
            {"name": "Shipping container", "url": "https://scale20.byjasco.com/scale/insights/4026"},
        ]

    # Extras for LiveMetricsProfile (extend if needed)
    live_extras = [{"name": "Live metrics", "url": "https://dc.byjasco.com/LiveMetrics"}]

    profiles = [
        ("ScaleProfile", base_links + scale_extras),
        ("LiveMetricsProfile", live_extras),
    ]

    for profile, links in profiles:
        # Ensure the bookmarks bar is enabled
        show_bookmarks_bar(profile)

        # Build bookmark entries
        now = str(int(time.time() * 1e6))
        children = []
        for i, bm in enumerate(links, start=1):
            entry = {
                "date_added": str(int(time.time() * 1e6) + i),
                "guid": str(uuid.uuid4()),
                "id": str(i),
                "name": bm["name"],
                "type": "url",
                "url": bm["url"],
            }
            children.append(entry)

        # Build the bookmarks JSON structure
        bookmarks_data = {
            "checksum": "",
            "roots": {
                "bookmark_bar": {
                    "children": children,
                    "date_added": now,
                    "date_last_used": "0",
                    "date_modified": now,
                    "guid": str(uuid.uuid4()),
                    "id": "1",
                    "name": "Bookmarks bar",
                    "type": "folder",
                },
                "other": {
                    "children": [],
                    "date_added": now,
                    "date_last_used": "0",
                    "date_modified": now,
                    "guid": str(uuid.uuid4()),
                    "id": "2",
                    "name": "Other bookmarks",
                    "type": "folder",
                },
                "synced": {
                    "children": [],
                    "date_added": now,
                    "date_last_used": "0",
                    "date_modified": "0",
                    "guid": str(uuid.uuid4()),
                    "id": "3",
                    "name": "Mobile bookmarks",
                    "type": "folder",
                },
            },
            "version": 1,
        }

        # Write out the bookmarks file
        bookmarks_fp = get_profile_data_path(profile, "Bookmarks")
        os.makedirs(os.path.dirname(bookmarks_fp), exist_ok=True)
        with open(bookmarks_fp, "w", encoding="utf-8") as f:
            json.dump(bookmarks_data, f, indent=4)