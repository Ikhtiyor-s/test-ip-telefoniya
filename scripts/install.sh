#!/bin/bash
# =============================================================================
# AUTODIALER PRO - O'RNATISH SKRIPTI
# =============================================================================

set -e

echo "=============================================="
echo "  AUTODIALER PRO - O'RNATISH"
echo "=============================================="

# Rangli output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Funksiyalar
log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# 1. Tizim yangilash
log_info "Tizimni yangilash..."
sudo apt-get update

# 2. Kerakli paketlar
log_info "Kerakli paketlarni o'rnatish..."
sudo apt-get install -y \
    python3.11 \
    python3.11-venv \
    python3-pip \
    ffmpeg \
    docker.io \
    docker-compose

# 3. Virtual environment yaratish
log_info "Python virtual environment yaratish..."
python3.11 -m venv venv
source venv/bin/activate

# 4. Python kutubxonalar
log_info "Python kutubxonalarni o'rnatish..."
pip install --upgrade pip
pip install -r requirements.txt

# 5. Papkalar yaratish
log_info "Kerakli papkalarni yaratish..."
mkdir -p audio logs

# 6. .env fayl
if [ ! -f .env ]; then
    log_info ".env fayl yaratish..."
    cp .env.example .env
    log_warn ".env faylni to'ldiring!"
fi

# 7. Asterisk sozlash (WSL uchun)
log_info "Asterisk sozlash..."
if command -v asterisk &> /dev/null; then
    sudo cp config/asterisk/pjsip.conf /etc/asterisk/pjsip.conf
    sudo cp config/asterisk/extensions.conf /etc/asterisk/extensions.conf
    sudo cp config/asterisk/manager.conf /etc/asterisk/manager.conf
    sudo mkdir -p /var/lib/asterisk/sounds/autodialer
    sudo chown -R asterisk:asterisk /var/lib/asterisk/sounds/autodialer
    sudo systemctl restart asterisk
    log_info "Asterisk qayta ishga tushirildi"
else
    log_warn "Asterisk topilmadi. Docker ishlatiladi."
fi

echo ""
echo "=============================================="
echo -e "  ${GREEN}O'RNATISH TUGADI!${NC}"
echo "=============================================="
echo ""
echo "Keyingi qadamlar:"
echo "1. .env faylni to'ldiring"
echo "2. ./scripts/start.sh bilan ishga tushiring"
echo ""
