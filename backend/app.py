import os
import json
import threading
from flask import Flask, jsonify, send_file, render_template, request
from flask_cors import CORS
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv

import dataset_for_web
from wc_utils import update_price_by_sku  # cập nhật giá WooCommerce theo SKU

# ===== Load .env (local) =====
load_dotenv()

# ===== Get absolute paths =====
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend")

app = Flask(
    __name__,
    template_folder=FRONTEND_DIR,
    static_folder=FRONTEND_DIR,
    static_url_path=""
)
CORS(app)

SHEET_URL = dataset_for_web.SHEET_URL
SCOPES = dataset_for_web.SCOPES

# ===== Google credentials =====
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
    return render_template("index.html")

@app.route("/health")
def health():
    return jsonify({"status": "ok"})

@app.route("/data")
def get_data():
    try:
        sheet = client.open_by_url(SHEET_URL)
        worksheet = sheet.get_worksheet(0)
        data = worksheet.get_all_records()
        # ensure numeric fields are passed as numbers or strings consistently
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
        return jsonify({"percent": percent, "current": progress["current"], "total": progress["total"], "status": "Đang xử lý..."})
    elif progress["status"] == "done":
        return jsonify({"percent": 100, "status": "✅ Hoàn tất"})
    elif isinstance(progress["status"], str) and progress["status"].startswith("error"):
        return jsonify({"percent": 0, "status": progress["status"]})
    return jsonify({"status": "Chưa chạy", "percent": 0})

@app.route("/download")
def download_excel():
    file_path = os.path.join(BASE_DIR, "ketqua_gia.xlsx")
    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True, download_name="ketqua_gia.xlsx")
    return jsonify({"error": "Chưa có file Excel. Hãy chạy 'Cập nhật giá' trước!"}), 404

# ===== Endpoint cập nhật giá WooCommerce (bulk) =====
@app.route("/update-prices", methods=["POST"])
def update_prices_woocommerce():
    """
    Nhận payload:
    {
      "selected_skus": ["SKU1", "SKU2", ...],
      "price_map": { "SKU1": 123000, "SKU2": 456000, ... }   # <-- dùng giá update_price từ frontend
    }
    - Cập nhật WooCommerce (update_price_by_sku)
    - Ghi lại update_price vào Google Sheet
    """
    try:
        data = request.get_json()
        sku_list = data.get("selected_skus", [])
        price_map = data.get("price_map", {})

        # load sheet
        sheet = client.open_by_url(SHEET_URL)
        ws = sheet.get_worksheet(0)
        df = pd.DataFrame(ws.get_all_records())

        results = {}
        for sku in sku_list:
            if sku in price_map:
                new_price = int(price_map[sku]) if price_map[sku] is not None else 0
                success = update_price_by_sku(sku, new_price)
                results[sku] = {"success": success, "new_price": new_price}

                # nếu cập nhật thành công (hoặc không), ghi update_price vào DF để lưu lại
                # tìm các hàng có model==sku
                matches = df.index[df['model'].astype(str) == str(sku)].tolist()
                for idx in matches:
                    df.at[idx, 'update_price'] = new_price
                    # cũng có thể ghi lại price2 là giá trên WC (tùy muốn)
            else:
                results[sku] = {"success": False, "error": "Không có giá trong payload"}

        # lưu lại vào sheet
        ws.update([df.columns.values.tolist()] + df.values.tolist())

        return jsonify(results)

    except Exception as e:
        print(f"❌ Error updating WooCommerce prices: {e}")
        return jsonify({"error": str(e)}), 500

# ===== Endpoint lưu 1 hàng (khi người dùng chỉnh update_price và bấm Lưu) =====
@app.route("/save-row", methods=["POST"])
def save_row():
    """
    Payload:
    {
      "sku": "SKU123",
      "update_price": 123000
    }
    Ghi update_price vào Google Sheet (hàng tương ứng).
    """
    try:
        data = request.get_json()
        sku = data.get("sku")
        update_price = data.get("update_price", 0)

        sheet = client.open_by_url(SHEET_URL)
        ws = sheet.get_worksheet(0)
        df = pd.DataFrame(ws.get_all_records())

        matches = df.index[df['model'].astype(str) == str(sku)].tolist()
        if not matches:
            return jsonify({"success": False, "error": "Không tìm thấy SKU trên sheet"}), 404

        for idx in matches:
            df.at[idx, 'update_price'] = int(update_price)

        ws.update([df.columns.values.tolist()] + df.values.tolist())
        return jsonify({"success": True, "updated_skus": matches})

    except Exception as e:
        print(f"❌ Error save-row: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    print(f"🚀 Starting server on port {port}...")
    app.run(host="0.0.0.0", port=port, debug=False)#
