"""
Autodialer Pro - Asosiy Servis
================================================================================

Professional autodialer tizimi - amoCRM buyurtmalarini kuzatish va
sotuvchilarga avtomatik qo'ng'iroq qilish

Jarayon:
1. Yangi buyurtma (TEKSHIRILMOQDA) keladi
2. 1.5 daqiqa kutish
3. Sotuvchiga qo'ng'iroq: "Sizda N ta yangi buyurtma bor"
4. Javob bo'lmasa → yana qo'ng'iroq (max 3 marta)
5. 3 daqiqada Telegram xabar
6. Status o'zgarsa → Telegram xabar o'chiriladi

================================================================================
"""

import asyncio
import logging
import signal
import sys
import os
from datetime import datetime, timedelta
from typing import Optional
from pathlib import Path
from dotenv import load_dotenv

# .env yuklash
load_dotenv(Path(__file__).parent.parent / ".env")

from services import (
    TTSService,
    AmoCRMService,
    AmoCRMPoller,
    AsteriskAMI,
    CallManager,
    CallStatus,
    TelegramService,
    TelegramNotificationManager,
    TelegramStatsHandler,
    StatsService,
    StatsCallResult,
    OrderResult
)

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/autodialer.log")
    ]
)
logger = logging.getLogger("autodialer")


class AutodialerState:
    """Autodialer holati"""

    def __init__(self):
        self.pending_orders_count: int = 0
        self.pending_order_ids: list = []  # Buyurtma IDlari
        self.last_new_order_time: Optional[datetime] = None
        self.call_attempts: int = 0
        self.call_started: bool = False  # Qo'ng'iroq jarayoni boshlandi
        self.waiting_for_call: bool = False
        self.telegram_notified: bool = False
        self.telegram_notify_time: Optional[datetime] = None

    def reset(self):
        """Holatni tozalash"""
        self.pending_orders_count = 0
        self.pending_order_ids = []
        self.last_new_order_time = None
        self.call_attempts = 0
        self.call_started = False
        self.waiting_for_call = False
        self.telegram_notified = False
        self.telegram_notify_time = None

    def new_order_received(self, count: int, order_ids: list):
        """Yangi buyurtma keldi"""
        self.pending_orders_count = count
        self.pending_order_ids = order_ids

        # Agar kutish boshlanmagan YOKI oldingi qo'ng'iroq tugagan bo'lsa
        if not self.waiting_for_call or self.call_started:
            self.last_new_order_time = datetime.now()
            self.waiting_for_call = True
            self.call_started = False  # Yangi qo'ng'iroq uchun reset
            self.call_attempts = 0
            self.telegram_notified = False
            self.telegram_notify_time = datetime.now() + timedelta(seconds=180)


