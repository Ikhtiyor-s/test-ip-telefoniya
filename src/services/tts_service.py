"""
TTS (Text-to-Speech) Servisi
Matnni ovozga aylantirish - O'zbek tili qo'llab-quvvatlanadi
"""

import os
import logging
import hashlib
from pathlib import Path
from typing import Optional
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class BaseTTSProvider(ABC):
    """TTS provider uchun asosiy klass"""

    @abstractmethod
    async def synthesize(self, text: str, output_path: Path) -> bool:
        """Matnni ovozga aylantirish"""
        pass


class GoogleTTSProvider(BaseTTSProvider):
    """Google Text-to-Speech"""

    def __init__(self, language: str = "uz"):
        self.language = language

    async def synthesize(self, text: str, output_path: Path) -> bool:
        """Google TTS orqali ovoz yaratish"""
        try:
            from gtts import gTTS

            tts = gTTS(text=text, lang=self.language, slow=False)

            # MP3 ga saqlash
            mp3_path = output_path.with_suffix(".mp3")
            tts.save(str(mp3_path))

            # WAV ga convert qilish (Asterisk uchun 8kHz)
            await self._convert_to_wav(mp3_path, output_path)

            # MP3 ni o'chirish
            mp3_path.unlink(missing_ok=True)

            logger.info(f"TTS yaratildi: {output_path}")
            return True

        except Exception as e:
            logger.error(f"Google TTS xatosi: {e}")
            return False

    async def _convert_to_wav(self, mp3_path: Path, wav_path: Path):
        """MP3 ni WAV ga convert qilish (8kHz, mono)"""
        import subprocess

        cmd = [
            "ffmpeg", "-y",
            "-i", str(mp3_path),
            "-ar", "8000",
            "-ac", "1",
            "-acodec", "pcm_s16le",
            str(wav_path)
        ]

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL
        )
        await process.wait()


class EdgeTTSProvider(BaseTTSProvider):
    """Microsoft Edge TTS - Bepul va sifatli"""

    def __init__(self, voice: str = "uz-UZ-MadinaNeural"):
        self.voice = voice

    async def synthesize(self, text: str, output_path: Path) -> bool:
        """Edge TTS orqali ovoz yaratish"""
        try:
            import edge_tts

            communicate = edge_tts.Communicate(text, self.voice)

            # MP3 ga saqlash
            mp3_path = output_path.with_suffix(".mp3")
            await communicate.save(str(mp3_path))

            # WAV ga convert qilish
            await self._convert_to_wav(mp3_path, output_path)

            # MP3 ni o'chirish
            mp3_path.unlink(missing_ok=True)

            logger.info(f"Edge TTS yaratildi: {output_path}")
            return True

        except Exception as e:
            logger.error(f"Edge TTS xatosi: {e}")
            return False

    async def _convert_to_wav(self, mp3_path: Path, wav_path: Path):
        """MP3 ni WAV ga convert qilish"""
        import asyncio
        import subprocess

        cmd = [
            "ffmpeg", "-y",
            "-i", str(mp3_path),
            "-ar", "8000",
            "-ac", "1",
            "-acodec", "pcm_s16le",
            str(wav_path)
        ]

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL
        )
        await process.wait()


