"""
TTS fayllarni oldindan yaratish skripti
uz, ru, en, zh tillari uchun 1-50 ta buyurtma
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from services.tts_service import TTSService, PRIMARY_LANGS

AUDIO_DIR = Path(__file__).parent / "src" / "audio"
MAX_COUNT = 50


async def main():
    tts = TTSService(audio_dir=AUDIO_DIR, provider="edge")

    print(f"TTS generatsiya boshlanmoqda...")
    print(f"Tillar: {PRIMARY_LANGS}")
    print(f"Son: 1-{MAX_COUNT}")
    print(f"Xabar turlari: order + planned")
    print(f"Jami: {len(PRIMARY_LANGS) * MAX_COUNT * 2} ta fayl\n")

    total = 0
    for lang in PRIMARY_LANGS:
        for i in range(1, MAX_COUNT + 1):
            # Yangi buyurtma xabari
            path = await tts.generate_order_message(i, lang=lang)
            if path:
                total += 1
                print(f"  OK order  [{lang}] {i:>2} ta -> {path.name}")
            else:
                print(f"  !! order  [{lang}] {i:>2} ta - XATO!")

            # Reja eslatma xabari
            path = await tts.generate_planned_message(i, lang=lang)
            if path:
                total += 1
                print(f"  OK planned[{lang}] {i:>2} ta -> {path.name}")
            else:
                print(f"  !! planned[{lang}] {i:>2} ta - XATO!")

        print(f"\n[{lang}] tugadi\n")

    print(f"\nJami yaratildi: {total} ta fayl")
    print(f"Joylashuv: {AUDIO_DIR / 'cache'}")


if __name__ == "__main__":
    asyncio.run(main())
