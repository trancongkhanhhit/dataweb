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
        return "Không có SKU"

    try:
        res = requests.get(
            f"{wc_api_url}/products",
            params={"sku": sku},
            auth=HTTPBasicAuth(wc_key, wc_secret),
        )
        if res.status_code != 200:
            return "Lỗi API"
        data = res.json()
        if not data:
            return "Không tìm thấy"
        product = data[0]
        return product.get("regular_price", "0")
    except Exception as e:
        return f"Lỗi: {e}"

# ====== Cào giá từ website đối thủ ======
def get_price(driver, url):
    try:
        if not url:
            return "Không có URL"

        driver.get(url)
        time.sleep(2)

        if "ketnoitieudung.vn" in url:
            els = driver.find_elements(By.CSS_SELECTOR, "span.product-card__main-price")
            if els:
                return els[-1].text.strip()

        elif "boschvn.com" in url:
            els = driver.find_elements(By.CSS_SELECTOR, "span.woocommerce-Price-amount.amount bdi")
            if els:
                text = els[0].text.strip().replace("\xa0", "").replace("₫", "").strip()
                return text + " ₫"

        return "Không tìm thấy giá"

    except Exception as e:
        return f"Lỗi: {e}"

# ====== Chạy toàn bộ cào giá + lấy giá Woo ======
def run_scraper(progress_callback=None):
    client = get_google_client()
    ws = client.open_by_url(SHEET_URL).get_worksheet(0)
    df = pd.DataFrame(ws.get_all_records())

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

        df.at[i, "price1"] = get_price(driver, url1)
        df.at[i, "price2"] = get_woocommerce_price(model)
        df.at[i, "date"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if progress_callback:
            progress_callback(i + 1, total)

    driver.quit()

    ws.update([df.columns.values.tolist()] + df.values.tolist())
    df.to_excel(EXCEL_FILE, index=False)
    print(f"✅ Hoàn tất. File Excel tại: {EXCEL_FILE}")
