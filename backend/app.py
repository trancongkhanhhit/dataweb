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

# ===== Get absolute paths =====
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend")

print(f"📁 BASE_DIR: {BASE_DIR}")
print(f"📁 FRONTEND_DIR: {FRONTEND_DIR}")
print(f"📁 Files in frontend: {os.listdir(FRONTEND_DIR) if os.path.exists(FRONTEND_DIR) else 'NOT FOUND'}")

# ===== Flask config =====
app = Flask(__name__, 
            template_folder=BASE_DIR,  # <-- Sửa ở đây
            static_folder=BASE_DIR,    # <-- Sửa ở đây
            static_url_path='')
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
        print(f"❌ Error in scraper: {e}")

# ===== Routes =====
@app.route("/")
def index():
    try:
        return render_template("index.html")
    except Exception as e:
        return jsonify({
            "error": str(e), 
            "template_folder": app.template_folder,
            "files": os.listdir(app.template_folder) if os.path.exists(app.template_folder) else []
        }), 500

@app.route("/health")
def health():
    return jsonify({
        "status": "ok", 
        "message": "Server is running",
        "template_folder": app.template_folder,
        "static_folder": app.static_folder
    })

@app.route("/data")
def get_data():
    try:
        sheet = client.open_by_url(SHEET_URL)
        worksheet = sheet.get_worksheet(0)
        data = worksheet.get_all_records()
        return jsonify(data)
    except Exception as e:
        print(f"❌ Error getting data: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/update")
def update_prices():
    try:
        t = threading.Thread(target=run_update_process)
        t.start()
        return jsonify({"status": "started"})
    except Exception as e:
        print(f"❌ Error starting update: {e}")
        return jsonify({"error": str(e)}), 500

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
    return jsonify({"status": "Chưa chạy", "percent": 0})

@app.route("/download")
def download_excel():
    file_path = os.path.join(BASE_DIR, "ketqua_gia.xlsx")
    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True, download_name="ketqua_gia.xlsx")
    return jsonify({"error": "Chưa có file Excel. Hãy chạy 'Cập nhật giá' trước!"}), 404

# ===== Run server =====
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    print(f"🚀 Starting server on port {port}...")
    app.run(host="0.0.0.0", port=port, debug=False)