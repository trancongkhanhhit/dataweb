import pandas as pd, gspread, datetime, time, os, json
from google.oauth2.service_account import Credentials
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

SHEET_URL = "https://docs.google.com/spreadsheets/d/1UZ-wwMFWwQYwOUh91_h4U6tUQLl5zjgpPlWov9B21yg/edit"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets",
          "https://www.googleapis.com/auth/drive"]

# Đường dẫn file Excel tuyệt đối
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
EXCEL_FILE = os.path.join(BASE_DIR, "ketqua_gia.xlsx")

def get_google_client():
    if os.environ.get("GOOGLE_CREDENTIALS"):
        creds_dict = json.loads(os.environ["GOOGLE_CREDENTIALS"])
        creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    else:
        creds = Credentials.from_service_account_file(
            os.path.join(BASE_DIR, "n8n-credential-452204-cd6aa6fc1a25.json"),
            scopes=SCOPES
        )
    client = gspread.authorize(creds)
    return client

def get_price(driver, url):
    try:
        if not url: return "Không có URL"
        driver.get(url)
        time.sleep(2)
        if "ketnoitieudung.vn" in url:
            els = driver.find_elements(By.CSS_SELECTOR, "span.product-card__main-price")
            if els: return els[-1].text.strip()
        elif "3rtech.vn" in url:
            els = driver.find_elements(By.CSS_SELECTOR, "span.woocommerce-Price-amount.amount bdi")
            if els: return els[0].text.strip() + " ₫"
        return "Không tìm thấy giá"
    except Exception as e:
        return f"Lỗi: {e}"

def run_scraper(progress_callback=None):
    client = get_google_client()
    ws = client.open_by_url(SHEET_URL).get_worksheet(0)
    df = pd.DataFrame(ws.get_all_records())

    # Setup Chrome
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    # Local hoặc Render
    CHROMEDRIVER_PATH = os.environ.get(
        "CHROMEDRIVER_PATH",
        "D:\\6.WORKING\\1. DATAWEB\\chromedriver-win64\\chromedriver-win64\\chromedriver.exe"
    )
    driver = webdriver.Chrome(service=Service(CHROMEDRIVER_PATH), options=options)

    total = len(df)
    for i, row in df.iterrows():
        model = row.get("model")
        url1, url2 = row.get("url1"), row.get("url2")
        print(f"🔍 ({i+1}/{total}) {model}")

        df.at[i, "price1"] = get_price(driver, url1)
        time.sleep(1)
        df.at[i, "price2"] = get_price(driver, url2)
        df.at[i, "date"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if progress_callback:
            progress_callback(i+1, total)

    ws.update([df.columns.values.tolist()] + df.values.tolist())

    df.to_excel(EXCEL_FILE, index=False)
    driver.quit()
    print(f"✅ Hoàn tất. File Excel tại: {EXCEL_FILE}")
