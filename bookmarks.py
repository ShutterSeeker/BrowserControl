import os, time, uuid, json

def generate_bookmarks(department: str):
    """
    Create Chrome bookmark JSON for ScaleProfile based on department.
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))
    bookmarks_path = os.path.join(base_dir, "profiles", "ScaleProfile", "Default", "Bookmarks")

    # Base and department-specific links
    base = [{"name": "RF", "url": "https://scale20.byjasco.com/RF/SignonMenuRF.aspx"}]
    extras = []
    if department.startswith("DECANT.WS"):
        extras += [
            {"name": "Inventory", "url": "https://scale20.byjasco.com/scale/insights/2723"},
            {"name": "Transaction history", "url": "https://scale20.byjasco.com/scale/insights/4026"},
        ]
    if department.startswith("PalletizingStation"):
        extras.append({"name": "Shipping container", "url": "https://scale20.byjasco.com/scale/insights/4026"})
    if department == "Packing":
        extras += [
            {"name": "Packing", "url": "https://scale20.byjasco.com/scale/trans/packing"},
            {"name": "Transaction history", "url": "https://scale20.byjasco.com/scale/insights/4026"},
        ]

    all_links = base + extras

    def create_entry(i, bm):
        return {
            "date_added": f"{13390000000000000 + i}",
            "guid": str(uuid.uuid4()),
            "id": str(i),
            "name": bm["name"],
            "type": "url",
            "url": bm["url"],
        }

    children = [create_entry(i + 1, bm) for i, bm in enumerate(all_links)]
    now = str(int(time.time() * 1e6))

    bookmarks = {
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
            "other":  {"children": [], "date_added": now, "date_last_used": "0",
                       "date_modified": now, "guid": str(uuid.uuid4()), "id": "2",
                       "name": "Other bookmarks", "type": "folder"},
            "synced": {"children": [], "date_added": now, "date_last_used": "0",
                       "date_modified": "0", "guid": str(uuid.uuid4()), "id": "3",
                       "name": "Mobile bookmarks", "type": "folder"},
        },
        "version": 1
    }

    os.makedirs(os.path.dirname(bookmarks_path), exist_ok=True)
    with open(bookmarks_path, "w") as f:
        json.dump(bookmarks, f, indent=4)