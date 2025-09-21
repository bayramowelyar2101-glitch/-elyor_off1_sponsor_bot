# elyor_bot1 — Telegram Sponsor Bot (ready to deploy)

Bu repo, **Render / Railway / Heroku** gibi servislerde deploy etmeye hazır şekilde hazırlanmıştır.
Bot kullanıcı arayüzü **Türkmençe**, admin yorumları / talimatlar Türkçe olarak dosyada bulunmaktadır.

## İçerik
- `elyor_bot1.py` — ana bot kodu (polling) + küçük HTTP ping sunucusu (uptime için)
- `requirements.txt` — Python paketleri
- `.env.example` — local geliştirme için örnek environment variables
- `Procfile` — bazı platformlar için start komutu
- `.gitignore` — hassas dosyaları hariç tutar

## Adım adım — GitHub'a yükleme
1. Yeni bir repository oluştur (public ya da private senin tercihin).
2. Lokal klasör oluştur ve dosyaları içine koy:
   ```bash
   mkdir elyor_bot_repo
   cd elyor_bot_repo
   # buraya elyor_bot1.py, requirements.txt, Procfile, .gitignore, .env.example, README.md ekle
   git init
   git add .
   git commit -m "Initial commit - elyor_bot1"
   git branch -M main
   git remote add origin https://github.com/USERNAME/REPO.git
   git push -u origin main
   ```

## Render'de deploy (özet)
1. Render hesabına GitHub erişimi ver ve repo'yu seç.
2. Yeni **Web Service** oluştur (öncelikle *Web Service*, çünkü uptime monitor HTTP ping atacak).
3. Build Command: `pip install -r requirements.txt`
4. Start Command: `python elyor_bot1.py`
5. Environment Variables bölümüne ekle:
   - `BOT_TOKEN` = (BotFather token)
   - `ADMIN_IDS` = (örnek: 6978728781)
   - `PORT` = 8080 (Render otomatik sağlar ama koymak zarar vermez)
6. Deploy başlat. Loglarda `Starting bot...` ve `Ping server started on port 8080` gibi mesajları görmelisiniz.

> Not: Daha önce yaşadığınız dependency conflict için `requirements.txt` buradaki sürümler uyumludur (`python-telegram-bot==20.3` ile `httpx==0.24.1` uyumlu olmalıdır). Eğer hâlâ çözülmezse, deploy log'unu buraya kopyalayın, beraber çözelim.

## Railway (özet)
Railway de benzer şekilde repo bağlanır. Start command `python elyor_bot1.py` ve ENV değişkenleri yukarıdaki gibi eklenir.

## UptimeRobot (300s interval)
1. UptimeRobot hesabı oluştur veya giriş yap.
2. "Add New Monitor" -> Monitor Type: **HTTP(s)**
3. Friendly name: `elyor-bot-ping`
4. URL (ping target): `https://<your-app>.onrender.com/` (Render tarafından verilen URL)
5. Interval: **5 minutes (300 seconds)** — UptimeRobot ücretsiz plan limitleri dahilinde destekliyorsa ayarla (bazı ücretsiz planlarda minimum 5 dakika veya 1 dakika olabilir).
6. Save — bundan sonra UptimeRobot her 300s'de bir `/` endpoint'ine istek atacak ve Render uygulamanın uyanık kalmasına yardımcı olur.

## Güvenlik
- **Asla** BOT token'ını repo'ya koyma. Render/Railway/Github Secrets/Evironment kısmına ekle.
- `.env` dosyasını asla commit etme — `.gitignore` bunu engeller.

## Local test (opsiyonel)
1. Kopyala `.env.example` -> `.env`, içine `BOT_TOKEN` ve `ADMIN_IDS` koy.
2. `python -m venv venv && source venv/bin/activate` (Linux/Mac) veya `venv\Scripts\activate` (Windows)
3. `pip install -r requirements.txt`
4. `python elyor_bot1.py` — ardından Telegram'dan `/start` ile test et.

---
Hazır dosyaları indirmek ya da ben doğrudan repo'ya push etmek istersen: hangi yolu tercih ediyorsun? Ben dosyaları buraya hazır koydum; istersen ben ZIP haline getirip paylaşırım veya tek tek dosyaları indirip push etmen için komutları veririm.
