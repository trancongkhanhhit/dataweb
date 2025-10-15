import os, json, threading
from flask import Flask, jsonify, send_file, render_template, request
from flask_cors import CORS
import gspread, pandas as pd
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv

import dataset_for_web
from wc_utils import update_price_by_sku

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend")

app = Flask(__name__, template_folder=FRONTEND_DIR, static_folder=FRONTEND_DIR, static_url_path="")
CORS(app)

SHEET_URL = dataset_for_web.SHEET_URL
SCOPES = dataset_for_web.SCOPES

cred_file = os.path.join(BASE_DIR, "n8n-credential-452204-cd6aa6fc1a25.json")
if os.path.exists(cred_file):
    creds = Credentials.from_service_account_file(cred_file, scopes=SCOPES)
else:
    raise RuntimeError("⚠️ Không tìm thấy file Google credentials.")

client = gspread.authorize(creds)
progress = {"current": 0, "total": 0, "status": "idle"}

def update_progress(current, total):
    progress["current"] = current
    progress["total"] = total
    progress["status"] = "running"

def run_update_process():
    try:
        progress["status"] = "running"
        dataset_for_web.run_scraper(progress_callback=update_progress)
        progress["status"] = "done"
    except Exception as e:
        progress["status"] = f"error: {e}"

@app.route("/")
def index(): return render_template("index.html")

@app.route("/data")
def get_data():
    try:
        ws = client.open_by_url(SHEET_URL).get_worksheet(0)
        data = ws.get_all_records()
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/update")
def update_prices():
    t = threading.Thread(target=run_update_process)
    t.start()
    return jsonify({"status": "started"})

@app.route("/progress")
def get_progress():
    if progress["status"] == "running":
        total = progress["total"] or 1
        percent = round(progress["current"] / total * 100, 1)
        return jsonify({"percent": percent, "status": "Đang xử lý..."})
    elif progress["status"] == "done":
        return jsonify({"percent": 100, "status": "✅ Hoàn tất"})
    elif isinstance(progress["status"], str) and progress["status"].startswith("error"):
        return jsonify({"percent": 0, "status": progress["status"]})
    return jsonify({"percent": 0, "status": "Chưa chạy"})

@app.route("/download_excel")
def download_excel():
    path = os.path.join(BASE_DIR, "ketqua_gia.xlsx")
    if os.path.exists(path):
        return send_file(path, as_attachment=True, download_name="ketqua_gia.xlsx")
    return jsonify({"error": "Chưa có file Excel"}), 404

@app.route("/update-prices", methods=["POST"])
def update_prices_wc():
    data = request.get_json()
    sku_list = data.get("selected_skus", [])
    price_map = data.get("price_map", {})

    ws = client.open_by_url(SHEET_URL).get_worksheet(0)
    df = pd.DataFrame(ws.get_all_records())

    results = {}
    for sku in sku_list:
        new_price = int(price_map.get(sku, 0))
        ok = update_price_by_sku(sku, new_price)
        results[sku] = {"success": ok, "new_price": new_price}
        idxs = df.index[df["model"].astype(str) == str(sku)].tolist()
        for i in idxs:
            df.at[i, "update_price"] = new_price

    ws.update([df.columns.values.tolist()] + df.values.tolist())
    return jsonify(results)

@app.route("/save-row", methods=["POST"])
def save_row():
    data = request.get_json()
    sku = data.get("sku")
    update_price = int(data.get("update_price", 0))
    ws = client.open_by_url(SHEET_URL).get_worksheet(0)
    df = pd.DataFrame(ws.get_all_records())

    idxs = df.index[df["model"].astype(str) == str(sku)].tolist()
    if not idxs:
        return jsonify({"success": False, "error": "Không tìm thấy SKU"}), 404
    for i in idxs:
        df.at[i, "update_price"] = update_price

    ws.update([df.columns.values.tolist()] + df.values.tolist())
    return jsonify({"success": True})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
