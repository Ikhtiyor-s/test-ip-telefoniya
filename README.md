# Autodialer Pro

Professional autodialer tizimi - amoCRM buyurtmalarini kuzatish va sotuvchilarga avtomatik qo'ng'iroq qilish.

## Jarayon

```
Yangi buyurtma (TEKSHIRILMOQDA)
        ↓
   1.5 daqiqa kutish
        ↓
Sotuvchiga qo'ng'iroq:
  "Sizda N ta yangi buyurtma bor. Iltimos, tekshiring."
        ↓
Javob bo'lmasa → yana qo'ng'iroq (max 3 marta)
        ↓
   3 daqiqada Telegram xabar
        ↓
Status o'zgarsa → Telegram xabar o'chiriladi
```

## Xususiyatlar

- ✅ **Jamlangan qo'ng'iroq** - Har bir buyurtma uchun alohida emas, barcha buyurtmalar uchun 1 ta qo'ng'iroq
- ✅ **Real-time kuzatish** - amoCRM har 3 sekundda tekshiriladi
- ✅ **TTS** - O'zbek tilida ovozli xabar ("Sizda 5 ta yangi buyurtma bor")
- ✅ **Retry logic** - Javob bo'lmasa 3 marta qayta qo'ng'iroq
- ✅ **Telegram** - 3 daqiqada xabar, status o'zgarsa o'chiriladi
- ✅ **Docker** - Oson deploy

## Talablar

- Python 3.11+
- Asterisk PBX
- Sarkor SIP (SIP chiquvchi ruxsati bilan)
- amoCRM
- Telegram Bot

## O'rnatish

### 1. Klonlash

```bash
git clone <repo>
cd autodialer-pro
```

### 2. Environment sozlash

```bash
cp .env.example .env
nano .env  # Qiymatlarni to'ldiring
```

### 3. O'rnatish

```bash
chmod +x scripts/*.sh
./scripts/install.sh
```

### 4. Ishga tushirish

**Oddiy:**
```bash
./scripts/start.sh
```

**Docker:**
```bash
./scripts/start_docker.sh
```

## Konfiguratsiya

`.env` faylida:

```env
# AMOCRM
AMOCRM_SUBDOMAIN=welltech
AMOCRM_TOKEN=your_token

# TELEGRAM
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id

# SOTUVCHI
SELLER_PHONE=+998948679300

# VAQTLAR
WAIT_BEFORE_CALL=90      # 1.5 daqiqa
TELEGRAM_ALERT_TIME=180  # 3 daqiqa
MAX_CALL_ATTEMPTS=3
```

## Loyiha Strukturasi

```
autodialer-pro/
├── src/
│   ├── services/
│   │   ├── amocrm_service.py    # amoCRM integratsiya
│   │   ├── asterisk_service.py  # Asterisk AMI
│   │   ├── telegram_service.py  # Telegram bot
│   │   └── tts_service.py       # Text-to-Speech
│   ├── models/
│   │   └── order.py             # Ma'lumot modellari
│   └── autodialer.py            # Asosiy servis
├── config/
│   ├── asterisk/
│   │   ├── pjsip.conf           # SIP konfiguratsiya
│   │   ├── extensions.conf      # Dialplan
│   │   └── manager.conf         # AMI
│   └── settings.py              # Sozlamalar
├── audio/                       # TTS audio fayllar
├── logs/                        # Log fayllar
├── scripts/
│   ├── install.sh               # O'rnatish
│   ├── start.sh                 # Ishga tushirish
│   └── start_docker.sh          # Docker bilan
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── .env.example
```

## Loglar

```bash
# Real-time
tail -f logs/autodialer.log

# Docker
docker-compose logs -f autodialer
```

## Muammolarni bartaraf qilish

### SIP registratsiya muvaffaqiyatsiz
```bash
# WSL da
sudo asterisk -rvvv
pjsip show registrations
```

### amoCRM 401 xatosi
- Token muddati tugagan
- Yangi token oling va `.env` ga qo'ying

### Qo'ng'iroq ishlamayapti
- Sarkordan SIP chiquvchi ruxsati olinganligini tekshiring
- `403 Calls not allowed` - Sarkor supportga murojaat qiling

## Litsenziya

MIT
