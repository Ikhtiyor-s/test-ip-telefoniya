"""
Audio fayllarni o'qiladigan nom bilan papkalarga ko'chirish
cache/ -> cache/uz/order_1.wav, cache/ru/order_1.wav ...
(Asosiy hash-based cache o'zgarmaydi)
"""
import hashlib
import shutil
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent / "src"))
from services.tts_service import ORDER_MESSAGES, PLANNED_MESSAGES, LANG_VOICES, PRIMARY_LANGS

AUDIO_DIR = Path(__file__).parent / "src" / "audio"
CACHE_DIR = AUDIO_DIR / "cache"
MAX_COUNT = 50


def get_hash(lang: str, text: str) -> str:
    key = f"{lang}_{text}"
    return hashlib.md5(key.encode()).hexdigest()


def main():
    print("O'qiladigan audio papkalar yaratilmoqda...")

    for lang in PRIMARY_LANGS:
        lang_dir = CACHE_DIR / lang
        lang_dir.mkdir(exist_ok=True)

        ok = 0
        for i in range(1, MAX_COUNT + 1):
            # Order xabari
            if i == 1:
                text = ORDER_MESSAGES[lang][0]
            else:
                text = ORDER_MESSAGES[lang][1].format(count=i)

            h = get_hash(lang, text)
            src = CACHE_DIR / f"{h}.wav"
            dst = lang_dir / f"order_{i:02d}.wav"
            if src.exists():
                shutil.copy2(src, dst)
                ok += 1
            else:
                print(f"  TOPILMADI: [{lang}] order {i}")

            # Planned xabari
            if i == 1:
                text = PLANNED_MESSAGES[lang][0]
            else:
                text = PLANNED_MESSAGES[lang][1].format(count=i)

            h = get_hash(lang, text)
            src = CACHE_DIR / f"{h}.wav"
            dst = lang_dir / f"planned_{i:02d}.wav"
            if src.exists():
                shutil.copy2(src, dst)
                ok += 1
            else:
                print(f"  TOPILMADI: [{lang}] planned {i}")

        print(f"  [{lang}] -> cache/{lang}/ papkasiga {ok} ta fayl ko'chirildi")

    print("\nNatija:")
    for lang in PRIMARY_LANGS:
        lang_dir = CACHE_DIR / lang
        count = len(list(lang_dir.glob("*.wav")))
        print(f"  cache/{lang}/ -> {count} ta fayl")
    print("\nEndi Windows Explorer da til papkalariga kirib eshitishingiz mumkin!")


if __name__ == "__main__":
    main()
