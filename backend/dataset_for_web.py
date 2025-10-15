import os
import json
import time
import datetime
import requests
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from requests.auth import HTTPBasicAuth

# ===== Config =====
SHEET_URL = "https://docs.google.com/spreadsheets/d/1UZ-wwMFWwQYwOUh91_h4U6tUQLl5zjgpPlWov9B21yg/edit"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
EXCEL_FILE = os.path.join(BASE_DIR, "ketqua_gia.xlsx")

# ====== Google Sheets client ======
def get_google_client():
    if os.environ.get("GOOGLE_CREDENTIALS"):
        creds_dict = json.loads(os.environ["GOOGLE_CREDENTIALS"])
        creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    else:
        raise RuntimeError("Thiếu GOOGLE_CREDENTIALS trong .env")
    return gspread.authorize(creds)

# ====== Lấy giá WooCommerce theo SKU ======
def get_woocommerce_price(sku):
    wc_api_url = os.environ.get("WC_API_URL")
    wc_key = os.environ.get("WC_CONSUMER_KEY")
    wc_secret = os.environ.get("WC_CONSUMER_SECRET")

    if not sku:
        return "0"

    try:
        res = requests.get(
            f"{wc_api_url}/products",
            params={"sku": sku},
            auth=HTTPBasicAuth(wc_key, wc_secret),
        )
        if res.status_code != 200:
            return "0"
        data = res.json()
        if not data:
            return "0"
        product = data[0]
        return product.get("regular_price", "0") or "0"
    except Exception as e:
        return "0"

# ====== Cào giá từ website đối thủ ======
def get_price(driver, url):
    try:
        if not url:
            return "0"

        driver.get(url)
        time.sleep(1.5)

        # một số selector ví dụ, giữ fallback
        if "ketnoitieudung.vn" in url:
            els = driver.find_elements(By.CSS_SELECTOR, "span.product-card__main-price")
            if els:
                return els[-1].text.strip()

        elif "boschvn.com" in url:
            els = driver.find_elements(By.CSS_SELECTOR, "span.woocommerce-Price-amount.amount bdi")
            if els:
                text = els[0].text.strip().replace("\xa0", "").replace("₫", "").strip()
                return text + " ₫"

        # fallback: tìm format số có chữ ₫
        els = driver.find_elements(By.XPATH, "//*[contains(text(),'₫') or contains(text(),'đ') or contains(text(),'VND')]")
        for e in els:
            t = e.text.strip()
            if t:
                return t

        return "0"

    except Exception as e:
        return "0"

# ===== helper parse price string -> int (vnđ) =====
def parse_price_to_int(val):
    if val is None:
        return 0
    if isinstance(val, (int, float)):
        return int(val)
    s = str(val)
    # remove non-digit
    s2 = ''.join(ch for ch in s if ch.isdigit())
    try:
        return int(s2) if s2 else 0
    except:
        return 0

# ====== Chạy toàn bộ cào giá + lấy giá Woo ======
def run_scraper(progress_callback=None):
    client = get_google_client()
    ws = client.open_by_url(SHEET_URL).get_worksheet(0)
    df = pd.DataFrame(ws.get_all_records())

    # Ensure columns exist (so updates won't break)
    for col in ["price1", "price-1", "change", "percent_change", "update_price", "price2", "date"]:
        if col not in df.columns:
            df[col] = ""

    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    driver = webdriver.Chrome(options=options)

    total = len(df)
    for i, row in df.iterrows():
        model = row.get("model")
        url1 = row.get("url1")

        print(f"🔍 ({i+1}/{total}) {model}")

        # lấy giá mới từ đối thủ
        raw_new = get_price(driver, url1)
        new_price_num = parse_price_to_int(raw_new)

        # giữ giá trước đó (price1 cũ -> price-1)
        old_price_val = row.get("price1", "")
        old_price_num = parse_price_to_int(old_price_val)

        # cập nhật các trường
        df.at[i, "price-1"] = old_price_num
        df.at[i, "price1"] = new_price_num
        df.at[i, "change"] = new_price_num - old_price_num
        if old_price_num:
            try:
                df.at[i, "percent_change"] = round(((new_price_num - old_price_num) / old_price_num) * 100, 2)
            except:
                df.at[i, "percent_change"] = 0
        else:
            df.at[i, "percent_change"] = 0
        df.at[i, "update_price"] = max(new_price_num - 5000, 0)

        # lấy giá WooCommerce hiện tại
        df.at[i, "price2"] = get_woocommerce_price(model)

        df.at[i, "date"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if progress_callback:
            progress_callback(i + 1, total)

    driver.quit()

    # ghi lại sheet (ghi toàn bộ bảng)
    ws.update([df.columns.values.tolist()] + df.values.tolist())
    df.to_excel(EXCEL_FILE, index=False)
    print(f"✅ Hoàn tất. File Excel tại: {EXCEL_FILE}")