class AutodialerPro:
    """
    Autodialer Pro - Asosiy klass

    Barcha komponentlarni birlashtiradi va jarayonni boshqaradi
    """

    def __init__(
        self,
        # amoCRM
        amocrm_subdomain: str,
        amocrm_token: str,
        # Sarkor SIP
        sip_host: str = "127.0.0.1",
        ami_port: int = 5038,
        ami_username: str = "autodialer",
        ami_password: str = "autodialer123",
        # Telegram
        telegram_token: str = None,
        telegram_chat_id: str = None,
        # Sotuvchi
        seller_phone: str = "+998948679300",
        # Vaqtlar
        wait_before_call: int = 90,  # 1.5 daqiqa
        telegram_alert_time: int = 180,  # 3 daqiqa
        max_call_attempts: int = 3,
        retry_interval: int = 60,
        # Yo'llar
        audio_dir: str = "audio"
    ):
        # Konfiguratsiya
        self.seller_phone = seller_phone
        self.wait_before_call = wait_before_call
        self.telegram_alert_time = telegram_alert_time
        self.max_call_attempts = max_call_attempts
        self.retry_interval = retry_interval
        self.audio_dir = Path(audio_dir)

        # Holat
        self.state = AutodialerState()
        self._running = False
        self._tasks = []

        # Servislar
        self.tts = TTSService(self.audio_dir, provider="edge")

        self.amocrm = AmoCRMService(
            subdomain=amocrm_subdomain,
            access_token=amocrm_token,
            status_name="TEKSHIRILMOQDA"
        )

        self.amocrm_poller = AmoCRMPoller(
            amocrm_service=self.amocrm,
            polling_interval=3,
            on_new_orders=self._on_new_orders,
            on_orders_resolved=self._on_orders_resolved
        )

        self.ami = AsteriskAMI(
            host=sip_host,
            port=ami_port,
            username=ami_username,
            password=ami_password
        )

        self.call_manager = CallManager(
            ami=self.ami,
            max_attempts=max_call_attempts,
            retry_interval=retry_interval
        )

        # Statistika servisi
        self.stats = StatsService(data_dir="data")

        if telegram_token and telegram_chat_id:
            self.telegram = TelegramService(
                bot_token=telegram_token,
                default_chat_id=telegram_chat_id
            )
            self.notification_manager = TelegramNotificationManager(self.telegram)
            self.stats_handler = TelegramStatsHandler(self.telegram, self.stats)
        else:
            self.telegram = None
            self.notification_manager = None
            self.stats_handler = None

        logger.info("AutodialerPro yaratildi")

    async def start(self):
        """Autodialer ni ishga tushirish"""
        logger.info("=" * 60)
        logger.info("AUTODIALER PRO ISHGA TUSHMOQDA")
        logger.info("=" * 60)

        self._running = True

        # Signal handlers (faqat Unix uchun, Windows da ishlamaydi)
        if sys.platform != "win32":
            for sig in (signal.SIGINT, signal.SIGTERM):
                asyncio.get_event_loop().add_signal_handler(
                    sig, lambda: asyncio.create_task(self.stop())
                )

        # TTS oldindan yaratish
        logger.info("TTS xabarlarini tayyorlash...")
        await self.tts.pregenerate_messages(max_count=20)

        # AMI ulanish
        logger.info("Asterisk AMI ga ulanish...")
        ami_connected = await self.ami.connect()
        if not ami_connected:
            logger.error("AMI ulanish muvaffaqiyatsiz!")
            # AMI siz ham davom etish mumkin (faqat Telegram)

        # SIP registratsiya tekshirish
        if ami_connected:
            registered = await self.ami.check_registration()
            if registered:
                logger.info("SIP registratsiya: OK")
            else:
                logger.warning("SIP registratsiya: MUVAFFAQIYATSIZ")

        # amoCRM polling boshlash
        logger.info("amoCRM polling boshlash...")
        await self.amocrm_poller.start()

        # Stats handler polling boshlash
        if self.stats_handler:
            logger.info("Telegram stats handler boshlash...")
            await self.stats_handler.start_polling()

        # Ishga tushganda sinxronizatsiya - amoCRM va Telegram
        await self._sync_on_startup()

        # Asosiy loop
        logger.info("=" * 60)
        logger.info("AUTODIALER PRO ISHLAYAPTI")
        logger.info("=" * 60)

        # Asosiy task
        self._tasks.append(asyncio.create_task(self._main_loop()))

        # Wait
        try:
            await asyncio.gather(*self._tasks)
        except asyncio.CancelledError:
            pass

    async def stop(self):
        """Autodialer ni to'xtatish"""
        logger.info("Autodialer to'xtatilmoqda...")
        self._running = False

        # Tasks ni bekor qilish
        for task in self._tasks:
            task.cancel()

        # Servislarni yopish
        await self.amocrm_poller.stop()
        if self.stats_handler:
            await self.stats_handler.stop_polling()
        await self.ami.disconnect()
        await self.amocrm.close()
        if self.telegram:
            await self.telegram.close()

        logger.info("Autodialer to'xtatildi")

    async def _sync_on_startup(self):
        """
        Ishga tushganda amoCRM va Telegram ni sinxronlashtirish

        Agar TEKSHIRILMOQDA statusida buyurtmalar bo'lsa:
        - Telegram ga yangi xabar yuborish
        - Holatni tiklash

        Agar buyurtmalar yo'q bo'lsa:
        - Telegramdagi eski xabarlarni o'chirish
        """
        logger.info("Sinxronizatsiya: amoCRM va Telegram tekshirilmoqda...")

        try:
            # TEKSHIRILMOQDA dagi buyurtmalarni olish
            leads = await self.amocrm.get_leads_by_status()

            if not leads:
                logger.info("Sinxronizatsiya: TEKSHIRILMOQDA da buyurtmalar yo'q")
                # Telegramdagi eski xabarlarni o'chirish
                await self._cleanup_old_telegram_messages()
                self.state.reset()
                return

            count = len(leads)
            order_ids = [lead["id"] for lead in leads]

            logger.info(f"Sinxronizatsiya: {count} ta buyurtma topildi, Telegram xabar yuborilmoqda...")

            # Holatni tiklash
            self.state.pending_orders_count = count
            self.state.pending_order_ids = order_ids
            self.state.last_new_order_time = datetime.now()
            self.state.waiting_for_call = True
            self.state.call_started = True  # Qo'ng'iroq qilmaslik uchun
            self.state.telegram_notified = True  # Telegram yuborilgan

            # Telegram xabar yuborish
            await self._send_telegram_for_remaining()

            logger.info(f"Sinxronizatsiya tugadi: {count} ta buyurtma uchun Telegram xabar yuborildi")

        except Exception as e:
            logger.error(f"Sinxronizatsiya xatosi: {e}")

    async def _cleanup_old_telegram_messages(self):
        """
        Telegramdagi eski buyurtma xabarlarini o'chirish

        So'nggi 10 ta xabarni tekshirib, buyurtma xabarlarini o'chiradi
        """
        if not self.telegram:
            return

        try:
            logger.info("Telegram: eski xabarlarni tozalash...")

            # So'nggi xabarlarni olish (getUpdates orqali)
            import aiohttp
            url = f"https://api.telegram.org/bot{self.telegram.bot_token}/getUpdates"
            params = {"limit": 100, "offset": -100}

            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    data = await response.json()

                    if not data.get("ok"):
                        return

                    results = data.get("result", [])
                    deleted_count = 0

                    for update in results:
                        message = update.get("message") or update.get("channel_post")
                        if not message:
                            continue

                        # Faqat bizning guruhdan
                        chat_id = str(message.get("chat", {}).get("id", ""))
                        if chat_id != self.telegram.default_chat_id:
                            continue

                        # Buyurtma xabari ekanligini tekshirish
                        text = message.get("text", "")
                        if "DIQQAT!" in text and "buyurtma" in text.lower():
                            msg_id = message.get("message_id")
                            try:
                                await self.telegram.delete_message(msg_id)
                                deleted_count += 1
                                logger.debug(f"Eski xabar o'chirildi: {msg_id}")
                            except:
                                pass

                    if deleted_count > 0:
                        logger.info(f"Telegram: {deleted_count} ta eski xabar o'chirildi")
                    else:
                        logger.info("Telegram: o'chiriladigan eski xabar topilmadi")

        except Exception as e:
            logger.error(f"Telegram tozalash xatosi: {e}")

    async def _main_loop(self):
        """Asosiy ishlash sikli"""
        while self._running:
            try:
                await self._check_and_process()
                await asyncio.sleep(1)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Main loop xatosi: {e}")
                await asyncio.sleep(5)

    async def _check_and_process(self):
        """Holatni tekshirish va qayta ishlash"""
        if not self.state.waiting_for_call:
            return

        now = datetime.now()

        # Kutish vaqti o'tdimi?
        if self.state.last_new_order_time:
            elapsed = (now - self.state.last_new_order_time).total_seconds()

            # Qo'ng'iroq qilish vaqti (faqat bir marta chaqiriladi - ichida barcha urinishlar)
            if elapsed >= self.wait_before_call and not self.state.call_started:
                self.state.call_started = True
                await self._make_call()

            # 3 daqiqa (180 soniya) o'tgandan keyin Telegram xabar yuborish
            if elapsed >= self.telegram_alert_time and not self.state.telegram_notified:
                logger.info(f"3 daqiqa o'tdi, Telegram xabar yuborish...")
                await self._send_telegram_for_remaining()
                self.state.telegram_notified = True

    async def _on_new_orders(self, count: int, new_ids: list):
        """Yangi buyurtmalar callback"""
        logger.info(f"Yangi buyurtmalar: {len(new_ids)} ta, Jami: {count} ta")

        # Holatni yangilash
        old_count = self.state.pending_orders_count
        self.state.new_order_received(count, new_ids)

        # Agar ilgari kutish boshlangan bo'lsa, faqat sonni yangilash
        if old_count > 0:
            logger.debug(f"Buyurtmalar soni yangilandi: {old_count} -> {count}")

    async def _on_orders_resolved(self, resolved_count: int, remaining_count: int):
        """Buyurtmalar tekshirildi callback"""
        logger.info(f"Tekshirildi: {resolved_count} ta, Qoldi: {remaining_count} ta")

        # Qabul qilingan buyurtmalarni statistikaga yozish
        # (Telegram yuborilgan yoki yuborilmaganini aniqlash)
        telegram_was_sent = self.state.telegram_notified

        # Har bir qabul qilingan buyurtma uchun statistika
        for order_id in self.state.pending_order_ids[:resolved_count]:
            try:
                order_data = await self.amocrm.get_order_full_data(order_id)
                self.stats.record_order(
                    order_id=order_id,
                    order_number=order_data.get("order_number", str(order_id)),
                    seller_name=order_data.get("seller_name", "Noma'lum"),
                    seller_phone=order_data.get("seller_phone", "Noma'lum"),
                    client_name=order_data.get("client_name", "Noma'lum"),
                    product_name=order_data.get("product_name", "Noma'lum"),
                    price=order_data.get("price", 0),
                    result=OrderResult.ACCEPTED,  # TEKSHIRILMOQDA dan chiqdi = qabul qilindi
                    call_attempts=self.state.call_attempts,
                    telegram_sent=telegram_was_sent
                )
            except Exception as e:
                logger.error(f"Buyurtma #{order_id} statistika yozishda xato: {e}")

        # Avvalgi xabarlarni o'chirish
        await self._delete_telegram_messages()

        # Agar hammasi tekshirilgan bo'lsa
        if remaining_count == 0:
            logger.info("Barcha buyurtmalar tekshirildi!")
            self.state.reset()
        else:
            # Qolgan buyurtmalar uchun yangi Telegram xabar yuborish
            self.state.pending_orders_count = remaining_count
            logger.info(f"Qolgan {remaining_count} ta buyurtma uchun yangi Telegram xabar...")
            await self._send_telegram_for_remaining()

    async def _make_call(self):
        """Har bir sotuvchiga alohida qo'ng'iroq qilish"""
        order_ids = self.state.pending_order_ids

        logger.info(f"Qo'ng'iroq tayyorlash: {len(order_ids)} ta buyurtma")

        # Barcha buyurtmalarni olish va sotuvchi bo'yicha guruhlash
        sellers = {}
        for order_id in order_ids:
            try:
                order_data = await self.amocrm.get_order_full_data(order_id)
                seller_phone = order_data.get("seller_phone", "Noma'lum")

                # Telefon raqamini formatlash
                if seller_phone and seller_phone != "Noma'lum":
                    # Faqat raqamlarni olish
                    phone_digits = ''.join(filter(str.isdigit, seller_phone))
                    if len(phone_digits) >= 9:
                        # +998 formatiga o'tkazish
                        if len(phone_digits) == 9:
                            seller_phone = f"+998{phone_digits}"
                        elif len(phone_digits) == 12 and phone_digits.startswith("998"):
                            seller_phone = f"+{phone_digits}"
                        else:
                            seller_phone = f"+{phone_digits}"
                    else:
                        seller_phone = None

                if not seller_phone:
                    logger.warning(f"Buyurtma #{order_id}: sotuvchi telefoni topilmadi, default ishlatiladi")
                    seller_phone = self.seller_phone

                if seller_phone not in sellers:
                    sellers[seller_phone] = {
                        "seller_name": order_data.get("seller_name", "Noma'lum"),
                        "seller_phone": seller_phone,
                        "orders": []
                    }
                sellers[seller_phone]["orders"].append(order_data)

            except Exception as e:
                logger.error(f"Buyurtma #{order_id} ma'lumotini olishda xato: {e}")

        if not sellers:
            logger.warning("Hech qanday sotuvchi topilmadi, default raqamga qo'ng'iroq")
            sellers[self.seller_phone] = {
                "seller_name": "Noma'lum",
                "seller_phone": self.seller_phone,
                "orders": []
            }

        # Har bir sotuvchiga alohida qo'ng'iroq
        total_attempts = 0
        for seller_phone, seller_data in sellers.items():
            order_count = len(seller_data["orders"])
            seller_name = seller_data["seller_name"]

            logger.info(f"Qo'ng'iroq: {seller_name} ({seller_phone}), {order_count} ta buyurtma")

            # TTS audio olish
            audio_path = await self.tts.generate_order_message(order_count)
            if not audio_path:
                logger.error(f"TTS audio yaratilmadi: {seller_phone}")
                total_attempts = self.max_call_attempts
                continue

            # Qo'ng'iroq qilish - barcha urinishlar (retry bilan)
            result = await self.call_manager.make_call_with_retry(
                phone_number=seller_phone,
                audio_file=str(audio_path),
                on_attempt=self._on_call_attempt
            )

            # Statistikaga yozish
            order_ids_for_call = [o.get("lead_id") for o in seller_data["orders"]]
            if result.is_answered:
                logger.info(f"Qo'ng'iroq muvaffaqiyatli: {seller_name} ({seller_phone})")
                self.stats.record_call(
                    phone=seller_phone,
                    seller_name=seller_name,
                    order_count=order_count,
                    attempts=self.state.call_attempts,
                    result=StatsCallResult.ANSWERED,
                    order_ids=order_ids_for_call
                )
            else:
                logger.warning(f"Qo'ng'iroq muvaffaqiyatsiz: {seller_name} ({seller_phone}) - {result.status}")
                total_attempts = max(total_attempts, self.state.call_attempts)
                self.stats.record_call(
                    phone=seller_phone,
                    seller_name=seller_name,
                    order_count=order_count,
                    attempts=self.state.call_attempts,
                    result=StatsCallResult.NO_ANSWER,
                    order_ids=order_ids_for_call
                )

        # Barcha qo'ng'iroqlar tugadi
        # Agar javob berilgan bo'lsa - state tozalash va Telegram yubormaslik
        if total_attempts == 0:
            logger.info("Barcha qo'ng'iroqlar muvaffaqiyatli, state tozalanmoqda")
            self.state.reset()
            # Telegram xabarlarni o'chirish
            await self._delete_telegram_messages()

    async def _on_call_attempt(self, attempt: int, max_attempts: int):
        """Qo'ng'iroq urinishi callback"""
        self.state.call_attempts = attempt
        logger.info(f"Qo'ng'iroq urinishi: {attempt}/{max_attempts}")

    async def _send_telegram_alert(self):
        """Telegram xabar yuborish - sotuvchi bo'yicha guruhlangan"""
        if not self.notification_manager:
            return

        order_ids = self.state.pending_order_ids
        logger.info(f"Telegram xabar yuborish: {len(order_ids)} ta buyurtma")

        # Barcha buyurtmalarni olish
        all_orders = []
        for order_id in order_ids:
            try:
                order_data = await self.amocrm.get_order_full_data(order_id)
                all_orders.append(order_data)
            except Exception as e:
                logger.error(f"Buyurtma #{order_id} ma'lumotini olishda xato: {e}")

        # Sotuvchi bo'yicha guruhlash
        sellers = {}
        for order in all_orders:
            seller_phone = order.get("seller_phone", "Noma'lum")
            if seller_phone not in sellers:
                sellers[seller_phone] = {
                    "seller_name": order.get("seller_name", "Noma'lum"),
                    "seller_phone": seller_phone,
                    "seller_address": order.get("seller_address", "Noma'lum"),
                    "orders": []
                }
            sellers[seller_phone]["orders"].append(order)

        # Har bir sotuvchi uchun bitta xabar
        for seller_phone, seller_data in sellers.items():
            try:
                logger.info(f"Sotuvchi {seller_data['seller_name']}: {len(seller_data['orders'])} ta buyurtma")
                await self.notification_manager.notify_seller_orders(
                    seller_data,
                    self.state.call_attempts
                )
            except Exception as e:
                logger.error(f"Sotuvchi {seller_phone} xabar yuborishda xato: {e}")

        self.state.telegram_notified = True

    async def _delete_telegram_messages(self):
        """Telegram xabarlarni o'chirish"""
        if not self.notification_manager:
            return

        if self.notification_manager._active_message_ids:
            logger.info(f"Telegram xabarlarni o'chirish: {len(self.notification_manager._active_message_ids)} ta")
            for msg_id in self.notification_manager._active_message_ids:
                try:
                    await self.telegram.delete_message(msg_id)
                    logger.debug(f"Xabar o'chirildi: {msg_id}")
                except Exception as e:
                    logger.error(f"Xabar o'chirishda xato {msg_id}: {e}")
            self.notification_manager._active_message_ids = []

    async def _send_telegram_for_remaining(self):
        """Qolgan buyurtmalar uchun Telegram xabar yuborish (birinchi tekshirilganda)"""
        if not self.notification_manager:
            return

        # Hozirgi TEKSHIRILMOQDA dagi barcha buyurtmalarni olish
        leads = await self.amocrm.get_leads_by_status()
        if not leads:
            return

        order_ids = [lead["id"] for lead in leads]
        logger.info(f"Qolgan buyurtmalar uchun Telegram: {len(order_ids)} ta")

        # Barcha buyurtmalarni olish
        all_orders = []
        for order_id in order_ids:
            try:
                order_data = await self.amocrm.get_order_full_data(order_id)
                all_orders.append(order_data)
            except Exception as e:
                logger.error(f"Buyurtma #{order_id} ma'lumotini olishda xato: {e}")

        # Sotuvchi bo'yicha guruhlash
        sellers = {}
        for order in all_orders:
            seller_phone = order.get("seller_phone", "Noma'lum")
            if seller_phone not in sellers:
                sellers[seller_phone] = {
                    "seller_name": order.get("seller_name", "Noma'lum"),
                    "seller_phone": seller_phone,
                    "seller_address": order.get("seller_address", "Noma'lum"),
                    "orders": []
                }
            sellers[seller_phone]["orders"].append(order)

        # Har bir sotuvchi uchun yangi xabar
        for seller_phone, seller_data in sellers.items():
            try:
                logger.info(f"Sotuvchi {seller_data['seller_name']}: {len(seller_data['orders'])} ta buyurtma")
                await self.notification_manager.notify_seller_orders(
                    seller_data,
                    self.state.call_attempts  # Qo'ng'iroq urinishlari soni
                )
            except Exception as e:
                logger.error(f"Sotuvchi {seller_phone} xabar yuborishda xato: {e}")


