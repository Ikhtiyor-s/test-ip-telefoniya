"""
Autodialer Pro - Asosiy Servis
================================================================================

Professional autodialer tizimi - Nonbor API buyurtmalarini kuzatish va
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
from typing import Optional, Dict
from pathlib import Path
from collections import OrderedDict
from dotenv import load_dotenv

# .env yuklash
load_dotenv(Path(__file__).parent.parent / ".env")

from services import (
    TTSService,
    NonborService,
    NonborPoller,
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


class BoundedOrderCache:
    """
    Buyurtmalar keshi - Memory leak oldini olish uchun

    Xususiyatlar:
    - Maksimal hajm chegaralangan (default: 1000 buyurtma)
    - TTL (Time To Live) - 24 soatdan keyin o'chiriladi
    - OrderedDict asosida - eng eski yozuvlar birinchi o'chiriladi
    """

    def __init__(self, max_size: int = 1000, ttl_hours: int = 24):
        """
        Args:
            max_size: Maksimal buyurtmalar soni
            ttl_hours: Buyurtma esdan chiqish vaqti (soatda)
        """
        self.cache = OrderedDict()
        self.max_size = max_size
        self.ttl = timedelta(hours=ttl_hours)
        logger.info(f"BoundedOrderCache yaratildi: max_size={max_size}, ttl={ttl_hours}h")

    def add(self, order_id: int):
        """Buyurtmani keshga qo'shish"""
        now = datetime.now()

        # Eskirgan yozuvlarni o'chirish
        expired_keys = [
            k for k, v in self.cache.items()
            if now - v > self.ttl
        ]
        for key in expired_keys:
            del self.cache[key]
            logger.debug(f"Eskirgan buyurtma o'chirildi: #{key}")

        # Hajm chegarasini nazorat qilish
        while len(self.cache) >= self.max_size:
            removed_id = self.cache.popitem(last=False)[0]  # Eng eskisini o'chirish
            logger.debug(f"Kesh to'ldi, eng eski buyurtma o'chirildi: #{removed_id}")

        # Yangi buyurtmani qo'shish
        self.cache[order_id] = now
        logger.debug(f"Buyurtma keshga qo'shildi: #{order_id}")

    def contains(self, order_id: int) -> bool:
        """Buyurtma keshda bormi tekshirish"""
        if order_id not in self.cache:
            return False

        # TTL tekshirish
        now = datetime.now()
        if now - self.cache[order_id] > self.ttl:
            del self.cache[order_id]
            logger.debug(f"Eskirgan buyurtma o'chirildi: #{order_id}")
            return False

        return True

    def size(self) -> int:
        """Kesh hajmi"""
        return len(self.cache)


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
        self.new_order_ids_for_call: list = []  # Yangi qo'ng'iroq qilish uchun buyurtmalar
        self.order_timestamps: dict = {}  # {order_id: datetime} - Har bir buyurtmaning kelgan vaqti
        self.last_communicated_orders: dict = {}  # {seller_phone: [order_ids]} - Har bir sotuvchiga oxirgi marta qaysi buyurtmalar haqida xabar berilgan
        self.call_in_progress: bool = False  # Hozir qo'ng'iroq jarayonida
        self.global_retry_count: int = 0  # Global qayta urinish hisoblagichi - barcha buyurtmalar uchun
        self.last_telegram_order_ids: set = set()  # Oxirgi marta Telegram ga yuborilgan buyurtmalar ID lari
        self.last_180s_check_time: Optional[datetime] = None  # Oxirgi 180s timer tekshiruv vaqti

    def reset(self):
        """Holatni tozalash - FAQAT qo'ng'iroq state, 180s timer uchun pending_order_ids saqlanadi"""
        # pending_orders_count va pending_order_ids ni SAQLAB qolamiz
        # Chunki buyurtmalar hali TEKSHIRILMOQDA da bo'lishi mumkin va 180s timer davom etishi kerak
        # self.pending_orders_count = 0  # DISABLED - 180s timer uchun
        # self.pending_order_ids = []  # DISABLED - 180s timer uchun kerak
        self.last_new_order_time = None
        self.call_attempts = 0
        self.call_started = False
        self.waiting_for_call = False
        self.telegram_notified = False
        # MUHIM: telegram_notify_time va order_timestamps ni SAQLAB qolamiz
        # 180s timer uchun kerak - buyurtmalar TEKSHIRILMOQDA da qolsa davom etadi
        # self.telegram_notify_time = None  # DISABLED - 180s timer davom etishi uchun
        self.new_order_ids_for_call = []
        # self.order_timestamps = {}  # DISABLED - 180s timer davom etishi uchun
        # MUHIM: last_communicated_orders ni SAQLAB qolamiz - takroriy qo'ng'iroqlarni oldini olish uchun
        # self.last_communicated_orders = {}  # DISABLED - eski buyurtmalar haqida qayta xabar bermaslik uchun
        self.call_in_progress = False
        self.global_retry_count = 0  # Global retry ni ham reset qilamiz
        # self.last_telegram_order_ids = set()  # DISABLED - 180s timer davom etishi uchun saqlab qolamiz

    def new_order_received(self, count: int, order_ids: list):
        """Yangi buyurtma keldi"""
        self.pending_orders_count = count
        self.pending_order_ids = order_ids

        # Agar kutish boshlanmagan YOKI (oldingi qo'ng'iroq tugagan bo'lsa VA qo'ng'iroq jarayonida EMAS)
        # MUHIM: call_in_progress tekshirish - ikki qo'ng'iroq bir vaqtda bo'lmasligi uchun
        if not self.waiting_for_call or (self.call_started and not self.call_in_progress):
            self.last_new_order_time = datetime.now()
            self.waiting_for_call = True
            self.call_started = False  # Yangi qo'ng'iroq uchun reset
            self.call_attempts = 0
            self.telegram_notified = False
            self.global_retry_count = 0  # Yangi buyurtmalar uchun global retry ni reset qilamiz
            # telegram_notify_time ni o'rnatmaymiz - 180s timer avtomatik ishlaydi


