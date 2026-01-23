"""
Telegram Bot Servisi
Xabar yuborish va boshqarish
"""

import logging
import aiohttp
import asyncio
from typing import Optional, Dict, Any, List, Callable
from datetime import datetime

logger = logging.getLogger(__name__)


# Callback data prefixes
CALLBACK_STATS = "stats"
CALLBACK_CALLS_1 = "calls_1"
CALLBACK_CALLS_2 = "calls_2"
CALLBACK_CALLS_3 = "calls_3"
CALLBACK_ANSWERED = "answered"
CALLBACK_UNANSWERED = "unanswered"
CALLBACK_ACCEPTED = "accepted"
CALLBACK_REJECTED = "rejected"
CALLBACK_NO_TELEGRAM = "no_telegram"
CALLBACK_BACK = "back"

# Davr tugmalari
CALLBACK_DAILY = "period_daily"
CALLBACK_WEEKLY = "period_weekly"
CALLBACK_MONTHLY = "period_monthly"
CALLBACK_YEARLY = "period_yearly"


class TelegramService:
    """
    Telegram Bot servisi

    Funksiyalar:
    - Xabar yuborish
    - Xabarni tahrirlash
    - Xabarni o'chirish
    - Inline buttonlar
    """

    def __init__(self, bot_token: str, default_chat_id: str = None):
        self.bot_token = bot_token
        self.default_chat_id = default_chat_id
        self.base_url = f"https://api.telegram.org/bot{bot_token}"

        self._session: Optional[aiohttp.ClientSession] = None

        logger.info("Telegram servisi ishga tushdi")

    async def _get_session(self) -> aiohttp.ClientSession:
        """HTTP session olish"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self):
        """Sessionni yopish"""
        if self._session and not self._session.closed:
            await self._session.close()

    async def _make_request(
        self,
        method: str,
        data: dict = None
    ) -> Optional[Dict]:
        """Telegram API so'rov"""
        session = await self._get_session()
        url = f"{self.base_url}/{method}"

        try:
            async with session.post(url, json=data) as response:
                result = await response.json()

                if result.get("ok"):
                    return result.get("result")
                else:
                    logger.error(f"Telegram xatosi: {result.get('description')}")
                    return None

        except aiohttp.ClientError as e:
            logger.error(f"Telegram ulanish xatosi: {e}")
            return None

    async def send_message(
        self,
        text: str,
        chat_id: str = None,
        parse_mode: str = "Markdown",
        reply_markup: dict = None,
        disable_notification: bool = False
    ) -> Optional[int]:
        """
        Xabar yuborish

        Args:
            text: Xabar matni
            chat_id: Chat ID (default ishlatiladi agar berilmasa)
            parse_mode: Markdown yoki HTML
            reply_markup: Inline keyboard
            disable_notification: Ovossiz yuborish

        Returns:
            Message ID yoki None
        """
        chat_id = chat_id or self.default_chat_id

        if not chat_id:
            logger.error("Chat ID ko'rsatilmagan")
            return None

        data = {
            "chat_id": chat_id,
            "text": text,
            "disable_notification": disable_notification
        }

        if parse_mode:
            data["parse_mode"] = parse_mode

        if reply_markup:
            data["reply_markup"] = reply_markup

        result = await self._make_request("sendMessage", data)

        if result:
            message_id = result.get("message_id")
            logger.info(f"Telegram xabar yuborildi: {message_id}")
            return message_id

        return None

    async def edit_message(
        self,
        message_id: int,
        text: str,
        chat_id: str = None,
        parse_mode: str = "Markdown",
        reply_markup: dict = None
    ) -> bool:
        """
        Xabarni tahrirlash

        Args:
            message_id: Xabar ID
            text: Yangi matn
            chat_id: Chat ID

        Returns:
            Muvaffaqiyat holati
        """
        chat_id = chat_id or self.default_chat_id

        data = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
            "parse_mode": parse_mode
        }

        if reply_markup:
            data["reply_markup"] = reply_markup

        result = await self._make_request("editMessageText", data)

        if result:
            logger.info(f"Telegram xabar tahrirlandi: {message_id}")
            return True

        return False

    async def delete_message(
        self,
        message_id: int,
        chat_id: str = None
    ) -> bool:
        """
        Xabarni o'chirish

        Args:
            message_id: Xabar ID
            chat_id: Chat ID

        Returns:
            Muvaffaqiyat holati
        """
        chat_id = chat_id or self.default_chat_id

        data = {
            "chat_id": chat_id,
            "message_id": message_id
        }

        # To'g'ridan-to'g'ri API chaqirish
        session = await self._get_session()
        url = f"{self.base_url}/deleteMessage"

        try:
            async with session.post(url, json=data) as response:
                result = await response.json()
                logger.debug(f"Delete response: {result}")

                if result.get("ok"):
                    logger.info(f"Telegram xabar o'chirildi: {message_id}")
                    return True
                else:
                    error_desc = result.get('description', '')
                    # Agar xabar topilmasa - bu xato emas, oddiy debug log
                    if "message to delete not found" in error_desc.lower():
                        logger.debug(f"Telegram xabar {message_id} allaqachon o'chirilgan")
                        return True  # Bu success deb hisoblaymiz
                    else:
                        logger.error(f"Telegram o'chirish xatosi: {error_desc}")
                        return False

        except Exception as e:
            logger.error(f"Telegram delete xatosi: {e}")
            return False

    async def send_seller_orders_alert(
        self,
        seller_orders: dict,
        call_attempts: int = 0,
        chat_id: str = None
    ) -> Optional[int]:
        """
        Sotuvchi uchun buyurtmalar haqida ogohlantirish yuborish

        Args:
            seller_orders: {
                "seller_name": str,
                "seller_phone": str,
                "seller_address": str,
                "orders": list of order dicts
            }
            call_attempts: Qo'ng'iroq urinishlari
            chat_id: Chat ID

        Returns:
            Message ID
        """
        text = self._format_seller_orders_alert(seller_orders, call_attempts)

        return await self.send_message(
            text=text,
            chat_id=chat_id,
            parse_mode="HTML"  # HTML link ishlashi uchun
        )

    async def send_all_sellers_alert(
        self,
        sellers_data: dict,
        call_attempts: int = 0,
        chat_id: str = None
    ) -> tuple[Optional[int], dict]:
        """
        HAR BIR sotuvchi uchun ALOHIDA xabar yuborish

        Args:
            sellers_data: Dictionary of sellers {seller_phone: {seller_name, seller_phone, seller_address, orders}}
            call_attempts: Qo'ng'iroq urinishlari
            chat_id: Chat ID

        Returns:
            Tuple of (first_message_id, seller_message_ids dict)
        """
        first_message_id = None
        seller_message_ids = {}  # {seller_phone: message_id}

        # HAR BIR SOTUVCHI UCHUN ALOHIDA XABAR
        for seller_phone, seller_data in sellers_data.items():
            message_id = await self.send_seller_orders_alert(
                seller_data,
                call_attempts,
                chat_id
            )
            if message_id:
                seller_message_ids[seller_phone] = message_id
                if first_message_id is None:
                    first_message_id = message_id

            logger.info(f"Sotuvchi {seller_phone} uchun alohida xabar yuborildi: {message_id}")

        return first_message_id, seller_message_ids

    def _format_seller_orders_alert(self, seller_orders: dict, call_attempts: int = 0) -> str:
        """Sotuvchi buyurtmalari xabarini formatlash - HAR BIR SOTUVCHI UCHUN ALOHIDA"""
        seller_name = seller_orders.get("seller_name", "Noma'lum")
        seller_phone = seller_orders.get("seller_phone", "Noma'lum")
        # Sotuvchi telefon raqamiga + qo'shish
        if seller_phone and seller_phone != "Noma'lum" and not str(seller_phone).startswith('+'):
            seller_phone = '+' + str(seller_phone)
        seller_address = seller_orders.get("seller_address", "Noma'lum")
        orders = seller_orders.get("orders", [])
        orders_count = len(orders)

        # Umumiy narx
        total_price = sum(o.get("price", 0) or 0 for o in orders)
        total_price_str = f"{total_price:,.0f}".replace(",", " ") + " so'm"

        # Header
        text = f"""🚨 DIQQAT! {orders_count} ta buyurtma qabul qilinmadi!

SOTUVCHI:
  Nomi: {seller_name}
  Tel: {seller_phone}
  Manzil: {seller_address}

━━━ BUYURTMALAR ━━━
"""
        # Har bir buyurtma (mijoz)
        for i, order in enumerate(orders, 1):
            order_number = order.get("order_number", order.get("lead_id", "N/A"))
            client_name = order.get("client_name", "Noma'lum")
            client_phone = order.get("client_phone", "Noma'lum")
            # Mijoz telefon raqamiga + qo'shish
            if client_phone and client_phone != "Noma'lum" and not str(client_phone).startswith('+'):
                client_phone = '+' + str(client_phone)
            product_name = order.get("product_name", "Noma'lum")
            quantity = order.get("quantity", 1)
            price = order.get("price", 0)

            # Narxni formatlash
            if isinstance(price, (int, float)) and price:
                price_str = f"{price:,.0f}".replace(",", " ") + " so'm"
            else:
                price_str = "Noma'lum"

            text += f"""
{i}. Buyurtma #{order_number}
   Mijoz: {client_name}
   Tel: {client_phone}
   Mahsulot: {product_name}
   Miqdor: {quantity} ta
   Narx: {price_str}
"""

        # Footer
        text += f"""
━━━━━━━━━━━━━━━━━━━━━
📦 Jami: {orders_count} ta buyurtma
💰 Umumiy: {total_price_str}

❌ Buyurtmalarni qabul qilmayapti!
📞 {call_attempts} marta qo'ng'iroq qilindi.
🔴 Zudlik bilan bog'laning!

📱 <a href="https://welltech.amocrm.ru">Buyurtmalarni ko'rish</a>"""

        return text

    def _format_all_sellers_alert(self, sellers_data: dict, call_attempts: int = 0) -> str:
        """
        BARCHA sotuvchilar buyurtmalarini BITTA xabarda formatlash

        Args:
            sellers_data: Dictionary of sellers {seller_phone: {seller_name, seller_phone, seller_address, orders}}
            call_attempts: Qo'ng'iroq urinishlari soni

        Returns:
            Formatted text message
        """
        # Jami buyurtmalar va umumiy narxni hisoblash
        total_orders_count = 0
        total_price_all = 0

        for seller_data in sellers_data.values():
            orders = seller_data.get("orders", [])
            total_orders_count += len(orders)
            total_price_all += sum(o.get("price", 0) or 0 for o in orders)

        total_price_str = f"{total_price_all:,.0f}".replace(",", " ") + " so'm"

        # Header
        text = f"""🚨 DIQQAT! {total_orders_count} ta buyurtma qabul qilinmadi!
{len(sellers_data)} ta sotuvchida buyurtmalar kutmoqda.

"""

        # Har bir sotuvchi uchun alohida bo'lim
        for seller_idx, (seller_phone, seller_data) in enumerate(sellers_data.items(), 1):
            seller_name = seller_data.get("seller_name", "Noma'lum")
            seller_phone_display = seller_data.get("seller_phone", "Noma'lum")
            seller_address = seller_data.get("seller_address", "Noma'lum")
            orders = seller_data.get("orders", [])
            orders_count = len(orders)

            # Sotuvchi narxi
            seller_total_price = sum(o.get("price", 0) or 0 for o in orders)
            seller_price_str = f"{seller_total_price:,.0f}".replace(",", " ") + " so'm"

            # Sotuvchi header
            text += f"""━━━━━━━━━━━━━━━━━━━━
📍 SOTUVCHI #{seller_idx}
  Nomi: {seller_name}
  Tel: {seller_phone_display}
  Manzil: {seller_address}
  Buyurtmalar: {orders_count} ta

"""

            # Har bir buyurtma
            for i, order in enumerate(orders, 1):
                order_number = order.get("order_number", order.get("lead_id", "N/A"))
                client_name = order.get("client_name", "Noma'lum")
                client_phone = order.get("client_phone", "Noma'lum")
                product_name = order.get("product_name", "Noma'lum")
                quantity = order.get("quantity", 1)
                price = order.get("price", 0)

                # Narxni formatlash
                if isinstance(price, (int, float)) and price:
                    price_str = f"{price:,.0f}".replace(",", " ") + " so'm"
                else:
                    price_str = "Noma'lum"

                text += f"""  {i}. Buyurtma #{order_number}
     Mijoz: {client_name}
     Tel: {client_phone}
     Mahsulot: {product_name}
     Miqdor: {quantity} ta
     Narx: {price_str}

"""

            # Sotuvchi footer
            text += f"""  💰 Sotuvchi jami: {seller_price_str}

"""

        # Umumiy footer
        text += f"""━━━━━━━━━━━━━━━━━━━━
📦 JAMI: {total_orders_count} ta buyurtma
💰 UMUMIY: {total_price_str}

❌ Buyurtmalarni qabul qilmayapti!
📞 {call_attempts} marta qo'ng'iroq qilindi.
🔴 Zudlik bilan bog'laning!

📱 Buyurtmalarni ko'rish (https://welltech.amocrm.ru/leads/pipeline/10154618)"""

        return text

    async def send_resolved_message(
        self,
        resolved_count: int,
        remaining_count: int,
        chat_id: str = None
    ) -> Optional[int]:
        """
        Buyurtmalar tekshirildi xabari

        Args:
            resolved_count: Tekshirilgan soni
            remaining_count: Qolgan soni
            chat_id: Chat ID

        Returns:
            Message ID
        """
        now = datetime.now().strftime("%H:%M:%S")

        if remaining_count == 0:
            text = f"""
✅ *Barcha buyurtmalar tekshirildi!*

📦 Tekshirilgan: *{resolved_count}* ta
⏰ Vaqt: {now}
            """
        else:
            text = f"""
✅ *Buyurtmalar tekshirildi*

📦 Tekshirilgan: *{resolved_count}* ta
📦 Qolgan: *{remaining_count}* ta
⏰ Vaqt: {now}
            """

        return await self.send_message(text=text, chat_id=chat_id)

    async def update_order_alert(
        self,
        message_id: int,
        orders_count: int,
        call_attempts: int = 0,
        chat_id: str = None
    ) -> bool:
        """
        Buyurtma ogohlantirishini yangilash

        Args:
            message_id: Xabar ID
            orders_count: Yangi buyurtmalar soni
            call_attempts: Qo'ng'iroq urinishlari
            chat_id: Chat ID

        Returns:
            Muvaffaqiyat holati
        """
        now = datetime.now().strftime("%H:%M:%S")

        text = f"""
🔔 *Yangi buyurtmalar!*

📦 Buyurtmalar soni: *{orders_count}* ta
📞 Qo'ng'iroq urinishlari: {call_attempts}/3
⏰ Yangilangan: {now}
📋 Status: TEKSHIRILMOQDA

⚠️ Iltimos, tezroq tekshiring!
        """

        reply_markup = {
            "inline_keyboard": [
                [
                    {
                        "text": "📱 amoCRM ochish",
                        "url": "https://welltech.amocrm.ru"
                    }
                ]
            ]
        }

        return await self.edit_message(
            message_id=message_id,
            text=text,
            chat_id=chat_id,
            reply_markup=reply_markup
        )


