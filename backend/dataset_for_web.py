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

SHEET_URL = "https://docs.google.com/spreadsheets/d/1UZ-wwMFWwQYwOUh91_h4U6tUQLl5zjgpPlWov9B21yg/edit"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
EXCEL_FILE = os.path.join(BASE_DIR, "ketqua_gia.xlsx")


# ====== Kết nối Google Sheet ======
def get_google_client():
    if os.environ.get("GOOGLE_CREDENTIALS"):
        creds_dict = json.loads(os.environ["GOOGLE_CREDENTIALS"])
        creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    else:
        raise RuntimeError("Thiếu GOOGLE_CREDENTIALS trong .env")
    return gspread.authorize(creds)


# ====== Lấy giá WooCommerce ======
def get_woocommerce_price(sku):
    wc_api_url = os.environ.get("WC_API_URL")
    wc_key = os.environ.get("WC_CONSUMER_KEY")
    wc_secret = os.environ.get("WC_CONSUMER_SECRET")

    if not sku:
        return 0

    try:
        res = requests.get(
            f"{wc_api_url}/products",
            params={"sku": sku},
            auth=HTTPBasicAuth(wc_key, wc_secret),
        )
        if res.status_code != 200:
            return 0
        data = res.json()
        if not data:
            return 0
        product = data[0]
        return int(float(product.get("regular_price", "0") or 0))
    except Exception:
        return 0


# ====== Hàm cào giá ======
def get_price(driver, url):
    try:
        if not url:
            return 0
        driver.get(url)
        time.sleep(1.5)

        if "ketnoitieudung.vn" in url:
            els = driver.find_elements(By.CSS_SELECTOR, "span.product-card__main-price")
            if els:
                return els[-1].text.strip()

        if "boschvn.com" in url:
            els = driver.find_elements(By.CSS_SELECTOR, "span.woocommerce-Price-amount.amount bdi")
            if els:
                text = els[0].text.strip().replace("\xa0", "").replace("₫", "").strip()
                return text + " ₫"

        els = driver.find_elements(By.XPATH, "//*[contains(text(),'₫')]")
        if els:
            return els[0].text.strip()
        return 0
    except Exception:
        return 0


def parse_price_to_int(val):
    if not val:
        return 0
    if isinstance(val, (int, float)):
        return int(val)
    s = ''.join(ch for ch in str(val) if ch.isdigit())
    return int(s) if s else 0


# ====== Hàm chính ======
def run_scraper(progress_callback=None):
    client = get_google_client()
    ws = client.open_by_url(SHEET_URL).get_worksheet(0)
    df = pd.DataFrame(ws.get_all_records())

    for col in ["price1", "price-1", "change", "percent_change", "update_price", "price2", "date"]:
        if col not in df.columns:
            df[col] = ""

    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    driver = webdriver.Chrome(options=options)

    total = len(df)
    for i, row in df.iterrows():
        sku = row.get("model")
        url1 = row.get("url1")

        old_price_num = parse_price_to_int(row.get("price1", 0))
        new_price_raw = get_price(driver, url1)
        new_price_num = parse_price_to_int(new_price_raw)
        woo_price = get_woocommerce_price(sku)

        # ---- Tính đúng công thức ----
# Làm sạch dữ liệu về đơn vị
        old_price_num = int(str(old_price_num).replace('.', '').replace(',', '').strip() or 0)
        new_price_num = int(str(new_price_num).replace('.', '').replace(',', '').strip() or 0)

        change_val = new_price_num - old_price_num
        percent_val = ((change_val / old_price_num) * 100) if old_price_num else 0


        df.at[i, "price-1"] = old_price_num
        df.at[i, "price1"] = new_price_num
        df.at[i, "change"] = change_val
        df.at[i, "percent_change"] = round(percent_val, 2)  # ví dụ -15.06%
        df.at[i, "update_price"] = max(new_price_num - 5000, 0)
        df.at[i, "price2"] = woo_price
        df.at[i, "date"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if progress_callback:
            progress_callback(i + 1, total)

    driver.quit()
    ws.update([df.columns.values.tolist()] + df.values.tolist())
    df.to_excel(EXCEL_FILE, index=False)
    print(f"✅ Đã cập nhật file: {EXCEL_FILE}")
