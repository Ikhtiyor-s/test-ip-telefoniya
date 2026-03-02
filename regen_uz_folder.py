"""Faqat uz/ papkasini qayta yaratish"""
import hashlib, shutil
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent / "src"))
from services.tts_service import ORDER_MESSAGES, PLANNED_MESSAGES

CACHE_DIR = Path(__file__).parent / "src" / "audio" / "cache"
UZ_DIR = CACHE_DIR / "uz"
UZ_DIR.mkdir(exist_ok=True)

ok = 0
for i in range(1, 51):
    for msg_type, msg_dict in [("order", ORDER_MESSAGES), ("planned", PLANNED_MESSAGES)]:
        text = msg_dict["uz"][0] if i == 1 else msg_dict["uz"][1].format(count=i)
        h = hashlib.md5(f"uz_{text}".encode()).hexdigest()
        src = CACHE_DIR / f"{h}.wav"
        dst = UZ_DIR / f"{msg_type}_{i:02d}.wav"
        if src.exists():
            shutil.copy2(src, dst)
            ok += 1
            print(f"  OK {msg_type}_{i:02d}.wav")
        else:
            print(f"  TOPILMADI: {msg_type}_{i:02d}")

print(f"\nJami: {ok} ta fayl -> cache/uz/")
