# Python 3.11 tabanlı resmi imajı kullan
FROM python:3.11-slim

# Çalışma dizinini ayarla
WORKDIR /app

# Gerekli bağımlılıkları yükle
RUN pip install --no-cache-dir python-telegram-bot==20.6 httpx==0.25.2

# Kod dosyanı konteynıra kopyala
COPY elyor_bot1.py /app/

# Ortam değişkeni (Render için gerekli olabilir)
ENV PYTHONUNBUFFERED=1

# Botu çalıştır
CMD ["python", "elyor_bot1.py"]
