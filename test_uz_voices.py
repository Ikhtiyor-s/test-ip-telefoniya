"""
O'zbek tili uchun ovoz sinovi - turli variantlar taqqoslash
"""
import asyncio
from pathlib import Path
import edge_tts

TEST_DIR = Path("test_voices")
TEST_DIR.mkdir(exist_ok=True)

# Xabar variantlari
TESTS = [
    # (fayl_nomi, ovoz, matn)
    (
        "1_sardor_latin.wav",
        "uz-UZ-SardorNeural",
        "Assalomu alaykum! Bu Nonbor xizmati. Sizda 3 ta yangi buyurtma keldi, iltimos ilovani tekshiring."
    ),
    (
        "2_madina_latin.wav",
        "uz-UZ-MadinaNeural",
        "Assalomu alaykum! Bu Nonbor xizmati. Sizda 3 ta yangi buyurtma keldi, iltimos ilovani tekshiring."
    ),
    (
        "3_aigul_kirill.wav",
        "kk-KZ-AigulNeural",
        "Ассалому алайкум! Бу Нонбор хизмати. Сизда 3 та янги буюртма келди, илтимос иловани текширинг."
    ),
    (
        "4_daulet_kirill.wav",
        "kk-KZ-DauletNeural",
        "Ассалому алайкум! Бу Нонбор хизмати. Сизда 3 та янги буюртма келди, илтимос иловани текширинг."
    ),
    (
        "5_svetlana_kirill.wav",
        "ru-RU-SvetlanaNeural",
        "Ассалому алайкум! Бу Нонбор хизмати. Сизда 3 та янги буюртма келди, илтимос иловани текширинг."
    ),
]

async def generate(name, voice, text):
    mp3 = TEST_DIR / name.replace(".wav", ".mp3")
    wav = TEST_DIR / name
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(str(mp3))

    import subprocess
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(mp3), "-ar", "8000", "-ac", "1", "-acodec", "pcm_s16le", str(wav)],
        capture_output=True
    )
    mp3.unlink(missing_ok=True)
    print(f"  OK: {name} ({voice})")

async def main():
    print("Test ovozlar yaratilmoqda...\n")
    for name, voice, text in TESTS:
        await generate(name, voice, text)
    print(r"Joylashuv: C:\Users\Asus\ip-telefon\test_voices")
    print("Eshitib, qaysi biri yaxshi ekanini ayting!")

asyncio.run(main())
