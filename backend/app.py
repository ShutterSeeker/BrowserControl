from flask import Flask, request, jsonify
import pyodbc
import threading
import pystray
from pystray import MenuItem as item
from PIL import Image, ImageDraw
import os, sys

app = Flask(__name__)

# SQL config
server = "JASPRODSQL09"
database = "ILS"
driver = "{ODBC Driver 17 for SQL Server}"

@app.errorhandler(500)
def handle_500_error(e):
    return jsonify({"MSG": "Internal server error", "details": str(e)}), 500

@app.route("/update_pallet_arrived_by_tote", methods=["POST"])
def update_pallet_arrived_by_tote():
    data = request.json
    container_id = data.get("PARENT_CONTAINER_ID")

    if not container_id:
        return jsonify({"MSG": "Missing PARENT_CONTAINER_ID"}), 400

    try:
        conn = pyodbc.connect(f"""
            DRIVER={driver};
            SERVER={server};
            DATABASE={database};
            Trusted_Connection=yes;
        """)
        sql = """
        UPDATE SHIPPING_CONTAINER SET
            USER_DEF2 = USER_DEF1
            ,USER_DEF1 = N'Arrived'
        WHERE PARENT_CONTAINER_ID = @PARENT_CONTAINER_ID
            AND USER_DEF1 <> N'Arrived'
        """ 

        cursor = conn.cursor()
        cursor.execute(sql, (container_id,))
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({"MSG": "Update successful"})
    except Exception as e:
        return jsonify({"MSG": str(e)}), 500

@app.route("/select_pallet_arrived_by_tote", methods=["POST"])
def select_pallet_arrived_by_tote():
    data = request.json
    tote = data.get("tote")

    if not tote:
        return jsonify({"MSG": "Missing tote number"}), 400

    try:
        conn = pyodbc.connect(f"""
            DRIVER={driver};
            SERVER={server};
            DATABASE={database};
            Trusted_Connection=yes;
        """)
        sql = """
        DECLARE @TOTEID NVARCHAR(50) = ?;

        DECLARE @TREE_UNIT NUMERIC(9,0);
        DECLARE @ActivePallets TABLE (
            TREE_UNIT NUMERIC(9,0),
            PARENT_CONTAINER_ID NVARCHAR(25),
            INTERNAL_SHIPMENT_NUM NUMERIC(9,0),
            PARENT NUMERIC(9,0),
            IN_PROCESS BIT
        );

        -- Fill table with filtered results.
        INSERT INTO @ActivePallets
        SELECT 
            TREE_UNIT, PARENT_CONTAINER_ID, INTERNAL_SHIPMENT_NUM, PARENT
            ,IN_PROCESS = ISNULL((SELECT TOP 1 1 FROM SHIPPING_CONTAINER SCC WITH (NOLOCK) WHERE SCC.TREE_UNIT = SC.TREE_UNIT AND SCC.USER_DEF1 = N'Arrived'), 0)
        FROM SHIPPING_CONTAINER SC WITH (NOLOCK)
        WHERE STATUS = 401
            AND TREE_UNIT NOT IN (
                SELECT TREE_UNIT FROM SHIPPING_CONTAINER WHERE USER_DEF1 = N'Dropped'
            )
            AND (USER_DEF1 = @TOTEID OR USER_DEF2 = @TOTEID);

        -- Early exit if tote is on multiple pallets that are in the same IN_PROCESS status.
        IF EXISTS (
            SELECT TOP 1 N'X'
            FROM @ActivePallets
            GROUP BY TREE_UNIT, IN_PROCESS
            HAVING COUNT(DISTINCT TREE_UNIT) > 1
        )
        BEGIN
            SELECT
                MSG = N'Tote exists on multiple active pallets'
                ,PARENT_CONTAINER_ID = N''
                ,TOTES_IN_TRANSIT = N''
            RETURN
        END

        -- Find TREE_UNIT.
        SELECT TOP 1 @TREE_UNIT = TREE_UNIT FROM @ActivePallets ORDER BY IN_PROCESS DESC -- prefer pallets in process

        IF @TREE_UNIT IS NOT NULL
        BEGIN
            -- Get pallet, shipment ID, and customer.
            SELECT TOP 1 
                MSG = N''
                ,PARENT_CONTAINER_ID
                ,TOTES_IN_TRANSIT = (
                    SELECT COUNT(DISTINCT SC.USER_DEF1)
                    FROM SHIPPING_CONTAINER SC WITH (NOLOCK)
                    WHERE SC.TREE_UNIT = @TREE_UNIT AND SC.USER_DEF1 IS NOT NULL AND SC.USER_DEF1 <> N'Arrived'
                )
            FROM
                @ActivePallets AP
                LEFT JOIN SHIPMENT_HEADER SH WITH (NOLOCK) ON SH.INTERNAL_SHIPMENT_NUM = AP.INTERNAL_SHIPMENT_NUM
            WHERE
                AP.PARENT = @TREE_UNIT
            RETURN
        END
        ELSE
        BEGIN
            SELECT
                MSG = N'No pallet found'
                ,PARENT_CONTAINER_ID = N''
                ,TOTES_IN_TRANSIT = N''

            RETURN
        END
        """

        cursor = conn.cursor()
        cursor.execute(sql, (tote,))
        row = cursor.fetchone()
        columns = [desc[0] for desc in cursor.description]
        result = dict(zip(columns, row))
        cursor.close()
        conn.close()
        return jsonify(result)
    except Exception as e:
        return jsonify({"MSG": str(e)}), 500


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
    
def resource_path(rel_path):
    # when frozen by PyInstaller, files are unpacked to _MEIPASS
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel_path)


def get_path(file):
    # if frozen (running as EXE), look next to the EXE
    if getattr(sys, "frozen", False):
        return os.path.join(os.path.dirname(sys.executable), file)
    # else (running from source), load the one in browser_control/
    return resource_path(file)

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

def run_tray():
    icon = pystray.Icon("BrowserControlAPI")
    icon.icon = create_image()
    icon.title = "Browser Control API"
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
