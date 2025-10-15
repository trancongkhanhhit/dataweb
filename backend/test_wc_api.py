import os
import requests
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv

load_dotenv()

url = os.getenv("WC_API_URL")
auth = HTTPBasicAuth(os.getenv("WC_CONSUMER_KEY"), os.getenv("WC_CONSUMER_SECRET"))

# ✅ Test lấy 1 sản phẩm
res = requests.get(f"{url}/products?per_page=1", auth=auth)
print("Status:", res.status_code)
data = res.json()
print("✅ Lấy sản phẩm mẫu:", data[0]["name"] if res.status_code == 200 else data)

# ✅ Test cập nhật giá theo SKU
sku = "1600A00F6U"  # Mã sản phẩm của bạn
r = requests.get(f"{url}/products?sku={sku}", auth=auth)
if r.status_code == 200 and r.json():
    product = r.json()[0]
    pid = product["id"]
    new_price = str(int(product["regular_price"] or 0) + 5000)
    update = requests.put(f"{url}/products/{pid}", json={"regular_price": new_price}, auth=auth)
    print(f"🟢 Cập nhật {sku}: {update.status_code}")
    print(update.json().get("regular_price", update.text))
else:
    print("❌ Không tìm thấy sản phẩm có SKU:", sku)
