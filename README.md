# AutoDialer Pro - amoCRM + Asterisk + Telegram

Yangi buyurtmalar uchun avtomatik qo'ng'iroq qiluvchi tizim.

## Tizim haqida

AutoDialer Pro quyidagi vazifalarni bajaradi:
1. amoCRM dan yangi buyurtmalarni kuzatadi
2. Yangi buyurtma kelganda 90 soniya kutadi
3. Sotuvchiga avtomatik qo'ng'iroq qiladi (ovozli xabar bilan)
4. Agar javob bermasa, qayta qo'ng'iroq qiladi
5. 3 daqiqadan keyin Telegram guruhga xabar yuboradi
6. Buyurtma holati o'zgarganda Telegram xabarini o'chiradi

---

## Tizim talablari

### Dasturiy ta'minot
- Windows 10/11
- WSL2 (Windows Subsystem for Linux)
- Ubuntu 22.04 (WSL ichida)
- Python 3.10+
- Asterisk 18+ (WSL ichida)

### Hisoblar
- amoCRM hisobi (admin huquqlari bilan)
- Telegram hisobi (bot yaratish uchun)
- Sarkor Telecom SIP hisobi

---

## 1-BOSQICH: Kerakli ma'lumotlarni olish

### 1.1 amoCRM API Token olish

1. amoCRM ga kiring: `https://SIZNING_SUBDOMAIN.amocrm.ru`

2. **Sozlamalar** > **Integratsiyalar** bo'limiga o'ting

3. **"O'z integratsiyangizni yarating"** tugmasini bosing

4. Integratsiya ma'lumotlarini kiriting:
   - Nomi: `AutoDialer`
   - Tavsif: `Avtomatik qo'ng'iroq tizimi`

5. **Ruxsatlar**ni tanlang:
   - [x] crm
   - [x] notifications

6. **Saqlash** tugmasini bosing

7. **Tokenlar** bo'limidan quyidagilarni nusxalang:
   - `Access Token` - bu sizning `AMOCRM_TOKEN`
   - Subdomain - bu sizning `AMOCRM_SUBDOMAIN` (masalan: `welltech`)

**Muhim:** Token 24 soatda eskiradi. Refresh token yordamida yangilanadi.

---

### 1.2 Telegram Bot yaratish

#### Bot yaratish:

1. Telegram da `@BotFather` ga yozing

2. `/newbot` buyrug'ini yuboring

3. Bot nomini kiriting: `AutoDialer Bot`