class TelegramNotificationManager:
    """
    Telegram bildirishnoma boshqaruvchisi

    - Xabarlarni kuzatish
    - Auto-delete qilish
    - Dublikatlarni oldini olish
    """

    def __init__(self, telegram_service: TelegramService, data_dir: str = "data"):
        self.telegram = telegram_service
        self._active_message_ids: list = []  # Barcha yuborilgan xabarlar
        self._seller_message_ids: dict = {}  # Sotuvchi telefon -> xabar ID mapping
        self._pending_deletions: list = []  # O'chirilmagan xabarlar (retry uchun)
        self._last_count = 0
        self._message_sent_at: Optional[datetime] = None

        # Xabar ID larini saqlash uchun fayl
        from pathlib import Path
        import json
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self.messages_file = self.data_dir / "telegram_messages.json"
        self._load_messages()

    def _load_messages(self):
        """Saqlangan xabar ID larini yuklash"""
        if self.messages_file.exists():
            try:
                import json
                with open(self.messages_file, "r") as f:
                    data = json.load(f)
                    self._active_message_ids = data.get("message_ids", [])
                    self._seller_message_ids = data.get("seller_message_ids", {})
                    self._pending_deletions = data.get("pending_deletions", [])
                    # MUHIM: combined_message_id ni ham yuklash
                    self._combined_message_id = data.get("combined_message_id", None)

                    # Eski xabar ID larni tozalash - faqat seller_message_ids yoki combined_message_id da bor bo'lganlarni saqlash
                    valid_message_ids = set(self._seller_message_ids.values())
                    if self._combined_message_id:
                        valid_message_ids.add(self._combined_message_id)
                    old_count = len(self._active_message_ids)
                    self._active_message_ids = [msg_id for msg_id in self._active_message_ids if msg_id in valid_message_ids]

                    if old_count != len(self._active_message_ids):
                        logger.info(f"Eski xabar ID lar tozalandi: {old_count} -> {len(self._active_message_ids)}")
                        self._save_messages()  # Tozalangan listni saqlash

                    logger.info(f"Telegram xabar ID lar yuklandi: {len(self._active_message_ids)} ta, pending: {len(self._pending_deletions)} ta")
            except Exception as e:
                logger.error(f"Telegram xabar ID lar yuklashda xato: {e}")
                self._active_message_ids = []
                self._seller_message_ids = {}
                self._pending_deletions = []
                self._combined_message_id = None

    def _save_messages(self):
        """Xabar ID larni faylga saqlash"""
        try:
            import json
            # MUHIM: combined_message_id ni ham saqlash
            combined_id = getattr(self, '_combined_message_id', None)
            with open(self.messages_file, "w") as f:
                json.dump({
                    "message_ids": self._active_message_ids,
                    "seller_message_ids": self._seller_message_ids,
                    "combined_message_id": combined_id,
                    "pending_deletions": self._pending_deletions
                }, f, indent=2)
        except Exception as e:
            logger.error(f"Telegram xabar ID lar saqlashda xato: {e}")

    async def notify_seller_orders(
        self,
        seller_orders: dict,
        call_attempts: int = 0
    ):
        """
        Sotuvchi buyurtmalari haqida xabar

        Args:
            seller_orders: Sotuvchi va uning buyurtmalari
            call_attempts: Qo'ng'iroq urinishlari
        """
        # Yangi xabar yuborish
        message_id = await self.telegram.send_seller_orders_alert(seller_orders, call_attempts)
        if message_id:
            self._active_message_ids.append(message_id)
            self._message_sent_at = datetime.now()
            self._save_messages()  # Faylga saqlash

    async def notify_resolved(self, resolved_count: int, remaining_count: int):
        """
        Buyurtmalar tekshirildi xabari

        Agar hammasi tekshirilgan bo'lsa - barcha aktiv xabarlarni o'chiradi
        Agar o'chirish muvaffaqiyatsiz bo'lsa - pending_deletions ga qo'shadi
        """
        if remaining_count == 0 and self._active_message_ids:
            # Barcha aktiv xabarlarni o'chirish
            failed_ids = []
            for msg_id in self._active_message_ids:
                success = await self.telegram.delete_message(msg_id)
                if not success:
                    failed_ids.append(msg_id)
                    logger.warning(f"Xabar o'chirilmadi, pending ga qo'shildi: {msg_id}")

            # Muvaffaqiyatsiz o'chirishlarni pending ga qo'shish
            if failed_ids:
                for msg_id in failed_ids:
                    if msg_id not in self._pending_deletions:
                        self._pending_deletions.append(msg_id)
                logger.info(f"Pending deletions: {len(self._pending_deletions)} ta xabar")

            self._active_message_ids = []
            self._seller_message_ids = {}
            self._combined_message_id = None
            self._message_sent_at = None
            self._save_messages()

        self._last_count = remaining_count

    async def delete_all_notifications(self):
        """Barcha aktiv xabarlarni o'chirish"""
        failed_ids = []
        for msg_id in self._active_message_ids:
            success = await self.telegram.delete_message(msg_id)
            if not success:
                failed_ids.append(msg_id)

        if failed_ids:
            for msg_id in failed_ids:
                if msg_id not in self._pending_deletions:
                    self._pending_deletions.append(msg_id)
            logger.warning(f"O'chirilmagan xabarlar pending ga qo'shildi: {len(failed_ids)} ta")

        self._active_message_ids = []
        self._seller_message_ids = {}
        self._combined_message_id = None
        self._message_sent_at = None
        self._save_messages()

    async def retry_pending_deletions(self):
        """Pending deletions ro'yxatidagi xabarlarni qayta o'chirishga urinish"""
        if not self._pending_deletions:
            return

        logger.info(f"Pending deletions retry: {len(self._pending_deletions)} ta xabar")
        still_pending = []
        for msg_id in self._pending_deletions:
            success = await self.telegram.delete_message(msg_id)
            if not success:
                still_pending.append(msg_id)
            else:
                logger.info(f"Pending xabar muvaffaqiyatli o'chirildi: {msg_id}")

        self._pending_deletions = still_pending
        self._save_messages()

        if still_pending:
            logger.warning(f"Hali o'chirilmagan xabarlar: {len(still_pending)} ta")
        else:
            logger.info("Barcha pending xabarlar muvaffaqiyatli o'chirildi")

    def clear_notification(self):
        """Bildirishnoma holatini tozalash"""
        self._active_message_ids = []
        self._seller_message_ids = {}
        self._combined_message_id = None  # MUHIM: combined_message_id ni ham tozalash
        self._last_count = 0
        self._message_sent_at = None
        self._save_messages()  # Faylga saqlash

    @property
    def has_active_notification(self) -> bool:
        """Aktiv bildirishnoma bormi"""
        return len(self._active_message_ids) > 0