class AutodialerPro:
    """
    Autodialer Pro - Asosiy klass

    Barcha komponentlarni birlashtiradi va jarayonni boshqaradi
    """

    def __init__(
        self,
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

        # Buyurtmalar keshi - Memory leak oldini olish
        self._recorded_orders = BoundedOrderCache(max_size=1000, ttl_hours=24)

        # Guruh xabarlari - order_id -> {msg_id, biz_id, chat_id}
        self._group_order_messages: Dict[int, dict] = {}

        # Qo'ng'iroq urinishlari soni (state.reset() dan keyin ham saqlanadi)
        self._last_call_attempts = 0

        # Servislar
        self.tts = TTSService(self.audio_dir, provider="edge")

        self.nonbor = NonborService(status_name="CHECKING")

        self.nonbor_poller = NonborPoller(
            nonbor_service=self.nonbor,
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
        # Data katalogi - loyiha ildiziga nisbatan
        project_root = Path(__file__).parent.parent
        data_dir = str(project_root / "data")

        self.stats = StatsService(data_dir=data_dir)

        if telegram_token and telegram_chat_id:
            self.telegram = TelegramService(
                bot_token=telegram_token,
                default_chat_id=telegram_chat_id
            )
            self.notification_manager = TelegramNotificationManager(self.telegram, data_dir=data_dir)
            self.stats_handler = TelegramStatsHandler(self.telegram, self.stats, self.nonbor)
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

        # Nonbor API polling boshlash
        logger.info("Nonbor API polling boshlash...")
        await self.nonbor_poller.start()

        # Stats handler polling boshlash
        if self.stats_handler:
            logger.info("Telegram stats handler boshlash...")
            await self.stats_handler.start_polling()

        # Ishga tushganda sinxronizatsiya - Nonbor API va Telegram
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
        await self.nonbor_poller.stop()
        if self.stats_handler:
            await self.stats_handler.stop_polling()
        await self.ami.disconnect()
        await self.nonbor.close()
        if self.telegram:
            await self.telegram.close()

        logger.info("Autodialer to'xtatildi")

    async def _sync_on_startup(self):
        """
        Ishga tushganda Nonbor API va Telegram ni sinxronlashtirish

        Agar CHECKING statusida buyurtmalar bo'lsa:
        - Telegram ga yangi xabar yuborish
        - Holatni tiklash

        Agar buyurtmalar yo'q bo'lsa:
        - Telegramdagi eski xabarlarni o'chirish
        """
        logger.info("Sinxronizatsiya: Nonbor API va Telegram tekshirilmoqda...")

        try:
            # CHECKING dagi buyurtmalarni olish
            leads = await self.nonbor.get_leads_by_status()

            if not leads:
                logger.info("Sinxronizatsiya: CHECKING da buyurtmalar yo'q")
                # Telegramdagi eski xabarlarni o'chirish (fayldan yuklangan ID lar)
                if self.notification_manager and self.notification_manager._active_message_ids:
                    logger.info(f"Telegram: {len(self.notification_manager._active_message_ids)} ta eski xabarni o'chirish...")
                    await self.notification_manager.delete_all_notifications()
                    logger.info("Telegram: barcha eski xabarlar o'chirildi")
                else:
                    logger.info("Telegram: o'chiriladigan eski xabar topilmadi")
                self.state.reset()
                return

            count = len(leads)
            order_ids = [lead["id"] for lead in leads]

            logger.info(f"Sinxronizatsiya: {count} ta buyurtma topildi")

            # Holatni tiklash
            self.state.pending_orders_count = count
            self.state.pending_order_ids = order_ids

            # Eng eski buyurtmaning vaqtini topish (created_at dan)
            oldest_time = datetime.now()
            for lead in leads:
                created_at = lead.get("created_at")
                if created_at:
                    from datetime import timezone
                    try:
                        lead_time = datetime.fromisoformat(created_at.replace("Z", "+00:00")).replace(tzinfo=None)
                    except (ValueError, AttributeError):
                        lead_time = datetime.now()
                    if lead_time < oldest_time:
                        oldest_time = lead_time

            self.state.last_new_order_time = oldest_time
            self.state.waiting_for_call = True
            self.state.call_started = True  # Qo'ng'iroq qilmaslik uchun

            # Buyurtmalar uchun timestamp qo'shish (180s timer uchun)
            for lead in leads:
                order_id = lead["id"]
                if order_id not in self.state.order_timestamps:
                    created_at = lead.get("created_at")
                    if created_at:
                        try:
                            self.state.order_timestamps[order_id] = datetime.fromisoformat(created_at.replace("Z", "+00:00")).replace(tzinfo=None)
                        except (ValueError, AttributeError):
                            self.state.order_timestamps[order_id] = datetime.now()
                    else:
                        self.state.order_timestamps[order_id] = datetime.now()

            # 180s timer avtomatik ishlaydi - Telegram xabar 180s dan keyin yuboriladi

            # MUHIM: Agar Telegram xabarlari mavjud bo'lsa, telegram_notified = True qilish
            # Bu autodialer qayta ishga tushganda kerak - oldingi Telegram xabarlari saqlanadi
            if self.notification_manager.has_active_notification:
                self.state.telegram_notified = True
                logger.info(f"Sinxronizatsiya: Telegram xabarlari mavjud, telegram_notified = True")

            logger.info(f"Sinxronizatsiya tugadi: {count} ta buyurtma, 180s timer kuzatmoqda")

        except Exception as e:
            logger.error(f"Sinxronizatsiya xatosi: {e}")


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
        now = datetime.now()

        # 90s TIMER: Qo'ng'iroq qilish
        if self.state.waiting_for_call and self.state.last_new_order_time:
            elapsed = (now - self.state.last_new_order_time).total_seconds()

            # Qo'ng'iroq qilish vaqti (faqat bir marta chaqiriladi - ichida barcha urinishlar)
            if elapsed >= self.wait_before_call and not self.state.call_started:
                self.state.call_started = True
                await self._make_call()

        # 180s TIMER: Telegram yuborish - waiting_for_call ga BOG'LIQ EMAS
        # MUHIM: Har 10 sekundda bir marta tekshirish (spam bo'lmaslik uchun)
        if len(self.state.order_timestamps) > 0:
            # Oxirgi tekshiruvdan 10 sekund o'tdimi?
            should_check = False
            if self.state.last_180s_check_time is None:
                should_check = True
            else:
                time_since_last_check = (now - self.state.last_180s_check_time).total_seconds()
                if time_since_last_check >= 10:
                    should_check = True

            if should_check:
                self.state.last_180s_check_time = now

                # Eng eski buyurtmaning vaqtini topish
                oldest_order_time = min(self.state.order_timestamps.values())
                time_since_oldest = (now - oldest_order_time).total_seconds()

                # Agar eng eski buyurtma telegram_alert_time+ bo'lsa
                if time_since_oldest >= self.telegram_alert_time:
                    # Tekshirish: telegram_alert_time+ buyurtmalar bor va ular hali yuborilmagan
                    old_order_ids = []
                    for order_id, timestamp in self.state.order_timestamps.items():
                        if (now - timestamp).total_seconds() >= self.telegram_alert_time:
                            old_order_ids.append(order_id)

                    # Agar 180s+ buyurtmalar bor
                    if old_order_ids:
                        current_old_ids = set(old_order_ids)
                        # MUHIM FIX: Yangi 180s+ buyurtmalar bormi tekshirish
                        # (ya'ni hali Telegram'da yo'q buyurtmalar)
                        new_old_ids = current_old_ids - self.state.last_telegram_order_ids
                        if new_old_ids:
                            logger.info(f"{self.telegram_alert_time}s timer: {len(new_old_ids)} ta YANGI buyurtma {self.telegram_alert_time}s+ eski, Telegram yuborilmoqda")
                            await self._send_telegram_for_remaining()

    async def _update_group_messages(self, new_order_ids: set = None):
        """
        Biriktirilgan guruhlarga har bir buyurtma uchun alohida xabar yuborish/yangilash.
        new_order_ids: yangi kelgan buyurtma ID lari (faqat ular uchun xabar yuboriladi)
        """
        try:
            orders = await self.nonbor.get_orders()
            if not orders:
                return

            # Biznes title -> ID mapping (businesses cache dan)
            title_to_id = {}
            for bid, bdata in self.nonbor._businesses_cache.items():
                title = bdata.get("title", "").strip().lower()
                if title:
                    title_to_id[title] = str(bid)

            # Agar cache bo'sh bo'lsa, API dan yuklash
            if not title_to_id:
                await self.nonbor.get_businesses()
                for bid, bdata in self.nonbor._businesses_cache.items():
                    title = bdata.get("title", "").strip().lower()
                    if title:
                        title_to_id[title] = str(bid)

            for order in orders:
                order_id = order.get("id")
                business = order.get("business") or {}

                # Business ID ni aniqlash: avval to'g'ridan-to'g'ri, keyin title orqali
                biz_id = str(business.get("id", ""))
                if not biz_id:
                    biz_title = business.get("title", "").strip().lower()
                    biz_id = title_to_id.get(biz_title, "")

                if not biz_id or biz_id not in self.stats_handler._business_groups:
                    continue

                group_chat_id = self.stats_handler._business_groups[biz_id]
                status = order.get("state", "CHECKING").upper()

                # Buyurtma ma'lumotlarini tayyorlash
                user = order.get("user") or {}
                items = order.get("order_item") or order.get("items") or []
                delivery = order.get("delivery") or {}
                client_name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip() or "Noma'lum"
                product_name = ""
                quantity = 1
                if items:
                    first_item = items[0]
                    product = first_item.get("product") or {}
                    product_name = product.get("title", "") or product.get("name", "")
                    quantity = first_item.get("count", 1) or first_item.get("quantity", 1)

                # Telefon raqami - user, delivery yoki boshqa maydonlardan
                client_phone = user.get("phone") or user.get("phone_number") or delivery.get("phone") or delivery.get("phone_number") or ""

                order_data = {
                    "order_number": str(order_id),
                    "status": status,
                    "client_name": client_name,
                    "client_phone": client_phone,
                    "product_name": product_name,
                    "quantity": quantity,
                    "price": (order.get("total_price", 0) or 0) / 100,
                }

                if order_id in self._group_order_messages:
                    # Mavjud xabar - status o'zgargan bo'lsa yangilash
                    tracked = self._group_order_messages[order_id]
                    if tracked.get("status") != status:
                        success = await self.telegram.update_business_order_message(
                            message_id=tracked["msg_id"],
                            order_data=order_data,
                            chat_id=group_chat_id
                        )
                        if success:
                            tracked["status"] = status
                            logger.info(f"Guruh: buyurtma #{order_id} status yangilandi: {status}")
                else:
                    # Yangi buyurtma - faqat new_order_ids da bo'lsa xabar yuborish
                    if new_order_ids and order_id in new_order_ids:
                        msg_id = await self.telegram.send_business_order_message(
                            order_data=order_data, chat_id=group_chat_id
                        )
                        if msg_id:
                            self._group_order_messages[order_id] = {
                                "msg_id": msg_id,
                                "biz_id": biz_id,
                                "chat_id": group_chat_id,
                                "status": status,
                                "order_data": order_data,
                            }
                            logger.info(f"Guruhga xabar yuborildi: buyurtma #{order_id}, status: {status}")

        except Exception as e:
            logger.error(f"Guruh xabarlarini yangilashda xato: {e}")

    async def _on_new_orders(self, count: int, new_ids: list):
        """Yangi buyurtmalar callback"""
        logger.info(f"Yangi buyurtmalar: {len(new_ids)} ta, Jami: {count} ta")

        # Holatni yangilash
        old_count = self.state.pending_orders_count
        old_ids = set(self.state.pending_order_ids)
        new_order_ids = set(new_ids)

        # MUHIM: Allaqachon qo'ng'iroq qilingan/xabar berilgan buyurtmalarni topish
        all_communicated_ids = set()
        for seller_phone, communicated_ids in self.state.last_communicated_orders.items():
            all_communicated_ids.update(communicated_ids)

        # MUHIM: Faqat YANGI (hali xabar berilmagan) buyurtmalarni aniqlash
        # 1. Haqiqatan yangi kelgan buyurtmalar (ilgari yo'q edi)
        truly_new_ids = new_order_ids - old_ids

        # 2. Barcha hozirgi buyurtmalardan allaqachon xabar berilganlarni olib tashlash
        uncommunicated_ids = new_order_ids - all_communicated_ids

        if len(all_communicated_ids) > 0:
            logger.debug(f"Allaqachon xabar berilgan: {len(new_order_ids & all_communicated_ids)} ta buyurtma")

        # MUHIM: Agar BARCHA buyurtmalar allaqachon xabar berilgan bo'lsa, ularni e'tiborsiz qoldiramiz
        # Bu buyurtmalar allaqachon qo'ng'iroq qilingan/Telegram yuborilgan
        if len(uncommunicated_ids) == 0 and count > 0:
            logger.info(f"Barcha {count} ta buyurtma haqida allaqachon xabar berilgan, yangi qo'ng'iroq kerak emas")
            # Holatni yangilash (faqat pending_order_ids)
            self.state.pending_order_ids = new_ids
            self.state.pending_orders_count = count
            # MUHIM: waiting_for_call ni False qoldiramiz, chunki qo'ng'iroq kerak emas
            # Agar waiting_for_call allaqachon True bo'lsa, uni False qilamiz
            if self.state.waiting_for_call:
                self.state.waiting_for_call = False
                logger.debug("waiting_for_call = False (barcha buyurtmalar xabar berilgan)")
            # MUHIM: order_timestamps ni O'CHIRMAYMIZ!
            # Chunki Telegram hali yuborilmagan bo'lishi mumkin (180s kutish kerak)
            # Faqat qo'ng'iroq qilingan, lekin Telegram hali kutilmoqda
            # order_timestamps faqat _on_orders_resolved() da o'chiriladi
            # yoki _send_telegram_for_remaining() dan keyin o'chiriladi
            # Agar order_timestamps bo'sh bo'lsa, last_180s_check_time ni ham reset qilamiz
            if len(self.state.order_timestamps) == 0:
                self.state.last_180s_check_time = None
                logger.debug("order_timestamps bo'sh, 180s timer to'xtatildi")
            # MUHIM: return qilamiz - bu buyurtmalar uchun hech narsa qilmaymiz
            return

        self.state.new_order_received(count, new_ids)

        now = datetime.now()

        # MUHIM: BARCHA yangi buyurtmalar uchun timestamp qo'yish (180s timer uchun)
        # Bu birinchi marta kelgan buyurtmalar uchun ham, keyingi buyurtmalar uchun ham ishlaydi
        if len(truly_new_ids) > 0:
            for new_id in truly_new_ids:
                if new_id not in self.state.order_timestamps:
                    self.state.order_timestamps[new_id] = now
                    logger.debug(f"Buyurtma #{new_id} uchun timestamp qo'yildi: {now}")

        # Agar yangi buyurtma qo'shilgan bo'lsa
        if len(truly_new_ids) > 0:
            if old_count > 0:
                logger.info(f"YANGI buyurtma qo'shildi: {len(truly_new_ids)} ta, Jami: {old_count} -> {count}")
            else:
                logger.info(f"Birinchi buyurtmalar keldi: {len(truly_new_ids)} ta")

            # Yangi buyurtmalarni to'plash listiga qo'shish
            for new_id in truly_new_ids:
                if new_id not in self.state.new_order_ids_for_call:
                    self.state.new_order_ids_for_call.append(new_id)

            logger.info(f"To'planayotgan yangi buyurtmalar: {len(self.state.new_order_ids_for_call)} ta")

            # DARHOL: Biriktirilgan guruhga har bir yangi buyurtma uchun alohida xabar
            if self.stats_handler and hasattr(self.stats_handler, '_business_groups') and self.stats_handler._business_groups:
                await self._update_group_messages(new_order_ids=truly_new_ids)

            # 1. MUHIM: Yangi buyurtma kelganda Telegram xabar DARHOL yangilanmaydi
            # Har bir buyurtma uchun 180s kutish kerak - _check_and_process() da 180s timer ishlaydi
            logger.info(f"Yangi buyurtmalar uchun 180s timer boshlandi: {len(truly_new_ids)} ta buyurtma")

            # 2. Timer/qo'ng'iroq holati bo'yicha harakat
            if self.state.call_in_progress:
                # Qo'ng'iroq jarayonida - yangi buyurtmalar KEYINGI qo'ng'iroqqa qoladi
                logger.info(f"Qo'ng'iroq jarayonida, yangi buyurtmalar keyingi qo'ng'iroq uchun to'planmoqda: {len(truly_new_ids)} ta")
            elif not self.state.call_started:
                if not self.state.waiting_for_call:
                    # Timer hali boshlanmagan - yangi timer boshlash
                    logger.info(f"Yangi buyurtmalar uchun 90s timer boshlandi")
                    logger.info(f"90 soniyadan keyin BARCHA yangi buyurtmalar uchun BITTA qo'ng'iroq")
                    self.state.last_new_order_time = now
                    self.state.waiting_for_call = True
                    self.state.call_started = False
                else:
                    # Timer allaqachon ishlayapti - buyurtma to'plamga qo'shiladi (timer QAYTA BOSHLANMAYDI)
                    logger.info(f"90s timer ishlayapti, yangi buyurtma to'plamga qo'shildi (Jami: {len(self.state.new_order_ids_for_call)} ta)")

        elif old_count > 0:
            logger.debug(f"Buyurtmalar soni yangilandi: {old_count} -> {count}")

        # TOZALASH: pending_order_ids da yo'q bo'lgan buyurtmalarni order_timestamps dan o'chirish
        # Bu buyurtmalar boshqa statusga o'tgan yoki o'chirilgan
        removed_ids = []
        for order_id in list(self.state.order_timestamps.keys()):
            if order_id not in new_order_ids:
                del self.state.order_timestamps[order_id]
                removed_ids.append(order_id)
                logger.debug(f"Buyurtma #{order_id} TEKSHIRILMOQDA statusidan chiqdi, vaqt yozuvlari o'chirildi")

        # TOZALASH: TEKSHIRILMOQDA statusidan chiqqan buyurtmalarni last_communicated_orders dan ham o'chirish
        # Aks holda ular hali TEKSHIRILMOQDA da bo'lganda ham "allaqachon xabar berilgan" deb hisoblanadi
        for seller_phone in list(self.state.last_communicated_orders.keys()):
            # Bu sotuvchining buyurtmalarini tekshirish
            seller_order_ids = self.state.last_communicated_orders[seller_phone]
            # Faqat hali TEKSHIRILMOQDA da bo'lgan buyurtmalarni qoldirish
            still_pending = [oid for oid in seller_order_ids if oid in new_order_ids]
            if len(still_pending) > 0:
                self.state.last_communicated_orders[seller_phone] = still_pending
            else:
                # Bu sotuvchining barcha buyurtmalari hal qilindi - sotuvchini o'chirish
                del self.state.last_communicated_orders[seller_phone]
                logger.debug(f"Sotuvchi {seller_phone}: barcha buyurtmalari hal qilindi, tozalandi")

        # TELEGRAM YANGILASH: Agar birinchi Telegram xabar allaqachon yuborilgan bo'lsa,
        # buyurtmalar o'zgarganda faqat 180s+ eski buyurtmalarni yangilash
        if self.state.telegram_notified and (len(truly_new_ids) > 0 or len(removed_ids) > 0):
            if len(truly_new_ids) > 0:
                logger.info(f"Telegram yangilanmoqda: {len(truly_new_ids)} ta yangi buyurtma qo'shildi")
            if len(removed_ids) > 0:
                logger.info(f"Telegram yangilanmoqda: {len(removed_ids)} ta buyurtma hal qilindi")
            await self._send_telegram_for_remaining()
        elif len(truly_new_ids) > 0:
            # Birinchi Telegram hali yuborilmagan - 180s kutish kerak
            logger.info(f"Yangi buyurtmalar: {len(truly_new_ids)} ta, 180s kutilmoqda (birinchi Telegram hali yuborilmagan)")
        elif len(removed_ids) > 0:
            logger.info(f"Hal qilingan buyurtmalar: {len(removed_ids)} ta")
        else:
            logger.debug(f"O'zgarish yo'q")

    async def _on_orders_resolved(self, resolved_ids: list, remaining_count: int):
        """Buyurtmalar tekshirildi callback"""
        resolved_count = len(resolved_ids)
        logger.info(f"Tekshirildi: {resolved_count} ta, Qoldi: {remaining_count} ta")

        # Qabul qilingan buyurtmalarni statistikaga yozish
        # (Telegram yuborilgan yoki yuborilmaganini aniqlash)
        telegram_was_sent = self.state.telegram_notified

        # Qaysi sotuvchilar uchun o'zgarish bo'lganini aniqlash
        affected_sellers = set()

        # Har bir hal qilingan buyurtma uchun statistika
        resolved_order_ids = resolved_ids
        for order_id in resolved_order_ids:
            # Agar bu buyurtma allaqachon qayd etilgan bo'lsa, o'tkazib yuborish
            if self._recorded_orders.contains(order_id):
                logger.debug(f"Buyurtma #{order_id} allaqachon qayd etilgan, o'tkazib yuborilmoqda")
                continue

            try:
                order_data = await self.nonbor.get_order_full_data(order_id)
                seller_phone = order_data.get("seller_phone", "Noma'lum")
                affected_sellers.add(seller_phone)

                self.stats.record_order(
                    order_id=order_id,
                    order_number=order_data.get("order_number", str(order_id)),
                    seller_name=order_data.get("seller_name", "Noma'lum"),
                    seller_phone=seller_phone,
                    client_name=order_data.get("client_name", "Noma'lum"),
                    product_name=order_data.get("product_name", "Noma'lum"),
                    price=order_data.get("price", 0),
                    result=OrderResult.ACCEPTED,
                    call_attempts=self.state.call_attempts,
                    telegram_sent=telegram_was_sent
                )
                self._recorded_orders.add(order_id)
                logger.info(f"Buyurtma #{order_id} statistikaga yozildi (Kesh hajmi: {self._recorded_orders.size()})")
            except Exception as e:
                logger.error(f"Buyurtma #{order_id} statistika yozishda xato: {e}")

        # Tekshirilgan buyurtmalarni order_timestamps dan o'chirish
        for order_id in resolved_order_ids:
            if order_id in self.state.order_timestamps:
                del self.state.order_timestamps[order_id]
                logger.debug(f"Buyurtma #{order_id} vaqt yozuvlari o'chirildi")

        # Tekshirilgan buyurtmalarni last_telegram_order_ids dan ham o'chirish
        for order_id in resolved_order_ids:
            if order_id in self.state.last_telegram_order_ids:
                self.state.last_telegram_order_ids.discard(order_id)
                logger.debug(f"Buyurtma #{order_id} Telegram tracking dan o'chirildi")

        # Tekshirilgan buyurtmalarni last_communicated_orders dan ham o'chirish
        # (agar buyurtma tekshirilgan bo'lsa, uni qayta xabar berish kerak emas)
        for seller_phone in list(self.state.last_communicated_orders.keys()):
            # Tekshirilgan buyurtmalarni olib tashlash
            original_count = len(self.state.last_communicated_orders[seller_phone])
            self.state.last_communicated_orders[seller_phone] = [
                oid for oid in self.state.last_communicated_orders[seller_phone]
                if oid not in resolved_order_ids
            ]
            removed_count = original_count - len(self.state.last_communicated_orders[seller_phone])
            if removed_count > 0:
                logger.debug(f"Sotuvchi {seller_phone}: {removed_count} ta tekshirilgan buyurtma tracking dan o'chirildi")

            # Agar sotuvchining hech qanday buyurtmasi qolmagan bo'lsa, uni ham o'chirish
            if len(self.state.last_communicated_orders[seller_phone]) == 0:
                del self.state.last_communicated_orders[seller_phone]
                logger.debug(f"Sotuvchi {seller_phone} tracking dan butunlay o'chirildi (buyurtmalar qolmagan)")

        # Agar hammasi tekshirilgan bo'lsa
        if remaining_count == 0:
            logger.info("Barcha buyurtmalar tekshirildi!")
            # TEKSHIRILMOQDA statusida buyurtmalar qolmasa Telegram xabar o'chiriladi
            await self._delete_telegram_messages()
            # Telegram buyurtmalar ro'yxatini tozalash
            self.state.last_telegram_order_ids = set()
            self.state.reset()
        else:
            # Qolgan buyurtmalar - holatni yangilash va Telegram ni yangilash
            self.state.pending_orders_count = remaining_count
            # Resolved ID larni pending dan o'chirish
            self.state.pending_order_ids = [
                oid for oid in self.state.pending_order_ids
                if oid not in resolved_order_ids
            ]
            logger.info(f"Qolgan {remaining_count} ta buyurtma, Telegram yangilanmoqda")

            # Buyurtma hal qilinganda Telegram yangilanadi (faqat 180s+ eski buyurtmalar)
            if self.state.telegram_notified:
                logger.info(f"Telegram xabar yangilanmoqda: {remaining_count} ta buyurtma qoldi")
                await self._send_telegram_for_remaining()

        # Guruh xabarlarini tozalash (buyurtma hal bo'lganda)
        for order_id in resolved_order_ids:
            if order_id in self._group_order_messages:
                del self._group_order_messages[order_id]

    async def _make_call(self):
        """Har bir sotuvchiga alohida qo'ng'iroq qilish"""
        # Qo'ng'iroq jarayonini boshlash - yangi buyurtmalar keyingi qo'ng'iroqqa qoladi
        self.state.call_in_progress = True

        # 90s da: FAQAT TELEFON (Telegram 180s da yuboriladi)

        # QO'NG'IROQ VAQTIDAGI BARCHA buyurtmalarni olish (90s davomida to'plangan)
        # Bu yerda pending_order_ids ni ishlatamiz - bu hozirgi holatdagi BARCHA buyurtmalar
        order_ids = list(self.state.pending_order_ids)
        logger.info(f"QO'NG'IROQ vaqtida: {len(order_ids)} ta buyurtma (90s davomida to'plangan)")

        # MUHIM: Qo'ng'iroq qilishdan oldin statusni tekshirish
        # Buyurtmalar qabul qilingan bo'lishi mumkin (TEKSHIRILMOQDA dan chiqgan)
        current_leads = await self.nonbor.get_leads_by_status()
        if current_leads is None:
            current_leads = []
        current_lead_ids = {lead["id"] for lead in current_leads}

        logger.info(f"Nonbor API dan hozirgi CHECKING statusidagi buyurtmalar: {len(current_lead_ids)} ta")

        # Faqat hali TEKSHIRILMOQDA statusida bo'lgan buyurtmalar uchun qo'ng'iroq qilish
        order_ids = [oid for oid in order_ids if oid in current_lead_ids]

        if len(order_ids) < len(self.state.pending_order_ids):
            removed_count = len(self.state.pending_order_ids) - len(order_ids)
            logger.info(f"Qo'ng'iroq qilishdan oldin {removed_count} ta buyurtma qabul qilindi, ular o'tkazib yuboriladi")

        if not order_ids:
            logger.info("Barcha buyurtmalar allaqachon qabul qilindi, qo'ng'iroq qilish kerak emas")
            self.state.call_in_progress = False
            # Pending buyurtmalarni yangilash - ular qabul qilindi
            self.state.pending_order_ids = []
            self.state.pending_orders_count = 0
            return

        # Barcha buyurtmalarni olish va sotuvchi bo'yicha guruhlash
        sellers = {}
        for order_id in order_ids:
            try:
                order_data = await self.nonbor.get_order_full_data(order_id)
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

                # MUHIM: Agar bu buyurtma haqida sotuvchiga allaqachon xabar berilgan bo'lsa, uni o'tkazib yuboramiz
                if seller_phone in self.state.last_communicated_orders:
                    if order_id in self.state.last_communicated_orders[seller_phone]:
                        logger.debug(f"Buyurtma #{order_id} sotuvchi {seller_phone} ga allaqachon xabar berilgan, o'tkazib yuborildi")
                        continue

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
            logger.info("Barcha buyurtmalar haqida allaqachon xabar berilgan, qo'ng'iroq qilish kerak emas")
            # Qo'ng'iroq jarayonini tugatish
            self.state.call_in_progress = False
            # State ni tozalash (last_communicated_orders saqlanadi)
            self.state.reset()
            return

        # Har bir sotuvchiga KETMA-KET qo'ng'iroq qilish
        # MUHIM: Birinchisi javob bersa, qolganlariga qo'ng'iroq qilinmaydi
        total_attempts = 0
        call_answered = False  # Hech kim javob berganini belgilash

        for seller_phone, seller_data in sellers.items():
            # MUHIM: Agar kimdir javob bergan bo'lsa, qolganlariga qo'ng'iroq qilmaslik
            if call_answered:
                logger.info(f"Bitta qo'ng'iroq javob berilgan, qolgan sotuvchilar o'tkazib yuborildi")
                break

            order_count = len(seller_data["orders"])
            seller_name = seller_data["seller_name"]

            # Agar bu sotuvchining barcha buyurtmalari allaqachon xabar berilgan bo'lsa, o'tkazib yuborish
            if order_count == 0:
                logger.debug(f"Sotuvchi {seller_name} ({seller_phone}) uchun yangi buyurtmalar yo'q, o'tkazib yuborildi")
                continue

            logger.info(f"Qo'ng'iroq: {seller_name} ({seller_phone}), {order_count} ta YANGI buyurtma")

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
            # MUHIM: Qo'ng'iroq qilingan (javob berilgan yoki berilmagan) buyurtmalarni belgilash
            # Bu buyurtmalar uchun QAYTA qo'ng'iroq qilinmaydi
            if seller_phone not in self.state.last_communicated_orders:
                self.state.last_communicated_orders[seller_phone] = []

            # Yangi buyurtmalarni qo'shish (dublikatlarni oldini olish)
            existing_ids = set(self.state.last_communicated_orders[seller_phone])
            new_ids = [oid for oid in order_ids_for_call if oid not in existing_ids]
            self.state.last_communicated_orders[seller_phone].extend(new_ids)

            logger.info(f"Sotuvchi {seller_name} ga {len(order_ids_for_call)} ta buyurtma uchun qo'ng'iroq qilindi (jami belgilangan: {len(self.state.last_communicated_orders[seller_phone])} ta)")

            if result.is_answered:
                logger.info(f"Qo'ng'iroq muvaffaqiyatli: {seller_name} ({seller_phone})")
                call_answered = True  # Javob berildi - qolgan qo'ng'iroqlarni bekor qilish

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
        # Qo'ng'iroq jarayonini tugatish
        self.state.call_in_progress = False

        # Yangi buyurtma qo'ng'iroqlari listini tozalash
        self.state.new_order_ids_for_call = []

        # MUHIM: Hozir BARCHA buyurtmalar allaqachon xabar berilgan yoki javob berilmagan urinishlar tugagan
        # Tekshirish: hali xabar berilmagan buyurtmalar bormi?
        uncommunicated_count = 0
        all_communicated_ids = set()
        for seller_phone, communicated_ids in self.state.last_communicated_orders.items():
            all_communicated_ids.update(communicated_ids)

        for order_id in self.state.pending_order_ids:
            if order_id not in all_communicated_ids:
                uncommunicated_count += 1

        # Qo'ng'iroq tugadi - javob berilgan yoki berilmagan, state ni tozalash
        # MUHIM: call_attempts ni saqlash (180s Telegram uchun kerak)
        self._last_call_attempts = max(self.state.call_attempts, total_attempts, 1) if call_answered else total_attempts

        if total_attempts == 0:
            logger.info("Barcha qo'ng'iroqlar muvaffaqiyatli, state tozalanmoqda")
            # Telegram xabarlarni HECH QACHON O'CHIRMAYMIZ - ular doim qoladi
            # await self._delete_telegram_messages()  # DISABLED - xabarlar qoladi
            logger.info("Telegram xabarlar saqlanadi (o'chirilmaydi)")
            # To'liq reset - javob berilgan, qayta qo'ng'iroq kerak emas
            self.state.reset()
        elif uncommunicated_count == 0:
            # BARCHA buyurtmalar haqida xabar berilgan (javob berilgan yoki berilmagan)
            # Qayta urinish kerak emas
            logger.info(f"Barcha {len(self.state.pending_order_ids)} ta buyurtma haqida xabar berilgan, qayta qo'ng'iroq KERAK EMAS")
            logger.info("180s timer davom etmoqda (Telegram uchun)")
            # State ni tozalash (lekin last_communicated_orders saqlanadi)
            self.state.reset()
        else:
            # Javob berilmadi - QAYTA QO'NG'IROQ QILINMAYDI
            # Faqat 2 marta qo'ng'iroq qilinadi, keyin to'xtaydi
            logger.warning(f"{total_attempts} ta qo'ng'iroqqa javob berilmadi, {uncommunicated_count} ta buyurtma uchun")
            logger.info("Qayta qo'ng'iroq qilinmaydi - 180s timer davom etmoqda (Telegram uchun)")
            # State ni tozalash
            self.state.reset()

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
                order_data = await self.nonbor.get_order_full_data(order_id)
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
                    self._last_call_attempts
                )
            except Exception as e:
                logger.error(f"Sotuvchi {seller_phone} xabar yuborishda xato: {e}")

    async def _delete_telegram_messages(self):
        """Telegram xabarlarni o'chirish"""
        if not self.notification_manager:
            return

        # Avval pending deletions ni qayta urinish
        await self.notification_manager.retry_pending_deletions()

        if self.notification_manager._active_message_ids:
            logger.info(f"Telegram xabarlarni o'chirish: {len(self.notification_manager._active_message_ids)} ta")
            failed_ids = []
            for msg_id in self.notification_manager._active_message_ids:
                try:
                    success = await self.telegram.delete_message(msg_id)
                    if success:
                        logger.debug(f"Xabar o'chirildi: {msg_id}")
                    else:
                        failed_ids.append(msg_id)
                        logger.warning(f"Xabar o'chirilmadi, pending ga qo'shilmoqda: {msg_id}")
                except Exception as e:
                    failed_ids.append(msg_id)
                    logger.error(f"Xabar o'chirishda xato {msg_id}: {e}")

            # Muvaffaqiyatsiz o'chirishlarni pending ga qo'shish
            if failed_ids:
                for msg_id in failed_ids:
                    if msg_id not in self.notification_manager._pending_deletions:
                        self.notification_manager._pending_deletions.append(msg_id)

            self.notification_manager._active_message_ids = []
            self.notification_manager._seller_message_ids = {}
            self.notification_manager._combined_message_id = None
            self.notification_manager._save_messages()

    async def _send_telegram_for_remaining(self, affected_sellers: set = None, force_all: bool = False):
        """
        Qolgan buyurtmalar uchun Telegram xabar yuborish
        affected_sellers - faqat o'zgargan sotuvchilar uchun xabar yangilash
        force_all - True bo'lsa, 180s filterni o'tkazib yuborish (barcha CHECKING buyurtmalar)

        MUHIM: force_all=False bo'lsa faqat 180 soniyadan oshgan buyurtmalarni Telegram ga yuborish
        """
        if not self.notification_manager:
            return

        # Avval pending deletions ni qayta urinish
        await self.notification_manager.retry_pending_deletions()

        # Hozirgi TEKSHIRILMOQDA dagi barcha buyurtmalarni olish
        leads = await self.nonbor.get_leads_by_status()
        if not leads:
            return

        order_ids = [lead["id"] for lead in leads]

        if force_all:
            # BARCHA CHECKING buyurtmalarni yuborish (180s filtersiz)
            old_order_ids = order_ids
        else:
            # Faqat 180 soniyadan oshgan buyurtmalarni filterlash
            now = datetime.now()
            old_order_ids = []
            for order_id in order_ids:
                if order_id in self.state.order_timestamps:
                    order_age = (now - self.state.order_timestamps[order_id]).total_seconds()
                    if order_age >= self.telegram_alert_time:  # telegram_alert_time soniyadan oshgan
                        old_order_ids.append(order_id)
                    else:
                        logger.debug(f"Buyurtma #{order_id} hali 180s dan yosh ({order_age:.0f}s), Telegram uchun kutilmoqda")
                else:
                    # Agar vaqt ma'lumoti yo'q bo'lsa, bu buyurtma yangi kelgan - 180s kutish kerak
                    logger.debug(f"Buyurtma #{order_id} uchun timestamp yo'q, Telegram yuborilmaydi (180s kutish kerak)")

        if not old_order_ids:
            logger.info(f"Telegram uchun buyurtmalar yo'q (barcha buyurtmalar 180s dan yangi)")
            return

        # MUHIM: Tekshirish - buyurtmalar ro'yxati o'zgardimi?
        # force_all=True bo'lsa, har doim yangilash (buyurtma qabul/bekor qilinganda)
        current_order_ids = set(old_order_ids)
        if not force_all and current_order_ids == self.state.last_telegram_order_ids:
            logger.info(f"Telegram yangilanmaydi - buyurtmalar o'zgarmagan ({len(old_order_ids)} ta)")
            return

        # Buyurtmalar ro'yxati o'zgardi - yangilash kerak
        added_orders = current_order_ids - self.state.last_telegram_order_ids
        removed_orders = self.state.last_telegram_order_ids - current_order_ids
        if added_orders:
            logger.info(f"Yangi buyurtmalar qo'shildi: {len(added_orders)} ta")
        if removed_orders:
            logger.info(f"Buyurtmalar hal qilindi: {len(removed_orders)} ta")

        logger.info(f"Qolgan buyurtmalar uchun Telegram: {len(old_order_ids)} ta (180s+ eski, jami: {len(order_ids)} ta)")

        # Barcha buyurtmalarni olish (faqat 180s+ eski)
        all_orders = []
        for order_id in old_order_ids:
            try:
                order_data = await self.nonbor.get_order_full_data(order_id)
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

        # MUHIM: Mavjud xabarlarni yangilash yoki yangi yuborish
        if not hasattr(self.notification_manager, '_combined_message_id'):
            self.notification_manager._combined_message_id = None

        existing_seller_msgs = dict(self.notification_manager._seller_message_ids) if self.notification_manager._seller_message_ids else {}

        # Endi ro'yxatda bo'lmagan sotuvchilarning xabarlarini o'chirish
        removed_sellers = set(existing_seller_msgs.keys()) - set(sellers.keys())
        for seller_phone in removed_sellers:
            msg_id = existing_seller_msgs[seller_phone]
            try:
                success = await self.telegram.delete_message(msg_id)
                if success:
                    if msg_id in self.notification_manager._active_message_ids:
                        self.notification_manager._active_message_ids.remove(msg_id)
                    logger.info(f"Sotuvchi xabari o'chirildi (buyurtma yo'q): {seller_phone} ({msg_id})")
                else:
                    if msg_id not in self.notification_manager._pending_deletions:
                        self.notification_manager._pending_deletions.append(msg_id)
            except Exception as e:
                if msg_id not in self.notification_manager._pending_deletions:
                    self.notification_manager._pending_deletions.append(msg_id)
                logger.error(f"Sotuvchi xabarini o'chirishda xato: {e}")
            del self.notification_manager._seller_message_ids[seller_phone]

        # Har bir sotuvchi uchun: mavjud xabarni YANGILASH yoki YANGI yuborish
        try:
            total_orders = sum(len(s["orders"]) for s in sellers.values())
            logger.info(f"Sotuvchilar xabarlarini yangilash: {len(sellers)} ta sotuvchi, {total_orders} ta buyurtma")

            for seller_phone, seller_data in sellers.items():
                if seller_phone in existing_seller_msgs:
                    # Mavjud xabarni TAHRIRLASH (faqat buyurtma soni o'zgaradi)
                    msg_id = existing_seller_msgs[seller_phone]
                    success = await self.telegram.update_seller_orders_alert(
                        message_id=msg_id,
                        seller_orders=seller_data,
                        call_attempts=self._last_call_attempts
                    )
                    if success:
                        logger.info(f"Sotuvchi xabari yangilandi: {seller_phone} ({msg_id}), buyurtmalar: {len(seller_data['orders'])}")
                    else:
                        # Edit ishlamadi - yangi xabar yuborish
                        logger.warning(f"Xabar tahrirlanmadi, yangi yuborilmoqda: {seller_phone}")
                        new_msg_id = await self.telegram.send_seller_orders_alert(
                            seller_data, self._last_call_attempts
                        )
                        if new_msg_id:
                            self.notification_manager._seller_message_ids[seller_phone] = new_msg_id
                            if new_msg_id not in self.notification_manager._active_message_ids:
                                self.notification_manager._active_message_ids.append(new_msg_id)
                else:
                    # YANGI sotuvchi - yangi xabar yuborish
                    new_msg_id = await self.telegram.send_seller_orders_alert(
                        seller_data, self._last_call_attempts
                    )
                    if new_msg_id:
                        self.notification_manager._seller_message_ids[seller_phone] = new_msg_id
                        if new_msg_id not in self.notification_manager._active_message_ids:
                            self.notification_manager._active_message_ids.append(new_msg_id)
                        logger.info(f"Yangi sotuvchi xabari: {seller_phone} ({new_msg_id})")

            # Combined message ID yangilash (birinchi sotuvchi xabari)
            if self.notification_manager._seller_message_ids:
                first_msg = list(self.notification_manager._seller_message_ids.values())[0]
                self.notification_manager._combined_message_id = first_msg

            self.notification_manager._save_messages()
            logger.info(f"Xabarlar yangilandi: {len(self.notification_manager._seller_message_ids)} ta sotuvchi")

        except Exception as e:
            logger.error(f"Sotuvchi xabarlarini yangilashda xato: {e}")

        # Oxirgi yuborilgan buyurtmalar ro'yxatini yangilash
        self.state.last_telegram_order_ids = current_order_ids
        self.state.telegram_notified = True  # Birinchi Telegram yuborildi - keyingi o'zgarishlarda darhol yangilanadi
        logger.debug(f"Oxirgi Telegram buyurtmalar ro'yxati yangilandi: {len(current_order_ids)} ta")

        # 180s timer davom etadi - buyurtmalar uchun
        logger.info("Telegram xabar yuborildi, 180s timer davom etmoqda")

    # DEPRECATED: _send_new_order_alert endi ishlatilmaydi
    # Yangi buyurtmalar uchun 180s timer kutiladi - _check_and_process() da
    # Eski kod saqlab qolindi - kelajakda kerak bo'lishi mumkin
    #
    # async def _send_new_order_alert(self, new_order_ids: list):
    #     """
    #     Yangi buyurtma kelganda TEKSHIRILMOQDA status xabarini yangilash
    #     ENDI ISHLATILMAYDI - 180s timer orqali yuboriladi
    #     """
    #     pass


async def main():
    """Asosiy funksiya"""

    autodialer = AutodialerPro(
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