4. Bot username kiriting: `autodialer_welltech_bot` (unique bo'lishi kerak)

5. BotFather sizga **token** beradi:
   ```
   7683981246:AAFCH2u26L1ohHEOddFY8I26o4k_uXptb08
   ```
   Bu sizning `TELEGRAM_BOT_TOKEN`

#### Guruh Chat ID olish:

1. Telegram da yangi guruh yarating yoki mavjud guruhni oching

2. Botni guruhga qo'shing (guruh sozlamalaridan)

3. Guruhga biror xabar yozing

4. Brauzerda quyidagi URL ni oching:
   ```
   https://api.telegram.org/bot<TOKEN>/getUpdates
   ```
   `<TOKEN>` o'rniga bot tokeningizni qo'ying

5. JSON javobdan `chat.id` ni toping:
   ```json
   "chat": {
     "id": -5219407458,
     "title": "WellTech Orders"
   }
   ```
   `-5219407458` - bu sizning `TELEGRAM_CHAT_ID`

**Eslatma:** Guruh ID har doim `-` belgisi bilan boshlanadi.

---

### 1.3 Sarkor Telecom SIP ma'lumotlari

Sarkor Telecom bilan shartnoma tuzganingizda quyidagi ma'lumotlarni olasiz:

| Parametr | Qiymat (misol) |
|----------|----------------|
| SIP server | `sip.sarkor.uz` |
| Port | `5060` |
| Username | `998783337984` |
| Password | `SizningParol123` |
| CallerID | `+998783337984` |

Bu ma'lumotlarni Asterisk PJSIP konfiguratsiyasida ishlatiladi.

---

## 2-BOSQICH: WSL va Asterisk o'rnatish

### 2.1 WSL2 o'rnatish

PowerShell da (Administrator):
```powershell
wsl --install -d Ubuntu-22.04
```

Qayta yuklangandan keyin Ubuntu username va parol o'rnating.

### 2.2 Asterisk o'rnatish

WSL Ubuntu da:
```bash
# Yangilash
sudo apt update && sudo apt upgrade -y

# Asterisk o'rnatish
sudo apt install -y asterisk asterisk-core-sounds-en

# Asterisk ni ishga tushirish
sudo systemctl start asterisk
sudo systemctl enable asterisk
```

### 2.3 Asterisk AMI sozlash

`/etc/asterisk/manager.conf` faylini tahrirlang:
```bash
sudo nano /etc/asterisk/manager.conf
```

Quyidagilarni qo'shing:
```ini
[general]
enabled = yes
port = 5038
bindaddr = 0.0.0.0

[autodialer]
secret = autodialer123
read = all
write = all
deny = 0.0.0.0/0.0.0.0
permit = 0.0.0.0/0.0.0.0
```

### 2.4 Asterisk PJSIP sozlash

`/etc/asterisk/pjsip.conf` faylini tahrirlang:
```bash
sudo nano /etc/asterisk/pjsip.conf
```

Sarkor Telecom uchun quyidagilarni qo'shing:
```ini
; === SARKOR TELECOM TRUNK ===

[sarkor-transport]
type=transport
protocol=udp
bind=0.0.0.0

[sarkor-registration]
type=registration
transport=sarkor-transport
outbound_auth=sarkor-auth
server_uri=sip:sip.sarkor.uz
client_uri=sip:998783337984@sip.sarkor.uz
retry_interval=60

[sarkor-auth]
type=auth
auth_type=userpass
username=998783337984
password=SizningParol123

[sarkor-aor]
type=aor
contact=sip:sip.sarkor.uz

[sarkor-endpoint]
type=endpoint
transport=sarkor-transport
context=from-sarkor
disallow=all
allow=alaw
allow=ulaw
outbound_auth=sarkor-auth
aors=sarkor-aor
from_user=998783337984
from_domain=sip.sarkor.uz

[sarkor-identify]
type=identify
endpoint=sarkor-endpoint
match=sip.sarkor.uz
```

### 2.5 Asterisk Dialplan sozlash

`/etc/asterisk/extensions.conf` faylini tahrirlang:
```bash
sudo nano /etc/asterisk/extensions.conf
```

Quyidagilarni qo'shing:
```ini
[autodialer-dynamic]
exten => _X.,1,NoOp(AutoDialer qo'ng'iroq: ${EXTEN})
 same => n,Answer()
 same => n,Wait(1)
 same => n,Playback(${AUDIO_FILE})
 same => n,Wait(1)
 same => n,Hangup()

[from-sarkor]
exten => _X.,1,NoOp(Kiruvchi qo'ng'iroq: ${CALLERID(num)})
 same => n,Hangup()
```

### 2.6 Asterisk qayta yuklash

```bash
sudo asterisk -rx "core reload"
sudo asterisk -rx "pjsip reload"
```

### 2.7 WSL IP manzilini olish

```bash
ip addr show eth0 | grep inet
```
Natija: `172.29.124.85` (bu sizning `AMI_HOST`)

---

## 3-BOSQICH: Loyihani sozlash

### 3.1 Loyihani yuklab olish

```bash
# Windows CMD yoki PowerShell da
cd C:\Users\YourUsername
git clone https://github.com/Ikhtiyor-s/ip-telefon.git autodialer-pro
cd autodialer-pro
```

### 3.2 Python muhitini yaratish

```bash
# Virtual environment yaratish
python -m venv venv

# Faollashtirish (Windows)
venv\Scripts\activate

# Kutubxonalarni o'rnatish
pip install -r requirements.txt
```

### 3.3 .env faylini sozlash

`autodialer-pro` papkasida `.env` fayl yarating:

```bash
# .env fayl namunasi

# AMOCRM
AMOCRM_SUBDOMAIN=welltech
AMOCRM_TOKEN=eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiIsImp0aSI6IjkwMTU2MjdhY2U4MjUzYTMzZjIwZGY2MjBjYmQ4NTUxNWM4YjM3NTM4NDZmODgyZDZkNTUxNzE1OTY4NTJjM2E3OWMxYjUwYTg3YmJkZGViIn0...

# TELEGRAM
TELEGRAM_BOT_TOKEN=7683981246:AAFCH2u26L1ohHEOddFY8I26o4k_uXptb08
TELEGRAM_CHAT_ID=-5219407458

# ASTERISK AMI (WSL IP manzili)
AMI_HOST=172.29.124.85
AMI_PORT=5038
AMI_USERNAME=autodialer
AMI_PASSWORD=autodialer123

# SOTUVCHI TELEFON RAQAMI
SELLER_PHONE=+998901234567

# VAQTLAR (sekundda)
WAIT_BEFORE_CALL=90
TELEGRAM_ALERT_TIME=180
MAX_CALL_ATTEMPTS=2
RETRY_INTERVAL=0
```

### Parametrlar tushuntirmasi:

| Parametr | Tavsif | Namuna |
|----------|--------|--------|
| `AMOCRM_SUBDOMAIN` | amoCRM subdomain | `welltech` |
| `AMOCRM_TOKEN` | amoCRM API token | JWT token |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token | `768398...:AAF...` |
| `TELEGRAM_CHAT_ID` | Telegram guruh ID | `-5219407458` |
| `AMI_HOST` | WSL IP manzili | `172.29.124.85` |
| `AMI_PORT` | Asterisk AMI port | `5038` |
| `AMI_USERNAME` | AMI username | `autodialer` |
| `AMI_PASSWORD` | AMI parol | `autodialer123` |
| `SELLER_PHONE` | Sotuvchi telefoni | `+998901234567` |
| `WAIT_BEFORE_CALL` | Qo'ng'iroqdan oldin kutish | `90` (soniya) |
| `TELEGRAM_ALERT_TIME` | Telegram xabar vaqti | `180` (soniya) |
| `MAX_CALL_ATTEMPTS` | Maksimum qo'ng'iroq urinishlari | `2` |
| `RETRY_INTERVAL` | Qayta qo'ng'iroq oralig'i | `0` (soniya) |

---

## 4-BOSQICH: Audio fayllarni tayyorlash

### 4.1 TTS audio fayllar

Tizim avtomatik ravishda Edge TTS orqali o'zbek tilida audio fayllar yaratadi.

**Qo'ng'iroqdagi xabar:**
> "Assalomu alaykum, men nonbor ovozli bot xizmatiman, sizda N ta buyurtma bor, iltimos, buyurtmalaringizni tekshiring."

### 4.2 WSL ga audio nusxalash

**Avtomatik:** Tizim ishga tushganda audio fayllar avtomatik WSL ga ko'chiriladi.

**Qo'lda** (agar kerak bo'lsa):
```bash
# WSL da papka yaratish va fayllarni nusxalash
wsl mkdir -p /tmp/autodialer
wsl cp /mnt/c/Users/Asus/autodialer-pro/audio/cache/*.wav /tmp/autodialer/
```

