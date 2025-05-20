from flask import Flask, request, jsonify
import pyodbc
import threading

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
        DECLARE @PARENT_CONTAINER_ID NVARCHAR(50) = ?;

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

        cursor = conn.cursor()
        cursor.execute("EXEC usp_BrowserControlArrive ?", (tote,)) # Comma needed to send as datatype tuple
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
    
if __name__ == "__main__":
    # Start Flask in a thread so the tray doesn't block it
    flask_thread = threading.Thread(target=lambda: app.run(host="0.0.0.0", port=5000), daemon=True)
    flask_thread.start()

    # Keep the main thread alive so the service doesn't exit
    try:
        while True:
            threading.Event().wait()
    except KeyboardInterrupt:
        pass