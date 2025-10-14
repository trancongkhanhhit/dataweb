import os
import json
import threading
from flask import Flask, jsonify, send_file, render_template
from flask_cors import CORS
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
import dataset_for_web
from dotenv import load_dotenv

# ===== Load .env (local) =====
load_dotenv()

# ===== Flask config =====
app = Flask(__name__, 
            template_folder="../frontend",  # HTML + CSS chung 1 folder
            static_folder="../frontend")    # CSS + JS cùng folder
CORS(app)

# ===== Google Sheet =====
SHEET_URL = "https://docs.google.com/spreadsheets/d/1UZ-wwMFWwQYwOUh91_h4U6tUQLl5zjgpPlWov9B21yg/edit"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets",
          "https://www.googleapis.com/auth/drive"]

# ===== Load Google credentials =====
if os.environ.get("GOOGLE_CREDENTIALS"):
    creds_dict = json.loads(os.environ["GOOGLE_CREDENTIALS"])
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
else:
    raise RuntimeError("Thiếu biến môi trường GOOGLE_CREDENTIALS")

client = gspread.authorize(creds)

# ===== Progress =====
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

# ===== Routes =====
@app.route("/")
def index():
    return render_template("index.html")  # sẽ tìm index.html trong frontend/

@app.route("/data")
def get_data():
    sheet = client.open_by_url(SHEET_URL)
    worksheet = sheet.get_worksheet(0)
    data = worksheet.get_all_records()
    return jsonify(data)

@app.route("/update")
def update_prices():
    t = threading.Thread(target=run_update_process)
    t.start()
    return jsonify({"status": "started"})

@app.route("/progress")
def get_progress():
    if progress["status"] == "running":
        total = progress["total"] or 1
        percent = round((progress["current"] / total) * 100, 1)
        return jsonify({
            "percent": percent,
            "current": progress["current"],
            "total": progress["total"],
            "status": "Đang xử lý..."
        })
    elif progress["status"] == "done":
        return jsonify({"percent": 100, "status": "✅ Hoàn tất"})
    elif progress["status"].startswith("error"):
        return jsonify({"percent": 0, "status": progress["status"]})
    return jsonify({"status": "Chưa chạy"})

@app.route("/download")
def download_excel():
    file_path = "ketqua_gia.xlsx"
    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True)
    return jsonify({"error": "Chưa có file Excel"}), 404

# ===== Run server =====
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))  # Render tự set PORT
    app.run(host="0.0.0.0", port=port)
