FROM python:3.12-slim

# ติดตั้ง FreeSerif font (รองรับภาษาไทย)
RUN apt-get update && apt-get install -y fonts-freefont-ttf && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# ใช้ gunicorn สำหรับ production
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--timeout", "120", "app:app"]
