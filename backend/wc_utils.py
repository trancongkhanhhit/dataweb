# backend/wc_utils.py
import os
import requests
from dotenv import load_dotenv

load_dotenv()

WC_API_URL = os.getenv("WC_API_URL")
WC_CONSUMER_KEY = os.getenv("WC_CONSUMER_KEY")
WC_CONSUMER_SECRET = os.getenv("WC_CONSUMER_SECRET")

def update_price_by_sku(sku, new_price):
    """Cập nhật giá WooCommerce theo SKU"""
    try:
        if not all([WC_API_URL, WC_CONSUMER_KEY, WC_CONSUMER_SECRET]):
            print("❌ Thiếu cấu hình WooCommerce API trong .env")
            return False

        # 1️⃣ Tìm sản phẩm theo SKU
        res = requests.get(
            f"{WC_API_URL}/products",
            params={"sku": sku},
            auth=(WC_CONSUMER_KEY, WC_CONSUMER_SECRET)
        )

        if res.status_code != 200:
            print(f"❌ Lỗi tìm SKU {sku}: {res.status_code}")
            return False

        data = res.json()
        if not data:
            print(f"⚠️ Không tìm thấy sản phẩm SKU {sku}")
            return False

        product_id = data[0]["id"]

        # 2️⃣ Gửi lệnh cập nhật giá
        payload = {
            "regular_price": str(int(new_price)),
            "price": str(int(new_price))
        }

        update_res = requests.put(
            f"{WC_API_URL}/products/{product_id}",
            auth=(WC_CONSUMER_KEY, WC_CONSUMER_SECRET),
            json=payload
        )

        if update_res.status_code in (200, 201):
            print(f"[✅] SKU {sku} cập nhật thành công → {new_price}đ")
            return True
        else:
            print(f"❌ Lỗi cập nhật SKU {sku}: {update_res.status_code} {update_res.text}")
            return False

    except Exception as e:
        print(f"⚠️ Exception khi cập nhật SKU {sku}: {e}")
        return False
#