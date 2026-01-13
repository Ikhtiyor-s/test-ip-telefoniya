"""
Autodialer Pro - Konfiguratsiya
Professional autodialer tizimi sozlamalari
"""

import os
from pathlib import Path

# =============================================================================
# ASOSIY SOZLAMALAR
# =============================================================================

BASE_DIR = Path(__file__).resolve().parent.parent
AUDIO_DIR = BASE_DIR / "audio"
LOGS_DIR = BASE_DIR / "logs"

# =============================================================================
# AMOCRM SOZLAMALARI
# =============================================================================

AMOCRM_CONFIG = {
    "subdomain": "welltech",  # welltech.amocrm.ru
    "access_token": os.getenv("AMOCRM_ACCESS_TOKEN", "YOUR_ACCESS_TOKEN"),
    "pipeline_id": None,  # Avtomatik aniqlanadi
    "status_checking": "TEKSHIRILMOQDA",  # Kuzatiladigan status
    "polling_interval": 3,  # Sekundda bir marta tekshirish
}

# =============================================================================
# SARKOR SIP SOZLAMALARI
# =============================================================================

SIP_CONFIG = {
    "server": "well-tech.sip.uz",
    "port": 5060,
    "username": "admin",
    "password": os.getenv("SIP_PASSWORD", "gHMu4nYzst"),
    "caller_id": "+998783337984",
    "transport": "udp",
}

# =============================================================================
# ASTERISK AMI SOZLAMALARI
# =============================================================================

ASTERISK_CONFIG = {
    "host": "127.0.0.1",
    "port": 5038,
    "username": "autodialer",
    "password": os.getenv("AMI_PASSWORD", "autodialer123"),
    "context": "autodialer",
}

# =============================================================================
# TELEGRAM BOT SOZLAMALARI
# =============================================================================

TELEGRAM_CONFIG = {
    "bot_token": os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN"),
    "chat_id": os.getenv("TELEGRAM_CHAT_ID", "YOUR_CHAT_ID"),
    "alert_timeout": 180,  # 3 daqiqa - xabar yuborish vaqti
}

# =============================================================================
# QO'NG'IROQ SOZLAMALARI
# =============================================================================

CALL_CONFIG = {
    "wait_before_call": 90,  # 1.5 daqiqa kutish (sekundda)
    "max_attempts": 3,  # Maksimal urinishlar soni
    "retry_interval": 60,  # Qayta qo'ng'iroq orasidagi vaqt (sekundda)
    "call_timeout": 30,  # Qo'ng'iroq kutish vaqti (sekundda)
    "answer_timeout": 20,  # Javob kutish vaqti
}

# =============================================================================
# SOTUVCHILAR RO'YXATI
# =============================================================================

SELLERS = {
    "default": {
        "name": "Asosiy sotuvchi",
        "phone": "+998948679300",
        "telegram_id": None,
    },
    # Qo'shimcha sotuvchilar qo'shish mumkin
    # "seller_2": {
    #     "name": "Ikkinchi sotuvchi",
    #     "phone": "+998901234567",
    #     "telegram_id": "123456789",
    # },
}

# =============================================================================
# TTS (TEXT-TO-SPEECH) SOZLAMALARI
# =============================================================================

TTS_CONFIG = {
    "provider": "google",  # google, silero, edge
    "language": "uz",  # O'zbek tili
    "voice": "uz-UZ-Standard-A",
    "audio_format": "wav",
    "sample_rate": 8000,  # Asterisk uchun 8kHz
}

# =============================================================================
# XABAR SHABLONLARI
# =============================================================================

MESSAGES = {
    "call_template": "Assalomu alaykum! Sizda {count} ta yangi buyurtma bor. Iltimos, tekshiring.",
    "telegram_template": """
🔔 *Yangi buyurtmalar!*

📦 Buyurtmalar soni: *{count}* ta
⏰ Vaqt: {time}
📋 Status: TEKSHIRILMOQDA

Iltimos, tezroq tekshiring!
    """,
    "telegram_resolved": """
✅ *Buyurtmalar tekshirildi!*

📦 Tekshirilgan: *{count}* ta
⏰ Vaqt: {time}
    """,
}

# =============================================================================
# LOGGING SOZLAMALARI
# =============================================================================

LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        },
        "detailed": {
            "format": "%(asctime)s [%(levelname)s] %(name)s:%(lineno)d - %(message)s"
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "level": "INFO",
            "formatter": "standard",
            "stream": "ext://sys.stdout",
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "level": "DEBUG",
            "formatter": "detailed",
            "filename": str(LOGS_DIR / "autodialer.log"),
            "maxBytes": 10485760,  # 10MB
            "backupCount": 5,
        },
    },
    "loggers": {
        "": {
            "level": "DEBUG",
            "handlers": ["console", "file"],
        },
    },
}
