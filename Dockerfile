FROM python:3.11-slim

# Install Chrome
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    && wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ./backend .

# Thiết lập cổng mà ứng dụng sẽ chạy
EXPOSE 10000

# Lệnh để chạy ứng dụng khi container khởi động
# Gunicorn sẽ chạy từ bên trong thư mục /app (nơi chứa code của bạn)
CMD ["gunicorn", "dataweb.wsgi:application", "--bind", "0.0.0.0:10000"]