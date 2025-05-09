from flask import Flask, request, jsonify
import pyodbc
import threading
import pystray
from pystray import MenuItem as item
from PIL import Image, ImageDraw
import os

app = Flask(__name__)

# SQL config
server = "JASPRODSQL09"
database = "ILS"
driver = "{ODBC Driver 17 for SQL Server}"

@app.route("/lookup_lp_by_gtin", methods=["POST"])
def lookup_lp_by_gtin():
    data = request.json
    gtin = data.get("gtin")
    loc = data.get("department")

    if not gtin or not loc:
        return jsonify({"error": "Missing GTIN or department"}), 400

    try:
        conn = pyodbc.connect(f"""
            DRIVER={driver};
            SERVER={server};
            DATABASE={database};
            Trusted_Connection=yes;
        """)
        sql = """
        DECLARE @GTIN NVARCHAR(50) = ?;
        DECLARE @LOCATION NVARCHAR(50) = ?;

        SELECT
            LI.LOCATION,
            LI.ITEM,
            ON_HAND_QTY = CONVERT(INT, LI.ON_HAND_QTY),
            TO_LOC = LI.USER_DEF1,
            LI.LOGISTICS_UNIT,
            UM_MATCH = CASE WHEN ICR.QUANTITY_UM = RIGHT(LEFT(LI.USER_DEF1, 7), 2) THEN 1 ELSE 0 END
        FROM LOCATION_INVENTORY LI
        INNER JOIN ITEM_CROSS_REFERENCE ICR ON ICR.ITEM = LI.ITEM
        WHERE
            ICR.X_REF_ITEM = @GTIN
            AND LI.TEMPLATE_FIELD1 = N'DECANT'
            AND LI.ON_HAND_QTY > 0
        ORDER BY
            CASE
                WHEN LI.LOCATION = @LOCATION THEN N'A'
                WHEN LI.TEMPLATE_FIELD2 = N'WS' THEN N'AB'
                ELSE LI.LOCATION
            END;
        """
        cursor = conn.cursor()
        cursor.execute(sql, (gtin, loc))
        columns = [col[0] for col in cursor.description]
        results = [dict(zip(columns, row)) for row in cursor.fetchall()]
        cursor.close()
        conn.close()
        return jsonify(results)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def create_image():
    # Simple black square icon
    image = Image.new('RGB', (64, 64), "black")
    d = ImageDraw.Draw(image)
    d.rectangle([16, 16, 48, 48], fill="white")
    return image

def run_tray():
    icon = pystray.Icon("BackendAPI")
    icon.icon = create_image()
    icon.title = "Backend API"
    icon.menu = pystray.Menu(
        item("Quit", lambda: stop_app(icon))
    )
    icon.run()

def stop_app(icon):
    icon.stop()
    print("Tray icon stopped. Exiting app...")
    os._exit(0)

if __name__ == "__main__":
    # Start Flask in a thread so the tray doesn't block it
    flask_thread = threading.Thread(target=lambda: app.run(host="0.0.0.0", port=5000), daemon=True)
    flask_thread.start()

    # Start tray icon
    run_tray()
