#!/bin/bash
# =============================================================================
# AUTODIALER PRO - ISHGA TUSHIRISH SKRIPTI
# =============================================================================

set -e

echo "=============================================="
echo "  AUTODIALER PRO - ISHGA TUSHIRISH"
echo "=============================================="

# .env tekshirish
if [ ! -f .env ]; then
    echo "[ERROR] .env fayl topilmadi!"
    echo "cp .env.example .env va to'ldiring"
    exit 1
fi

# Environment yuklash
source .env

# Asterisk tekshirish
echo "[INFO] Asterisk holatini tekshirish..."
if command -v asterisk &> /dev/null; then
    if sudo asterisk -rx "core show version" &> /dev/null; then
        echo "[OK] Asterisk ishlayapti"
    else
        echo "[INFO] Asterisk ishga tushirilmoqda..."
        sudo service asterisk start
        sleep 3
    fi

    # SIP registratsiya
    echo "[INFO] SIP registratsiyani tekshirish..."
    REG_STATUS=$(sudo asterisk -rx "pjsip show registrations" | grep -c "Registered" || true)
    if [ "$REG_STATUS" -gt 0 ]; then
        echo "[OK] SIP Registered"
    else
        echo "[WARN] SIP registratsiya kutilmoqda..."
    fi
else
    echo "[INFO] Asterisk Docker orqali ishlatiladi"
fi

# Virtual environment
if [ -d "venv" ]; then
    echo "[INFO] Virtual environment aktivlash..."
    source venv/bin/activate
fi

# Audio papka
mkdir -p audio logs

# Autodialer ishga tushirish
echo ""
echo "=============================================="
echo "  AUTODIALER ISHGA TUSHMOQDA..."
echo "=============================================="
echo ""

cd src
python autodialer.py
