"""
TTS (Text-to-Speech) Servisi
Matnni ovozga aylantirish - Ko'p til qo'llab-quvvatlanadi (uz, ru)
"""

import os
import asyncio
import logging
import hashlib
from pathlib import Path
from typing import Optional
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

# Tilga qarab Edge TTS ovozlari
LANG_VOICES = {
    "uz": "uz-UZ-MadinaNeural",
    "ru": "ru-RU-SvetlanaNeural",
    "kk": "kk-KZ-AigulNeural",
    "en": "en-US-JennyNeural",
}
DEFAULT_LANG = "uz"

# Tilga qarab buyurtma xabari matnlari
def _order_message_text(count: int, lang: str) -> str:
    """Tilga qarab buyurtma xabar matnini qaytarish"""
    lang = lang.lower() if lang else DEFAULT_LANG

    if lang == "ru":
        if count == 1:
            return "Здравствуйте, вас приветствует голосовой бот Nonbor. У вас 1 новый заказ. Пожалуйста, проверьте ваш заказ."
        else:
            return f"Здравствуйте, вас приветствует голосовой бот Nonbor. У вас {count} новых заказа. Пожалуйста, проверьте ваши заказы."
    elif lang == "kk":
        if count == 1:
            return f"Сәлеметсіз бе, мен Nonbor дауыстық бот қызметімін, сізде 1 тапсырыс бар, тапсырысыңызды тексеріңіз."
        else:
            return f"Сәлеметсіз бе, мен Nonbor дауыстық бот қызметімін, сізде {count} тапсырыс бар, тапсырыстарыңызды тексеріңіз."
    else:
        # uz va boshqa tillar uchun o'zbek
        if count == 1:
            return "Assalomu alaykum, men nonbor ovozli bot xizmatiman, sizda 1 ta buyurtma bor, iltimos, buyurtmangizni tekshiring."
        else:
            return f"Assalomu alaykum, men nonbor ovozli bot xizmatiman, sizda {count} ta buyurtma bor, iltimos, buyurtmalaringizni tekshiring."


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

    Ko'p til qo'llab-quvvatlanadi: uz, ru, kk
    Foydalanish:
        tts = TTSService(audio_dir="/path/to/audio")
        audio_path = await tts.generate_order_message(count=5, lang='ru')
    """

    def __init__(self, audio_dir: Path, provider: str = "edge"):
        self.audio_dir = Path(audio_dir)
        self.audio_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir = self.audio_dir / "cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.provider_type = provider

        # Tilga qarab provider cache: {lang: EdgeTTSProvider}
        self._providers: dict = {}

        logger.info(f"TTS servisi ishga tushdi: {provider}, tillar: {list(LANG_VOICES.keys())}")

    def _get_provider(self, lang: str) -> BaseTTSProvider:
        """Tilga mos provider olish (cache da saqlash)"""
        lang = lang.lower() if lang else DEFAULT_LANG
        if lang not in self._providers:
            if self.provider_type == "google":
                # Google TTS faqat uz/ru ni to'g'ri qo'llab-quvvatlaydi
                self._providers[lang] = GoogleTTSProvider(language=lang if lang in ("uz", "ru") else "uz")
            else:
                voice = LANG_VOICES.get(lang, LANG_VOICES[DEFAULT_LANG])
                self._providers[lang] = EdgeTTSProvider(voice=voice)
            logger.info(f"TTS provider yaratildi: lang={lang}, provider={self.provider_type}")
        return self._providers[lang]

    def _get_cache_path(self, text: str, lang: str = DEFAULT_LANG) -> Path:
        """Matn va til uchun cache fayl yo'lini olish"""
        key = f"{lang}_{text}"
        text_hash = hashlib.md5(key.encode()).hexdigest()
        return self.cache_dir / f"{text_hash}.wav"

    async def generate_order_message(self, count: int, lang: str = DEFAULT_LANG) -> Optional[Path]:
        """
        Buyurtma xabarini tilga qarab yaratish

        Args:
            count: Buyurtmalar soni
            lang: Til kodi ('uz', 'ru', 'kk', ...)

        Returns:
            Audio fayl yo'li yoki None
        """
        lang = (lang or DEFAULT_LANG).lower()
        text = _order_message_text(count, lang)

        # Cache tekshirish
        cache_path = self._get_cache_path(text, lang)
        if cache_path.exists():
            logger.debug(f"TTS cache dan olindi: {lang}/{count} ta buyurtma")
            return cache_path

        # Tilga mos provider bilan yangi audio yaratish
        provider = self._get_provider(lang)
        logger.info(f"TTS yaratilmoqda: lang={lang}, count={count}")
        success = await provider.synthesize(text, cache_path)

        if success:
            # Yangi yaratilgan faylni Asterisk katalogiga ham ko'chirish
            await self._sync_single_file(cache_path)
            return cache_path
        return None

    async def generate_custom_message(self, text: str, filename: str = None, lang: str = DEFAULT_LANG) -> Optional[Path]:
        """
        Maxsus xabar yaratish

        Args:
            text: Xabar matni
            filename: Fayl nomi (ixtiyoriy)
            lang: Til kodi

        Returns:
            Audio fayl yo'li yoki None
        """
        lang = (lang or DEFAULT_LANG).lower()
        if filename:
            output_path = self.audio_dir / f"{filename}.wav"
        else:
            output_path = self._get_cache_path(text, lang)

        if output_path.exists():
            return output_path

        provider = self._get_provider(lang)
        success = await provider.synthesize(text, output_path)

        if success:
            await self._sync_single_file(output_path)
            return output_path
        return None

    def get_audio_path(self, count: int, lang: str = DEFAULT_LANG) -> Optional[Path]:
        """Mavjud audio faylni olish (agar cache da bo'lsa)"""
        lang = (lang or DEFAULT_LANG).lower()
        text = _order_message_text(count, lang)
        cache_path = self._get_cache_path(text, lang)
        if cache_path.exists():
            return cache_path
        return None

    async def pregenerate_messages(self, max_count: int = 20):
        """
        Oldindan xabarlar yaratish (1 dan max_count gacha)
        Asosiy tillar uchun: uz va ru
        """
        langs = ["uz", "ru"]
        logger.info(f"TTS xabarlarini oldindan yaratish: 1-{max_count}, tillar: {langs}")

        for lang in langs:
            for i in range(1, max_count + 1):
                await self.generate_order_message(i, lang=lang)
                logger.debug(f"TTS yaratildi: {lang}/{i} ta buyurtma")

        logger.info("TTS oldindan yaratish tugadi")

        # Asterisk katalogiga ko'chirish
        await self.sync_to_wsl()

    async def _sync_single_file(self, wav_path: Path):
        """Bitta audio faylni Asterisk katalogiga ko'chirish"""
        import shutil

        default_platform = "wsl" if os.name == "nt" else "linux"
        platform = os.getenv("PLATFORM", default_platform).lower()
        default_sounds = "/tmp/autodialer" if os.name == "nt" else "/var/lib/asterisk/sounds/autodialer"
        sounds_path = os.getenv("ASTERISK_SOUNDS_PATH", default_sounds)

        try:
            if platform == "linux":
                os.makedirs(sounds_path, exist_ok=True)
                dest = os.path.join(sounds_path, wav_path.name)
                shutil.copy2(str(wav_path), dest)
                logger.debug(f"Audio ko'chirildi: {wav_path.name} -> {sounds_path}")
            else:
                import subprocess
                wav_wsl = str(wav_path).replace("\\", "/")
                if len(wav_wsl) > 1 and wav_wsl[1] == ":":
                    wav_wsl = f"/mnt/{wav_wsl[0].lower()}{wav_wsl[2:]}"
                subprocess.run(
                    ["wsl", "mkdir", "-p", sounds_path],
                    capture_output=True, timeout=5
                )
                subprocess.run(
                    ["wsl", "cp", wav_wsl, f"{sounds_path}/"],
                    capture_output=True, timeout=10
                )
        except Exception as e:
            logger.warning(f"Audio sync xatosi ({wav_path.name}): {e}")

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
        default_platform = "wsl" if os.name == "nt" else "linux"
        platform = os.getenv("PLATFORM", default_platform).lower()
        default_sounds = "/tmp/autodialer" if os.name == "nt" else "/var/lib/asterisk/sounds/autodialer"
        sounds_path = os.getenv("ASTERISK_SOUNDS_PATH", default_sounds)

        try:
            import glob
            wav_files = glob.glob(str(cache_dir / "*.wav"))

            if not wav_files:
                logger.warning(f"Hech qanday .wav fayl topilmadi: {cache_dir}")
                return

            if platform == "linux":
                os.makedirs(sounds_path, exist_ok=True)
                for wav_file in wav_files:
                    dest = os.path.join(sounds_path, os.path.basename(wav_file))
                    shutil.copy2(wav_file, dest)
                logger.info(f"Audio fayllar ko'chirildi: {len(wav_files)} ta fayl -> {sounds_path}")

            else:
                subprocess.run(
                    ["wsl", "mkdir", "-p", sounds_path],
                    capture_output=True, timeout=10
                )
                for wav_file in wav_files:
                    wav_file_wsl = str(wav_file).replace("\\", "/")
                    if len(wav_file_wsl) > 1 and wav_file_wsl[1] == ":":
                        wav_file_wsl = f"/mnt/{wav_file_wsl[0].lower()}{wav_file_wsl[2:]}"
                    result = subprocess.run(
                        ["wsl", "cp", wav_file_wsl, f"{sounds_path}/"],
                        capture_output=True, timeout=10
                    )
                    if result.returncode != 0:
                        logger.warning(f"Fayl ko'chirishda xato {wav_file}: {result.stderr.decode()}")
                logger.info(f"Audio fayllar WSL ga ko'chirildi: {len(wav_files)} ta fayl")

        except subprocess.TimeoutExpired:
            logger.error("WSL buyrug'i timeout")
        except Exception as e:
            logger.error(f"Audio sync xatosi: {e}")
