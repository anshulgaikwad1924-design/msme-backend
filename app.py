from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
import os
from model import forecast_demand, analyze_inventory, calculate_revenue_risk
from whatsapp import send_whatsapp_alert
load_dotenv()
app = Flask(__name__)
CORS(app, origins=["https://anshulgaikwad1924-design.github.io"])
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024
ALLOWED_EXTENSIONS = {"csv", "xlsx", "xls"}
def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
@app.route("/api/forecast", methods=["POST"])
def forecast():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    file = request.files["file"]
    if file.filename == "" or not allowed_file(file.filename):
        return jsonify({"error": "Invalid file"}), 400
    try:
        result = forecast_demand(file)
        return jsonify(result), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        app.logger.exception(e)
        return jsonify({"error": "Forecast failed"}), 500
@app.route("/api/inventory-status", methods=["POST"])
def inventory_status():
    data = request.get_json()
    if not data or "products" not in data:
        return jsonify({"error": "Send JSON with products array"}), 400
    try:
        return jsonify(analyze_inventory(data["products"])), 200
    except Exception as e:
        app.logger.exception(e)
        return jsonify({"error": "Inventory analysis failed"}), 500
@app.route("/api/revenue-risk", methods=["POST"])
def revenue_risk():
    data = request.get_json()
    if not data or "products" not in data:
        return jsonify({"error": "Send JSON with products array"}), 400
    try:
        return jsonify(calculate_revenue_risk(data["products"])), 200
    except Exception as e:
        app.logger.exception(e)
        return jsonify({"error": "Revenue risk failed"}), 500
@app.route("/api/whatsapp-alert", methods=["POST"])
def whatsapp_alert():
    import re
    data = request.get_json()
    required = ["supplier_phone", "product", "current_stock", "reorder_qty"]
    if not data or not all(k in data for k in required):
        return jsonify({"error": f"Required fields: {required}"}), 400
    phone = data["supplier_phone"]
    if not re.match(r"^\+\d{10,15}$", phone):
        return jsonify({"error": "Invalid phone number"}), 400
    try:
        return jsonify(send_whatsapp_alert(supplier_phone=phone, product=data["product"], current_stock=data["current_stock"], reorder_qty=data["reorder_qty"], days_left=data.get("days_left","N/A"), store_name=data.get("store_name","MSME Store"))), 200
    except Exception as e:
        app.logger.exception(e)
        return jsonify({"error": "WhatsApp alert failed"}), 500
@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "message": "MSME Demand Forecaster API running"}), 200
if __name__ == "__main__":
    app.run(debug=os.getenv("FLASK_DEBUG","0")=="1", port=5000)