class TTSService:
    """
    TTS Servisi - Buyurtma xabarlarini ovozga aylantirish

    Foydalanish:
        tts = TTSService(audio_dir="/path/to/audio")
        audio_path = await tts.generate_order_message(count=5)
    """

    def __init__(self, audio_dir: Path, provider: str = "edge"):
        self.audio_dir = Path(audio_dir)
        self.audio_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir = self.audio_dir / "cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Provider tanlash
        if provider == "google":
            self.provider = GoogleTTSProvider(language="uz")
        else:
            self.provider = EdgeTTSProvider(voice="uz-UZ-MadinaNeural")

        logger.info(f"TTS servisi ishga tushdi: {provider}")

    def _get_cache_path(self, text: str) -> Path:
        """Matn uchun cache fayl yo'lini olish"""
        text_hash = hashlib.md5(text.encode()).hexdigest()
        return self.cache_dir / f"{text_hash}.wav"

    async def generate_order_message(self, count: int) -> Optional[Path]:
        """
        Buyurtma xabarini yaratish

        Args:
            count: Buyurtmalar soni

        Returns:
            Audio fayl yo'li yoki None
        """
        # Xabar matni
        if count == 1:
            text = "Assalomu alaykum, men nonbor ovozli bot xizmatiman, sizda 1 ta buyurtma bor, iltimos, buyurtmangizni tekshiring."
        else:
            text = f"Assalomu alaykum, men nonbor ovozli bot xizmatiman, sizda {count} ta buyurtma bor, iltimos, buyurtmalaringizni tekshiring."

        # Cache tekshirish
        cache_path = self._get_cache_path(text)
        if cache_path.exists():
            logger.debug(f"Cache dan olindi: {cache_path}")
            return cache_path

        # Yangi audio yaratish
        success = await self.provider.synthesize(text, cache_path)

        if success:
            return cache_path
        return None

    async def generate_custom_message(self, text: str, filename: str = None) -> Optional[Path]:
        """
        Maxsus xabar yaratish

        Args:
            text: Xabar matni
            filename: Fayl nomi (ixtiyoriy)

        Returns:
            Audio fayl yo'li yoki None
        """
        if filename:
            output_path = self.audio_dir / f"{filename}.wav"
        else:
            output_path = self._get_cache_path(text)

        if output_path.exists():
            return output_path

        success = await self.provider.synthesize(text, output_path)

        if success:
            return output_path
        return None

    def get_audio_path(self, count: int) -> Optional[Path]:
        """Mavjud audio faylni olish (agar cache da bo'lsa)"""
        if count == 1:
            text = "Assalomu alaykum, men nonbor ovozli bot xizmatiman, sizda 1 ta buyurtma bor, iltimos, buyurtmangizni tekshiring."
        else:
            text = f"Assalomu alaykum, men nonbor ovozli bot xizmatiman, sizda {count} ta buyurtma bor, iltimos, buyurtmalaringizni tekshiring."

        cache_path = self._get_cache_path(text)
        if cache_path.exists():
            return cache_path
        return None

    async def pregenerate_messages(self, max_count: int = 20):
        """
        Oldindan xabarlar yaratish (1 dan max_count gacha)
        Tizim ishga tushganda chaqiriladi
        """
        logger.info(f"TTS xabarlarini oldindan yaratish: 1-{max_count}")

        for i in range(1, max_count + 1):
            await self.generate_order_message(i)
            logger.debug(f"TTS yaratildi: {i} ta buyurtma")

        logger.info("TTS oldindan yaratish tugadi")

        # WSL ga audio fayllarni ko'chirish
        await self.sync_to_wsl()

    async def sync_to_wsl(self):
        """
        Audio fayllarni Asterisk katalogiga ko'chirish

        PLATFORM env ga qarab:
        - wsl: WSL /tmp/autodialer/ ga ko'chirish (Windows development)
        - linux: To'g'ridan-to'g'ri ASTERISK_SOUNDS_PATH ga ko'chirish (Production)
        """
        import subprocess
        import shutil

        cache_dir = self.audio_dir / "cache"
        if not cache_dir.exists():
            logger.warning("Cache katalogi topilmadi")
            return

        # Platform va yo'lni aniqlash
        # Auto-detect: Windows = wsl, Linux = linux
        default_platform = "wsl" if os.name == "nt" else "linux"
        platform = os.getenv("PLATFORM", default_platform).lower()
        sounds_path = os.getenv("ASTERISK_SOUNDS_PATH", "/tmp/autodialer")

        try:
            import glob
            wav_files = glob.glob(str(cache_dir / "*.wav"))

            if not wav_files:
                logger.warning(f"Hech qanday .wav fayl topilmadi: {cache_dir}")
                return

            if platform == "linux":
                # PRODUCTION: To'g'ridan-to'g'ri Linux da
                # Katalog yaratish
                os.makedirs(sounds_path, exist_ok=True)

                # Fayllarni ko'chirish
                for wav_file in wav_files:
                    dest = os.path.join(sounds_path, os.path.basename(wav_file))
                    shutil.copy2(wav_file, dest)

                logger.info(f"Audio fayllar ko'chirildi: {len(wav_files)} ta fayl -> {sounds_path}")

            else:
                # WSL (Windows development)
                # WSL da katalog yaratish
                subprocess.run(
                    ["wsl", "mkdir", "-p", sounds_path],
                    capture_output=True,
                    timeout=10
                )

                # Har bir faylni xavfsiz ko'chirish
                for wav_file in wav_files:
                    wav_file_wsl = str(wav_file).replace("\\", "/")
                    if len(wav_file_wsl) > 1 and wav_file_wsl[1] == ":":
                        wav_file_wsl = f"/mnt/{wav_file_wsl[0].lower()}{wav_file_wsl[2:]}"

                    result = subprocess.run(
                        ["wsl", "cp", wav_file_wsl, f"{sounds_path}/"],
                        capture_output=True,
                        timeout=10
                    )

                    if result.returncode != 0:
                        logger.warning(f"Fayl ko'chirishda xato {wav_file}: {result.stderr.decode()}")

                logger.info(f"Audio fayllar WSL ga ko'chirildi: {len(wav_files)} ta fayl")

        except subprocess.TimeoutExpired:
            logger.error("WSL buyrug'i timeout")
        except Exception as e:
            logger.error(f"Audio sync xatosi: {e}")


# Async import uchun
import asyncio
