FROM python:3.12-slim

# ติดตั้ง LibreOffice + Thai fonts + FreeSerif
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libreoffice \
        fonts-freefont-ttf \
        fonts-thai-tlwg \
        fonts-noto-cjk \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8080
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--timeout", "120", "app:app"]
