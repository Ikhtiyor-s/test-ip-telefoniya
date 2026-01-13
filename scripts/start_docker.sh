#!/bin/bash
# =============================================================================
# AUTODIALER PRO - DOCKER BILAN ISHGA TUSHIRISH
# =============================================================================

set -e

echo "=============================================="
echo "  AUTODIALER PRO - DOCKER"
echo "=============================================="

# .env tekshirish
if [ ! -f .env ]; then
    echo "[ERROR] .env fayl topilmadi!"
    exit 1
fi

# Docker Compose
echo "[INFO] Docker konteynerlarni ishga tushirish..."
docker-compose up -d

echo ""
echo "[INFO] Konteynerlar holati:"
docker-compose ps

echo ""
echo "[INFO] Loglarni ko'rish:"
echo "docker-compose logs -f autodialer"
