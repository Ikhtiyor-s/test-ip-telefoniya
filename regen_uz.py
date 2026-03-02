"""Faqat uz tilini qayta yaratish - MadinaNeural ovozi bilan"""
import asyncio, hashlib, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))
from services.tts_service import TTSService, ORDER_MESSAGES, PLANNED_MESSAGES

AUDIO_DIR = Path(__file__).parent / "src" / "audio"
CACHE_DIR = AUDIO_DIR / "cache"

async def main():
    # Eski uz fayllarini o'chirish
    deleted = 0
    for i in range(1, 51):
        for msg_dict in [ORDER_MESSAGES, PLANNED_MESSAGES]:
            text = msg_dict["uz"][0] if i == 1 else msg_dict["uz"][1].format(count=i)
            key = f"uz_{text}"
            h = hashlib.md5(key.encode()).hexdigest()
            f = CACHE_DIR / f"{h}.wav"
            if f.exists():
                f.unlink()
                deleted += 1
    print(f"Eski uz fayllar o'chirildi: {deleted} ta")

    # MadinaNeural bilan qayta yaratish
    tts = TTSService(audio_dir=AUDIO_DIR, provider="edge")
    total = 0
    for i in range(1, 51):
        path = await tts.generate_order_message(i, lang="uz")
        if path:
            total += 1
            print(f"  OK order  [uz] {i:>2} ta -> {path.name}")
        path = await tts.generate_planned_message(i, lang="uz")
        if path:
            total += 1
            print(f"  OK planned[uz] {i:>2} ta -> {path.name}")

    print(f"\nJami yaratildi: {total} ta fayl (MadinaNeural)")

asyncio.run(main())