---

## 5-BOSQICH: Tizimni ishga tushirish

### 5.1 Asterisk tekshirish

WSL da:
```bash
# Asterisk ishlayaptimi?
sudo systemctl status asterisk

# SIP registratsiya
sudo asterisk -rx "pjsip show registrations"

# AMI ishlayaptimi?
sudo asterisk -rx "manager show connected"
```

### 5.2 AutoDialer ishga tushirish

Windows da:
```bash
cd C:\Users\Asus\autodialer-pro

# Virtual environment faollashtirish
venv\Scripts\activate

# Ishga tushirish
python src/autodialer.py
```

### 5.3 Muvaffaqiyatli ishga tushish

Quyidagi xabarlarni ko'rishingiz kerak:
```
============================================================
AUTODIALER PRO ISHGA TUSHMOQDA
============================================================
TTS xabarlarini tayyorlash...
Asterisk AMI ga ulanish...
AMI ulanish muvaffaqiyatli
amoCRM polling boshlash...
============================================================
AUTODIALER PRO ISHLAYAPTI
============================================================
```

---

## 6-BOSQICH: amoCRM sozlash

### 6.1 Pipeline va Status

AutoDialer quyidagi pipeline va statusni kuzatadi:
- **Pipeline nomi:** `nonbor-order-manage`
- **Status nomi:** `Tekshirilmoqda`

