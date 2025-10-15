import os
import requests
from dotenv import load_dotenv

load_dotenv()

WC_API_URL = os.getenv("WC_API_URL")
WC_CONSUMER_KEY = os.getenv("WC_CONSUMER_KEY")
WC_CONSUMER_SECRET = os.getenv("WC_CONSUMER_SECRET")

def update_price_by_sku(sku, new_price):
    try:
        res = requests.get(f"{WC_API_URL}/products", params={"sku": sku},
                           auth=(WC_CONSUMER_KEY, WC_CONSUMER_SECRET))
        if res.status_code != 200 or not res.json():
            print(f"❌ SKU {sku} không tìm thấy hoặc lỗi API")
            return False
        product_id = res.json()[0]["id"]
        r = requests.put(f"{WC_API_URL}/products/{product_id}",
                         json={"regular_price": str(new_price), "price": str(new_price)},
                         auth=(WC_CONSUMER_KEY, WC_CONSUMER_SECRET))
        if r.status_code in (200, 201):
            print(f"✅ Cập nhật SKU {sku}: {new_price}đ")
            return True
        print(f"❌ Lỗi cập nhật SKU {sku}: {r.text}")
        return False
    except Exception as e:
        print(f"⚠️ Exception SKU {sku}: {e}")
        return False