async def main():
    """Asosiy funksiya"""

    autodialer = AutodialerPro(
        # amoCRM
        amocrm_subdomain=os.getenv("AMOCRM_SUBDOMAIN", "welltech"),
        amocrm_token=os.getenv("AMOCRM_TOKEN", "YOUR_TOKEN"),

        # Asterisk AMI (WSL)
        sip_host=os.getenv("AMI_HOST", "172.29.124.85"),
        ami_port=int(os.getenv("AMI_PORT", "5038")),
        ami_username=os.getenv("AMI_USERNAME", "autodialer"),
        ami_password=os.getenv("AMI_PASSWORD", "autodialer123"),

        # Telegram
        telegram_token=os.getenv("TELEGRAM_BOT_TOKEN"),
        telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID"),

        # Sotuvchi
        seller_phone=os.getenv("SELLER_PHONE", "+998948679300"),

        # Vaqtlar
        wait_before_call=int(os.getenv("WAIT_BEFORE_CALL", "90")),
        telegram_alert_time=int(os.getenv("TELEGRAM_ALERT_TIME", "180")),
        max_call_attempts=int(os.getenv("MAX_CALL_ATTEMPTS", "3")),
        retry_interval=int(os.getenv("RETRY_INTERVAL", "60")),
    )

    await autodialer.start()


if __name__ == "__main__":
    asyncio.run(main())