Agar sizning pipeline va status nomlari boshqacha bo'lsa, `src/services/amocrm_service.py` faylida o'zgartiring:

```python
PIPELINE_NAME = "nonbor-order-manage"  # Sizning pipeline nomingiz
STATUS_NAME = "Tekshirilmoqda"         # Sizning status nomingiz
```

### 6.2 Lead kontaktlari

Har bir lead da quyidagi ma'lumotlar bo'lishi kerak:
- **Buyurtma raqami** - lead nomi yoki custom field da
- **Telefon raqami** - kontakt telefoni (ixtiyoriy, chunki asosiy qo'ng'iroq SELLER_PHONE ga)

---

## Xatoliklarni tuzatish

### AMI ulanish xatosi

**Xato:** `AMI ulanish xatosi: Connection refused`

**Yechim:**
1. WSL IP manzilini tekshiring: `wsl ip addr show eth0`
2. Asterisk ishlayaptimi: `wsl sudo systemctl status asterisk`
3. `manager.conf` da `bindaddr = 0.0.0.0` ekanini tekshiring

### SIP registratsiya muvaffaqiyatsiz

**Xato:** `SIP registratsiya: MUVAFFAQIYATSIZ`

**Yechim:**
1. Sarkor ma'lumotlarini tekshiring (`pjsip.conf`)
2. Internet ulanishini tekshiring
3. Asterisk loglarni ko'ring: `wsl sudo tail -f /var/log/asterisk/messages`

### Audio eshitilmadi

**Xato:** Qo'ng'iroq bo'ldi lekin ovoz yo'q

**Yechim:**
1. Audio fayllar WSL da borligini tekshiring:
   ```bash
   wsl ls -la /tmp/autodialer/
   ```
2. Fayl formati to'g'ri ekanini tekshiring (WAV, 8kHz, mono)

### amoCRM token eskirgan

**Xato:** `401 Unauthorized`

**Yechim:**
1. amoCRM dan yangi token oling
2. `.env` faylda `AMOCRM_TOKEN` ni yangilang

---

## Foydali buyruqlar

```bash
# WSL IP olish
wsl hostname -I

# Asterisk CLI
wsl sudo asterisk -rvvv

# SIP registratsiya
wsl sudo asterisk -rx "pjsip show registrations"

# Faol qo'ng'iroqlar
wsl sudo asterisk -rx "core show channels"

# AMI ulanishlar
wsl sudo asterisk -rx "manager show connected"

# Loglarni ko'rish
wsl sudo tail -f /var/log/asterisk/messages
```

---

## Loyiha tuzilishi

```
autodialer-pro/
├── .env                    # Konfiguratsiya
├── requirements.txt        # Python kutubxonalari
├── README.md              # Ushbu qo'llanma
├── dialplan.conf          # Asterisk dialplan namunasi
├── setup_dialplan.py      # Dialplan o'rnatish skripti
├── audio/
│   └── cache/             # TTS audio fayllar (1-20 buyurtma)
├── logs/                  # Log fayllar
└── src/
    ├── autodialer.py      # Asosiy business logic (ishga tushirish)
    └── services/
        ├── __init__.py          # Servislar eksporti
        ├── amocrm_service.py    # amoCRM API
        ├── asterisk_service.py  # Asterisk AMI
        ├── telegram_service.py  # Telegram Bot
        └── tts_service.py       # Text-to-Speech + WSL sync
```

---

## Xavfsizlik

**Eslatma:** `.env` faylida maxfiy ma'lumotlar bor:
- amoCRM API token
- Telegram bot token
- AMI parol

Loyihani boshqa muhitga o'rnatganda `.env` faylini to'g'ri sozlang.

---

## Qo'llab-quvvatlash

Savollar va muammolar uchun:
- GitHub Issues: https://github.com/Ikhtiyor-s/ip-telefon/issues

---

## Litsenziya

MIT License

---

**Muallif:** WellTech Team
**Versiya:** 1.0.0
**Sana:** 2026-01-14
