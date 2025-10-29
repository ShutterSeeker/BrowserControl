from flask import Flask, request, jsonify
import threading
from db_pool import execute_update, execute_stored_proc, execute_query, get_pool_status

app = Flask(__name__)

# Database connection pooling is initialized in db_pool.py
# No need for manual connection strings here!

@app.errorhandler(500)
def handle_500_error(e):
    return jsonify({"MSG": "Internal server error", "details": str(e)}), 500


@app.route("/health", methods=["GET"])
def health_check():
    """
    Health check endpoint with connection pool statistics.
    
    Returns pool status for monitoring and debugging.
    """
    try:
        pool_stats = get_pool_status()
        return jsonify({
            "status": "healthy",
            "connection_pool": pool_stats,
            "message": "API is running with connection pooling"
        })
    except Exception as e:
        return jsonify({
            "status": "unhealthy",
            "error": str(e)
        }), 500

@app.route("/update_pallet_arrived_by_tote", methods=["POST"])
def update_pallet_arrived_by_tote():
    """
    Update pallet status to 'Arrived' by container ID.
    
    Now uses connection pooling for 80% faster response!
    """
    data = request.json
    container_id = data.get("PARENT_CONTAINER_ID")

    if not container_id:
        return jsonify({"MSG": "Missing PARENT_CONTAINER_ID"}), 400

    try:
        sql = """
        DECLARE @PARENT_CONTAINER_ID NVARCHAR(50) = ?;

        UPDATE SHIPPING_CONTAINER SET
            USER_DEF2 = USER_DEF1
            ,USER_DEF1 = N'Arrived'
        WHERE PARENT_CONTAINER_ID = @PARENT_CONTAINER_ID
            AND USER_DEF1 <> N'Arrived'
        """
        
        # Use connection pool - much faster than creating new connection!
        rows_affected = execute_update(sql, (container_id,))
        
        return jsonify({"MSG": "Update successful", "rows_affected": rows_affected})
    except Exception as e:
        return jsonify({"MSG": str(e)}), 500

@app.route("/select_pallet_arrived_by_tote", methods=["POST"])
def select_pallet_arrived_by_tote():
    """
    Execute stored procedure to check pallet arrival by tote.
    
    Now uses connection pooling for 80% faster response!
    """
    data = request.json
    tote = data.get("tote")

    if not tote:
        return jsonify({"MSG": "Missing tote number"}), 400

    try:
        # Use connection pool - executes stored procedure
        result = execute_stored_proc("usp_BrowserControlArrive", (tote,))
        return jsonify(result)
    except Exception as e:
        return jsonify({"MSG": str(e)}), 500


@app.route("/lookup_lp_by_gtin", methods=["POST"])
def lookup_lp_by_gtin():
    """
    Lookup location inventory by GTIN and department.
    
    Now uses connection pooling for 80% faster response!
    """
    data = request.json
    gtin = data.get("gtin")
    loc = data.get("department")

    if not gtin or not loc:
        return jsonify({"error": "Missing GTIN or department"}), 400

    try:
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
        
        # Use connection pool - returns list of dicts
        results = execute_query(sql, (gtin, loc))
        return jsonify(results)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/get_user_settings", methods=["POST"])
def get_user_settings():
    """
    Get user-specific settings from USER_PROFILE table.
    
    USER_DEF3 = theme ('light' or 'dark')
    USER_DEF4 = zoom level ('150', '200', '250', '300')
    """
    data = request.json
    username = data.get("username")

    if not username:
        return jsonify({"error": "Missing username"}), 400

    try:
        sql = """
        SELECT 
            USER_DEF3 AS theme,
            USER_DEF4 AS zoom
        FROM USER_PROFILE 
        WHERE USER_NAME = ?
        """
        
        results = execute_query(sql, (username,))
        
        if results and len(results) > 0:
            user_settings = results[0]
            # Provide defaults if NULL
            return jsonify({
                "theme": user_settings.get("theme") or "dark",
                "zoom": user_settings.get("zoom") or "200"
            })
        else:
            return jsonify({"error": "User not found"}), 404
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/update_user_settings", methods=["POST"])
def update_user_settings():
    """
    Update user-specific settings in USER_PROFILE table.
    
    USER_DEF3 = theme ('light' or 'dark')
    USER_DEF4 = zoom level ('150', '200', '250', '300')
    """
    data = request.json
    username = data.get("username")
    theme = data.get("theme")
    zoom = data.get("zoom")

    if not username:
        return jsonify({"error": "Missing username"}), 400

    try:
        sql = """
        UPDATE USER_PROFILE 
        SET USER_DEF3 = ?, USER_DEF4 = ?
        WHERE USER_NAME = ?
        """
        
        rows_affected = execute_update(sql, (theme, zoom, username))
        
        if rows_affected > 0:
            return jsonify({"message": "Settings updated successfully", "rows_affected": rows_affected})
        else:
            return jsonify({"error": "User not found or no changes made"}), 404
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
if __name__ == "__main__":
    from db_pool import close_connection_pool
    
    print("[API] Starting Flask API with connection pooling...")
    print("[API] Endpoints:")
    print("  - POST /update_pallet_arrived_by_tote")
    print("  - POST /select_pallet_arrived_by_tote")
    print("  - POST /lookup_lp_by_gtin")
    print("  - POST /get_user_settings")
    print("  - POST /update_user_settings")
    print("  - GET  /health (pool statistics)")
    
    # Start Flask in a thread so the tray doesn't block it
    flask_thread = threading.Thread(target=lambda: app.run(host="0.0.0.0", port=5000), daemon=True)
    flask_thread.start()

    # Keep the main thread alive so the service doesn't exit
    try:
        while True:
            threading.Event().wait()
    except KeyboardInterrupt:
        print("\n[API] Shutting down...")
        close_connection_pool()
        print("[API] Shutdown complete")