class TelegramStatsHandler:
    """
    Telegram statistika handleri

    Inline keyboard orqali statistika ko'rsatish va boshqarish
    """

    def __init__(self, telegram_service: TelegramService, stats_service=None):
        self.telegram = telegram_service
        self.stats_service = stats_service
        self._polling_task: Optional[asyncio.Task] = None
        self._running = False
        self._last_update_id = 0
        self._current_period = "daily"  # Joriy davr

    def set_stats_service(self, stats_service):
        """Stats servisini sozlash"""
        self.stats_service = stats_service

    async def start_polling(self):
        """Callback query polling boshlash"""
        if self._running:
            return

        self._running = True
        self._polling_task = asyncio.create_task(self._poll_updates())
        logger.info("Telegram stats polling boshlandi")

    async def stop_polling(self):
        """Polling to'xtatish"""
        self._running = False
        if self._polling_task:
            self._polling_task.cancel()
            try:
                await self._polling_task
            except asyncio.CancelledError:
                pass
        logger.info("Telegram stats polling to'xtatildi")

    async def _poll_updates(self):
        """Updates polling"""
        while self._running:
            try:
                updates = await self._get_updates()
                for update in updates:
                    await self._handle_update(update)
                await asyncio.sleep(1)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Polling xatosi: {e}")
                await asyncio.sleep(5)

    async def _get_updates(self) -> List[dict]:
        """Telegram updates olish"""
        session = await self.telegram._get_session()
        url = f"{self.telegram.base_url}/getUpdates"

        params = {
            "offset": self._last_update_id + 1,
            "timeout": 30,
            "allowed_updates": ["callback_query", "message"]
        }

        try:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=35)) as response:
                data = await response.json()
                if data.get("ok"):
                    updates = data.get("result", [])
                    if updates:
                        self._last_update_id = updates[-1]["update_id"]
                    return updates
        except asyncio.TimeoutError:
            pass
        except Exception as e:
            logger.error(f"getUpdates xatosi: {e}")

        return []

    async def _handle_update(self, update: dict):
        """Update ni qayta ishlash"""
        # /stats komandasi
        message = update.get("message")
        if message:
            text = message.get("text", "")
            chat_id = str(message.get("chat", {}).get("id", ""))

            if text == "/stats" or text.startswith("/stats@"):
                logger.info(f"/stats komandasi qabul qilindi: {chat_id}")
                await self.send_stats_message(chat_id)
            return

        # Callback query
        callback_query = update.get("callback_query")
        if not callback_query:
            return

        callback_id = callback_query.get("id")
        data = callback_query.get("data", "")
        callback_message = callback_query.get("message", {})
        message_id = callback_message.get("message_id")
        chat_id = str(callback_message.get("chat", {}).get("id", ""))

        logger.info(f"Callback query: {data}")

        # Answer callback
        await self._answer_callback(callback_id)

        # Handle callback
        if data == CALLBACK_BACK:
            await self._show_main_stats(message_id, chat_id)
        elif data == CALLBACK_CALLS_1:
            await self._show_calls_list(message_id, chat_id, 1)
        elif data == CALLBACK_CALLS_2:
            await self._show_calls_list(message_id, chat_id, 2)
        elif data == CALLBACK_CALLS_3:
            await self._show_calls_list(message_id, chat_id, 3)
        elif data == CALLBACK_ANSWERED:
            await self._show_answered_calls(message_id, chat_id)
        elif data == CALLBACK_UNANSWERED:
            await self._show_unanswered_calls(message_id, chat_id)
        elif data == CALLBACK_ACCEPTED:
            await self._show_orders_list(message_id, chat_id, "accepted")
        elif data == CALLBACK_REJECTED:
            await self._show_orders_list(message_id, chat_id, "rejected")
        elif data == CALLBACK_NO_TELEGRAM:
            await self._show_no_telegram_orders(message_id, chat_id)
        # Davr tugmalari
        elif data == CALLBACK_DAILY:
            self._current_period = "daily"
            await self._show_main_stats(message_id, chat_id)
        elif data == CALLBACK_WEEKLY:
            self._current_period = "weekly"
            await self._show_main_stats(message_id, chat_id)
        elif data == CALLBACK_MONTHLY:
            self._current_period = "monthly"
            await self._show_main_stats(message_id, chat_id)
        elif data == CALLBACK_YEARLY:
            self._current_period = "yearly"
            await self._show_main_stats(message_id, chat_id)

    async def _answer_callback(self, callback_id: str):
        """Callback query javob"""
        session = await self.telegram._get_session()
        url = f"{self.telegram.base_url}/answerCallbackQuery"

        try:
            await session.post(url, json={"callback_query_id": callback_id})
        except Exception as e:
            logger.error(f"answerCallbackQuery xatosi: {e}")

    def _get_period_title(self) -> str:
        """Davr sarlavhasini olish"""
        titles = {
            "daily": "BUGUNGI",
            "weekly": "HAFTALIK (7 kun)",
            "monthly": "OYLIK (30 kun)",
            "yearly": "YILLIK (365 kun)"
        }
        return titles.get(self._current_period, "BUGUNGI")

    async def send_stats_message(self, chat_id: str = None) -> Optional[int]:
        """Statistika xabarini yuborish"""
        if not self.stats_service:
            return None

        chat_id = chat_id or self.telegram.default_chat_id
        self._current_period = "daily"  # Har doim kunlik bilan boshlash
        stats = self.stats_service.get_period_stats(self._current_period)

        title = self._get_period_title()
        text = f"""📊 <b>{title} STATISTIKA</b>
━━━━━━━━━━━━━━━━━━━━

📞 <b>QO'NG'IROQLAR:</b> {stats.total_calls} ta
├ ✅ Javob berildi: {stats.answered_calls}
├ ❌ Javob berilmadi: {stats.unanswered_calls}
├ 1️⃣ 1-urinishda: {stats.calls_1_attempt}
└ 2️⃣ 2-urinishda: {stats.calls_2_attempts}

📦 <b>BUYURTMALAR:</b> {stats.total_orders} ta
├ ✅ Qabul qilindi: {stats.accepted_orders}
├ ❌ Bekor qilindi: {stats.rejected_orders}
└ 🚀 Telegram'siz qabul: {stats.accepted_without_telegram}

📅 Davr: {stats.date}

<i>Batafsil ko'rish uchun tugmalarni bosing:</i>"""

        keyboard = self._get_stats_keyboard(stats)

        return await self.telegram.send_message(
            text=text,
            chat_id=chat_id,
            parse_mode="HTML",
            reply_markup=keyboard
        )

    def _get_stats_keyboard(self, stats) -> dict:
        """Statistika inline keyboard"""
        # Davr tugmalari - tanlangan davr belgilanadi
        period_buttons = []
        periods = [
            ("📅 Kunlik", CALLBACK_DAILY, "daily"),
            ("📆 Haftalik", CALLBACK_WEEKLY, "weekly"),
            ("🗓 Oylik", CALLBACK_MONTHLY, "monthly"),
            ("📊 Yillik", CALLBACK_YEARLY, "yearly")
        ]
        for label, callback, period in periods:
            if period == self._current_period:
                period_buttons.append({"text": f"✓ {label}", "callback_data": callback})
            else:
                period_buttons.append({"text": label, "callback_data": callback})

        return {
            "inline_keyboard": [
                period_buttons[:2],  # Kunlik, Haftalik
                period_buttons[2:],  # Oylik, Yillik
                [
                    {"text": f"1️⃣ 1-urinish ({stats.calls_1_attempt})", "callback_data": CALLBACK_CALLS_1},
                    {"text": f"2️⃣ 2-urinish ({stats.calls_2_attempts})", "callback_data": CALLBACK_CALLS_2}
                ],
                [
                    {"text": f"✅ Javob ({stats.answered_calls})", "callback_data": CALLBACK_ANSWERED},
                    {"text": f"❌ Javobsiz ({stats.unanswered_calls})", "callback_data": CALLBACK_UNANSWERED}
                ],
                [
                    {"text": f"✅ Qabul ({stats.accepted_orders})", "callback_data": CALLBACK_ACCEPTED},
                    {"text": f"❌ Bekor ({stats.rejected_orders})", "callback_data": CALLBACK_REJECTED}
                ],
                [
                    {"text": f"🚀 Telegram'siz ({stats.accepted_without_telegram})", "callback_data": CALLBACK_NO_TELEGRAM}
                ]
            ]
        }

    async def _show_main_stats(self, message_id: int, chat_id: str):
        """Asosiy statistika sahifasiga qaytish"""
        if not self.stats_service:
            return

        stats = self.stats_service.get_period_stats(self._current_period)
        title = self._get_period_title()

        text = f"""📊 <b>{title} STATISTIKA</b>
━━━━━━━━━━━━━━━━━━━━

📞 <b>QO'NG'IROQLAR:</b> {stats.total_calls} ta
├ ✅ Javob berildi: {stats.answered_calls}
├ ❌ Javob berilmadi: {stats.unanswered_calls}
├ 1️⃣ 1-urinishda: {stats.calls_1_attempt}
└ 2️⃣ 2-urinishda: {stats.calls_2_attempts}

📦 <b>BUYURTMALAR:</b> {stats.total_orders} ta
├ ✅ Qabul qilindi: {stats.accepted_orders}
├ ❌ Bekor qilindi: {stats.rejected_orders}
└ 🚀 Telegram'siz qabul: {stats.accepted_without_telegram}

📅 Davr: {stats.date}

<i>Batafsil ko'rish uchun tugmalarni bosing:</i>"""

        keyboard = self._get_stats_keyboard(stats)

        await self.telegram.edit_message(
            message_id=message_id,
            text=text,
            chat_id=chat_id,
            parse_mode="HTML",
            reply_markup=keyboard
        )

    async def _show_calls_list(self, message_id: int, chat_id: str, attempts: int):
        """Berilgan urinishlar soni bo'yicha qo'ng'iroqlar ro'yxati"""
        if not self.stats_service:
            return

        calls = self.stats_service.get_period_calls_by_attempts(self._current_period, attempts)

        if not calls:
            text = f"""📞 <b>{attempts}-URINISHDA JAVOB BERILGAN QO'NG'IROQLAR</b>
━━━━━━━━━━━━━━━━━━━━

<i>Hozircha ma'lumot yo'q</i>"""
        else:
            text = f"""📞 <b>{attempts}-URINISHDA JAVOB BERILGAN QO'NG'IROQLAR</b>
━━━━━━━━━━━━━━━━━━━━

"""
            for i, call in enumerate(calls[-10:], 1):  # Oxirgi 10 ta
                time = call.timestamp.split("T")[1][:5]
                text += f"""{i}. <b>{call.seller_name}</b>
   📱 {call.phone}
   📦 {call.order_count} ta buyurtma
   ⏰ {time}

"""

        keyboard = {
            "inline_keyboard": [
                [{"text": "◀️ Orqaga", "callback_data": CALLBACK_BACK}]
            ]
        }

        await self.telegram.edit_message(
            message_id=message_id,
            text=text,
            chat_id=chat_id,
            parse_mode="HTML",
            reply_markup=keyboard
        )

    async def _show_answered_calls(self, message_id: int, chat_id: str):
        """Javob berilgan qo'ng'iroqlar"""
        if not self.stats_service:
            return

        stats = self.stats_service.get_period_stats(self._current_period)
        calls = [c for c in stats.call_records if c["result"] == "answered"]

        if not calls:
            text = """✅ <b>JAVOB BERILGAN QO'NG'IROQLAR</b>
━━━━━━━━━━━━━━━━━━━━

<i>Hozircha ma'lumot yo'q</i>"""
        else:
            text = f"""✅ <b>JAVOB BERILGAN QO'NG'IROQLAR</b> ({len(calls)} ta)
━━━━━━━━━━━━━━━━━━━━

"""
            for i, call in enumerate(calls[-10:], 1):
                time = call["timestamp"].split("T")[1][:5]
                text += f"""{i}. <b>{call["seller_name"]}</b>
   📱 {call["phone"]}
   📦 {call["order_count"]} ta | 🔄 {call["attempts"]} urinish
   ⏰ {time}

"""

        keyboard = {
            "inline_keyboard": [
                [{"text": "◀️ Orqaga", "callback_data": CALLBACK_BACK}]
            ]
        }

        await self.telegram.edit_message(
            message_id=message_id,
            text=text,
            chat_id=chat_id,
            parse_mode="HTML",
            reply_markup=keyboard
        )

    async def _show_unanswered_calls(self, message_id: int, chat_id: str):
        """Javob berilmagan qo'ng'iroqlar"""
        if not self.stats_service:
            return

        stats = self.stats_service.get_period_stats(self._current_period)
        calls = [c for c in stats.call_records if c["result"] != "answered"]

        if not calls:
            text = """❌ <b>JAVOB BERILMAGAN QO'NG'IROQLAR</b>
━━━━━━━━━━━━━━━━━━━━

<i>Hozircha ma'lumot yo'q</i>"""
        else:
            text = f"""❌ <b>JAVOB BERILMAGAN QO'NG'IROQLAR</b> ({len(calls)} ta)
━━━━━━━━━━━━━━━━━━━━

"""
            for i, call in enumerate(calls[-10:], 1):
                time = call["timestamp"].split("T")[1][:5]
                status = "❌ Javobsiz" if call["result"] == "no_answer" else "🔴 " + call["result"]
                text += f"""{i}. <b>{call["seller_name"]}</b>
   📱 {call["phone"]}
   📦 {call["order_count"]} ta | 🔄 {call["attempts"]} urinish
   {status}
   ⏰ {time}

"""

        keyboard = {
            "inline_keyboard": [
                [{"text": "◀️ Orqaga", "callback_data": CALLBACK_BACK}]
            ]
        }

        await self.telegram.edit_message(
            message_id=message_id,
            text=text,
            chat_id=chat_id,
            parse_mode="HTML",
            reply_markup=keyboard
        )

    async def _show_orders_list(self, message_id: int, chat_id: str, result: str):
        """Buyurtmalar ro'yxati"""
        if not self.stats_service:
            return

        from .stats_service import OrderResult
        order_result = OrderResult.ACCEPTED if result == "accepted" else OrderResult.REJECTED
        orders = self.stats_service.get_period_orders_by_result(self._current_period, order_result)

        title = "✅ QABUL QILINGAN" if result == "accepted" else "❌ BEKOR QILINGAN"

        if not orders:
            text = f"""<b>{title} BUYURTMALAR</b>
━━━━━━━━━━━━━━━━━━━━

<i>Hozircha ma'lumot yo'q</i>"""
        else:
            text = f"""<b>{title} BUYURTMALAR</b> ({len(orders)} ta)
━━━━━━━━━━━━━━━━━━━━

"""
            for i, order in enumerate(orders[-10:], 1):
                time = order.timestamp.split("T")[1][:5]
                price_str = f"{order.price:,.0f}".replace(",", " ") if order.price else "N/A"
                text += f"""{i}. <b>#{order.order_number}</b>
   👤 {order.client_name}
   📦 {order.product_name}
   💰 {price_str} so'm
   🏪 {order.seller_name}
   ⏰ {time}

"""

        keyboard = {
            "inline_keyboard": [
                [{"text": "◀️ Orqaga", "callback_data": CALLBACK_BACK}]
            ]
        }

        await self.telegram.edit_message(
            message_id=message_id,
            text=text,
            chat_id=chat_id,
            parse_mode="HTML",
            reply_markup=keyboard
        )

    async def _show_no_telegram_orders(self, message_id: int, chat_id: str):
        """Telegram yuborilmasdan qabul qilingan buyurtmalar"""
        if not self.stats_service:
            return

        orders = self.stats_service.get_period_orders_without_telegram(self._current_period)

        if not orders:
            text = """🚀 <b>TELEGRAM'SIZ QABUL QILINGAN</b>
━━━━━━━━━━━━━━━━━━━━

<i>Hozircha ma'lumot yo'q</i>

Bu buyurtmalar 3 daqiqa ichida (Telegram yuborilmasdan) qabul qilingan."""
        else:
            text = f"""🚀 <b>TELEGRAM'SIZ QABUL QILINGAN</b> ({len(orders)} ta)
━━━━━━━━━━━━━━━━━━━━

<i>Bu buyurtmalar 3 daqiqa ichida qabul qilingan</i>

"""
            for i, order in enumerate(orders[-10:], 1):
                time = order.timestamp.split("T")[1][:5]
                price_str = f"{order.price:,.0f}".replace(",", " ") if order.price else "N/A"
                text += f"""{i}. <b>#{order.order_number}</b>
   👤 {order.client_name}
   📦 {order.product_name}
   💰 {price_str} so'm
   🏪 {order.seller_name}
   📞 {order.call_attempts} marta qo'ng'iroq
   ⏰ {time}

"""

        keyboard = {
            "inline_keyboard": [
                [{"text": "◀️ Orqaga", "callback_data": CALLBACK_BACK}]
            ]
        }

        await self.telegram.edit_message(
            message_id=message_id,
            text=text,
            chat_id=chat_id,
            parse_mode="HTML",
            reply_markup=keyboard
        )
