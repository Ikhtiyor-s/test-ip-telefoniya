"""
Telegram Bot Servisi
Xabar yuborish va boshqarish
"""

import logging
import json
import os
import random
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
CALLBACK_CALLS_BACK = "calls_back"  # Qo'ng'iroqlar sub-sahifalaridan orqaga

# Menu tugmalari
CALLBACK_MENU_BUSINESSES = "menu_businesses"
CALLBACK_MENU_CALLS = "menu_calls"
CALLBACK_MENU_ORDERS = "menu_orders"
CALLBACK_MENU_BACK = "menu_back"
CALLBACK_BIZ_REFRESH = "biz_refresh"

# Bizneslar pagination va region tugmalari
CALLBACK_BIZ_PAGE = "biz_page_"       # biz_page_0, biz_page_1, ...
CALLBACK_BIZ_REGION = "biz_region_"   # biz_region_0, biz_region_1, ...
CALLBACK_BIZ_BACK = "biz_back"        # Regiondan orqaga
CALLBACK_BIZ_REG_PAGE = "biz_rp_"     # biz_rp_0_1 (region_idx_page)
CALLBACK_BIZ_DISTRICT = "biz_dist_"   # biz_dist_0_1 (region_idx_district_idx)
CALLBACK_BIZ_DIST_BACK = "biz_dback_" # biz_dback_0 (region_idx ga qaytish)
CALLBACK_BIZ_ITEM = "biz_item_"       # biz_item_5 (business id)
CALLBACK_BIZ_ADD_GROUP = "biz_grp_"   # biz_grp_5 (business id - guruh qo'shish)

# Davr tugmalari
CALLBACK_DAILY = "period_daily"
CALLBACK_WEEKLY = "period_weekly"
CALLBACK_MONTHLY = "period_monthly"
CALLBACK_YEARLY = "period_yearly"

# Owner orders (biznes egasi buyurtmalari)
CALLBACK_OWNER_ORDERS = "owner_orders"
CALLBACK_OWNER_BACK = "owner_back"
CALLBACK_OWNER_PERIOD = "oo_period_"    # oo_period_daily, oo_period_weekly, etc.
CALLBACK_OWNER_PAGE = "oo_page_"        # oo_page_0, oo_page_1, ...
CALLBACK_OWNER_STATUS = "oo_status_"    # oo_status_all, oo_status_accepted, oo_status_rejected

# Admin orders (admin buyurtmalar bo'limi)
CALLBACK_ADMIN_ORDERS_PAGE = "ao_page_"      # ao_page_0, ao_page_1, ...
CALLBACK_ADMIN_ORDERS_STATUS = "ao_status_"  # ao_status_all, ao_status_accepted, ao_status_rejected, ao_status_notg

# Auth states
AUTH_IDLE = "idle"
AUTH_AWAITING_PHONE = "awaiting_phone"
AUTH_AWAITING_OTP = "awaiting_otp"
AUTH_VERIFIED = "verified"

# Admin telefon raqamlari - barcha funksiyalarga to'liq kirish
ADMIN_PHONES = {
    "+998948679300",
    "+998773088888",
}


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

    async def update_seller_orders_alert(
        self,
        message_id: int,
        seller_orders: dict,
        call_attempts: int = 0,
        chat_id: str = None
    ) -> bool:
        """Mavjud sotuvchi xabarini tahrirlash (yangilash)"""
        text = self._format_seller_orders_alert(seller_orders, call_attempts)
        chat_id = chat_id or self.default_chat_id

        return await self.edit_message(
            message_id=message_id,
            text=text,
            chat_id=chat_id,
            parse_mode="HTML"
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

            # Tayyorlab berish vaqti (planned buyurtmalar uchun)
            delivery_time = order.get("delivery_time", "")

            text += f"""
{i}. Buyurtma #{order_number}
   Mijoz: {client_name}
   Tel: {client_phone}
   Mahsulot: {product_name}
   Miqdor: {quantity} ta
   Narx: {price_str}"""
            if delivery_time:
                text += f"\n   🕐 Tayyor bo'lish vaqti: {delivery_time}"
            text += "\n"

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

    STATUS_LABELS = {
        "CHECKING": "🟡 Tekshirilmoqda",
        "ACCEPTED": "🟢 Qabul qilindi",
        "READY": "✅ Tayyor",
        "PAYMENT_EXPIRED": "💳 To'lov muddati o'tdi",
        "ACCEPT_EXPIRED": "⏰ Qabul muddati o'tdi",
        "CANCELLED_CLIENT": "❌ Mijoz bekor qildi",
        "CANCELLED_SELLER": "🚫 Sotuvchi bekor qildi",
        "DELIVERING": "🚗 Yetkazilmoqda",
        "DELIVERED": "📦 Yetkazildi",
        "COMPLETED": "🏁 Yakunlandi",
        "CANCELLED": "❌ Bekor qilindi",
    }

    def _format_business_order_message(self, order_data: dict) -> str:
        """Biznes guruhi uchun bitta buyurtma xabari"""
        order_number = order_data.get("order_number", "")
        status = order_data.get("status", "CHECKING").upper()
        client_name = order_data.get("client_name", "Noma'lum")
        client_phone = order_data.get("client_phone", "")
        if client_phone and not str(client_phone).startswith('+'):
            client_phone = '+' + str(client_phone)
        product_name = order_data.get("product_name", "")
        quantity = order_data.get("quantity", 1)
        price = order_data.get("price", 0)
        price_str = f"{price:,.0f}".replace(",", " ") + " so'm" if price else "—"

        # Yetkazib berish ma'lumotlari
        delivery_address = order_data.get("delivery_address", "")
        delivery_lat = order_data.get("delivery_lat", "")
        delivery_lon = order_data.get("delivery_lon", "")
        delivery_time = order_data.get("delivery_time", "")

        # Status label
        status_label = self.STATUS_LABELS.get(status, f"📋 {status}")

        text = f"📦 Buyurtma #{order_number}\n"
        text += f"━━━━━━━━━━━━━━━━━━━\n"
        text += f"📊 Status: {status_label}\n"

        # Tayyorlab berish vaqti - har doim ko'rsatish
        if delivery_time:
            text += f"🕐 Tayyorlab berish vaqti: {delivery_time}\n"

        # TAYYOR va yetkazish bosqichlarida mijoz ma'lumotlarini ko'rsatish
        if status in ["READY", "DELIVERING", "DELIVERED", "COMPLETED"]:
            if client_name and client_name != "Noma'lum":
                text += f"👤 Mijoz: {client_name}\n"
            if client_phone:
                text += f"📞 Tel: {client_phone}\n"
            if delivery_address:
                text += f"📍 Manzil: {delivery_address}\n"
            if delivery_lat and delivery_lon:
                text += f"🗺 Lokatsiya: https://maps.google.com/?q={delivery_lat},{delivery_lon}\n"

        if product_name:
            text += f"🏷 Mahsulot: {product_name}\n"
            text += f"📦 Miqdor: {quantity} ta\n"
        text += f"💰 Narx: {price_str}"

        return text

    async def send_business_order_message(self, order_data: dict, chat_id: str) -> Optional[int]:
        """Biznes guruhiga bitta buyurtma xabari yuborish"""
        text = self._format_business_order_message(order_data)
        return await self.send_message(text=text, chat_id=chat_id)

    async def update_business_order_message(self, message_id: int, order_data: dict, chat_id: str) -> bool:
        """Biznes guruhidagi buyurtma xabarini yangilash (status o'zgarganda)"""
        text = self._format_business_order_message(order_data)
        return await self.edit_message(message_id=message_id, text=text, chat_id=chat_id)

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

    def __init__(self, telegram_service: TelegramService, stats_service=None, nonbor_service=None):
        self.telegram = telegram_service
        self.stats_service = stats_service
        self.nonbor_service = nonbor_service
        self._polling_task: Optional[asyncio.Task] = None
        self._running = False
        self._last_update_id = 0
        self._current_period = "daily"  # Joriy davr

        # Biznes guruh qo'shish uchun state
        self._awaiting_group_input: Dict[str, int] = {}  # chat_id -> business_id
        self._awaiting_message_id: Dict[str, int] = {}   # chat_id -> message_id

        # Guruhlar faylini yuklash
        self._groups_file = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data", "business_groups.json"
        )
        self._business_groups: Dict[str, str] = self._load_groups()

        # Auth tizimi
        self._auth_states: Dict[str, str] = {}          # chat_id -> state
        self._auth_phones: Dict[str, str] = {}          # chat_id -> phone (vaqtinchalik)
        self._auth_otps: Dict[str, dict] = {}           # chat_id -> {code, expires, phone, business_id}
        self._verified_users: Dict[str, dict] = {}      # chat_id -> {phone, business_id, business_title}
        self._phone_to_chat: Dict[str, str] = {}        # phone -> chat_id
        self._auth_file = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data", "auth_users.json"
        )
        self._load_auth_users()

        # Owner orders view state (har bir chat uchun alohida)
        self._owner_orders_period: Dict[str, str] = {}    # chat_id -> period (daily/weekly/monthly/yearly)
        self._owner_orders_page: Dict[str, int] = {}      # chat_id -> page (0-indexed)
        self._owner_orders_status: Dict[str, str] = {}    # chat_id -> status filter (all/accepted/rejected)

        # Admin orders view state
        self._admin_orders_page: Dict[str, int] = {}      # chat_id -> page (0-indexed)
        self._admin_orders_status: Dict[str, str] = {}    # chat_id -> status filter (all/accepted/rejected/notg)

    def set_stats_service(self, stats_service):
        """Stats servisini sozlash"""
        self.stats_service = stats_service

    def set_nonbor_service(self, nonbor_service):
        """Nonbor servisini sozlash"""
        self.nonbor_service = nonbor_service

    def _load_groups(self) -> Dict[str, str]:
        """Guruhlar faylidan yuklash"""
        try:
            if os.path.exists(self._groups_file):
                with open(self._groups_file, "r") as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Guruhlar faylini yuklash xatosi: {e}")
        return {}

    def _save_groups(self):
        """Guruhlarni faylga saqlash"""
        try:
            os.makedirs(os.path.dirname(self._groups_file), exist_ok=True)
            with open(self._groups_file, "w") as f:
                json.dump(self._business_groups, f, indent=2)
        except Exception as e:
            logger.error(f"Guruhlar faylini saqlash xatosi: {e}")

    # ===== AUTH METODLAR =====

    def _load_auth_users(self):
        """Auth faylidan yuklash"""
        try:
            if os.path.exists(self._auth_file):
                with open(self._auth_file, "r") as f:
                    data = json.load(f)
                    self._verified_users = data.get("verified_users", {})
                    self._phone_to_chat = data.get("phone_to_chat", {})
                    for chat_id in self._verified_users:
                        self._auth_states[chat_id] = AUTH_VERIFIED
                    logger.info(f"Auth yuklandi: {len(self._verified_users)} ta tasdiqlangan foydalanuvchi")
        except Exception as e:
            logger.error(f"Auth faylini yuklash xatosi: {e}")

    def _save_auth_users(self):
        """Auth faylga saqlash"""
        try:
            os.makedirs(os.path.dirname(self._auth_file), exist_ok=True)
            with open(self._auth_file, "w") as f:
                json.dump({
                    "verified_users": self._verified_users,
                    "phone_to_chat": self._phone_to_chat
                }, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Auth faylini saqlash xatosi: {e}")

    def _is_authenticated(self, chat_id: str) -> bool:
        """Foydalanuvchi tasdiqlangan mi? Biznes guruhlari ham ruxsat oladi."""
        if self._auth_states.get(chat_id) == AUTH_VERIFIED:
            return True
        # Biznesga biriktirilgan guruhlar avtomatik ruxsat oladi
        if chat_id in self._business_groups.values():
            return True
        return False

    def _is_admin(self, chat_id: str) -> bool:
        """Foydalanuvchi admin mi? (ADMIN_PHONES ro'yxatida)"""
        user_data = self._verified_users.get(chat_id)
        if not user_data:
            return False
        return user_data.get("phone") in ADMIN_PHONES

    def _get_user_business_id(self, chat_id: str) -> Optional[int]:
        """Foydalanuvchining business_id sini olish"""
        user_data = self._verified_users.get(chat_id)
        if not user_data:
            return None
        return user_data.get("business_id")

    def _generate_otp(self, chat_id: str, phone: str, business_id=None, business_title="") -> str:
        """4-raqamli OTP yaratish (5 daqiqa amal qiladi)"""
        code = str(random.randint(1000, 9999))
        self._auth_otps[chat_id] = {
            "code": code,
            "phone": phone,
            "expires": datetime.now().timestamp() + 300,
            "business_id": business_id,
            "business_title": business_title
        }
        return code

    def _verify_otp(self, chat_id: str, entered_code: str) -> str:
        """OTP tekshirish. Returns: 'valid', 'invalid', 'expired'"""
        otp_data = self._auth_otps.get(chat_id)
        if not otp_data:
            return "expired"
        if datetime.now().timestamp() > otp_data["expires"]:
            self._auth_otps.pop(chat_id, None)
            return "expired"
        if otp_data["code"] == entered_code.strip():
            return "valid"
        return "invalid"

    async def _find_business_by_phone(self, phone: str) -> Optional[Dict]:
        """Telefon raqam bo'yicha biznesni topish"""
        if not self.nonbor_service:
            return None
        businesses = await self.nonbor_service.get_businesses()
        if not businesses:
            return None

        # Raqamni normalizatsiya qilish
        normalized = phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
        if normalized.startswith("+"):
            without_plus = normalized[1:]
        else:
            without_plus = normalized
            normalized = "+" + normalized

        for biz in businesses:
            biz_phone = (biz.get("phone_number") or "").replace(" ", "").replace("-", "")
            if not biz_phone:
                continue
            biz_without_plus = biz_phone.lstrip("+")
            if without_plus == biz_without_plus:
                return biz
        return None

    async def _start_auth_flow(self, chat_id: str):
        """Auth jarayonini boshlash"""
        self._auth_states[chat_id] = AUTH_AWAITING_PHONE
        await self.telegram.send_message(
            text=(
                "📋 <b>Nonbor Buyurtmalar Bot</b>\n\n"
                "Buyurtmalar haqida xabar va statistika.\n\n"
                "<b>Kirish:</b>\n"
                "1. business.nonbor.uz da ro'yxatdan o'ting\n"
                "2. Ro'yxatdagi raqamni quyida yozing\n"
                "3. Tasdiqlash kodini kiriting\n\n"
                "<b>Guruhga ulash (ixtiyoriy):</b>\n"
                "1. Guruh yarating va @Nonborbuyurtmalar_bot ni admin qiling\n"
                "2. @userinfobot ga guruhdan xabar forward qiling — ID olasiz\n"
                "3. Botda \"Bizneslar\" → biznesingiz → \"Guruh ID\" → ID kiriting\n\n"
                "━━━━━━━━━━━━━━━━━━━\n"
                "📱 <b>Telefon raqamingizni kiriting:</b>\n"
                "<i>Masalan: +998901234567</i>"
            ),
            chat_id=chat_id,
            parse_mode="HTML"
        )

    async def _handle_phone_input(self, chat_id: str, phone: str):
        """Telefon raqamni tekshirish va OTP yuborish"""
        # Raqamni normalizatsiya (avval qilish kerak - admin tekshirish uchun)
        normalized = phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
        if not normalized.startswith("+"):
            normalized = "+" + normalized

        # Admin raqammi tekshirish - biznes tekshiruvisiz
        is_admin_phone = normalized in ADMIN_PHONES

        if is_admin_phone:
            # Admin uchun biznes tekshiruv shart emas
            business = {"id": None, "title": "🔐 Admin"}
        else:
            # Oddiy foydalanuvchi - biznesni topish
            business = await self._find_business_by_phone(phone)
            if not business:
                await self.telegram.send_message(
                    text=(
                        "❌ <b>Raqam topilmadi</b>\n\n"
                        "Bu raqam tizimda ro'yxatdan o'tmagan.\n"
                        "📱 Boshqa raqam kiriting:"
                    ),
                    chat_id=chat_id,
                    parse_mode="HTML"
                )
                return

        # Boshqa foydalanuvchi allaqachon shu raqamni tasdiqlaganmi?
        existing_chat = self._phone_to_chat.get(normalized)
        if existing_chat and existing_chat != chat_id:
            # Asl egasi uchun OTP yaratish
            self._auth_phones[existing_chat] = normalized
            self._auth_states[existing_chat] = AUTH_AWAITING_OTP
            otp_code = self._generate_otp(
                existing_chat, normalized,
                business_id=business.get("id"),
                business_title=business.get("title", "")
            )
            # Asl egasiga ogohlantirish + OTP yuborish
            await self.telegram.send_message(
                text=(
                    "⚠️ <b>OGOHLANTIRISH!</b>\n\n"
                    "Kimdir sizning biznes raqamingiz bilan "
                    "botga kirishga harakat qilmoqda!\n\n"
                    f"📱 Raqam: <code>{normalized}</code>\n"
                    f"🕐 Vaqt: {datetime.now().strftime('%H:%M:%S %d.%m.%Y')}\n\n"
                    f"🔑 <b>Tasdiqlash kodi:</b> <code>{otp_code}</code>\n"
                    f"<i>Siz ekanligingizni tasdiqlash uchun kodni kiriting:</i>"
                ),
                chat_id=existing_chat,
                parse_mode="HTML"
            )
            # Hozirgi foydalanuvchiga rad javob
            await self.telegram.send_message(
                text=(
                    "🚫 <b>Kirish rad etildi</b>\n\n"
                    "Bu raqam boshqa akkauntda tasdiqlangan.\n"
                    "📱 Boshqa raqam kiriting:"
                ),
                chat_id=chat_id,
                parse_mode="HTML"
            )
            return

        # OTP yaratish va yuborish
        self._auth_phones[chat_id] = normalized
        self._auth_states[chat_id] = AUTH_AWAITING_OTP
        otp_code = self._generate_otp(
            chat_id, normalized,
            business_id=business.get("id"),
            business_title=business.get("title", "")
        )

        if is_admin_phone:
            await self.telegram.send_message(
                text=(
                    f"🔐 <b>Admin raqami aniqlandi</b>\n\n"
                    f"🔑 Tasdiqlash kodi: <code>{otp_code}</code>\n\n"
                    f"<i>Kodni kiriting (5 daqiqa amal qiladi):</i>"
                ),
                chat_id=chat_id,
                parse_mode="HTML"
            )
        else:
            await self.telegram.send_message(
                text=(
                    f"✅ <b>Biznes topildi:</b> {business.get('title', '')}\n\n"
                    f"🔑 Tasdiqlash kodi: <code>{otp_code}</code>\n\n"
                    f"<i>Kodni kiriting (5 daqiqa amal qiladi):</i>"
                ),
                chat_id=chat_id,
                parse_mode="HTML"
            )

    async def _handle_otp_input(self, chat_id: str, code: str):
        """OTP tasdiqlash"""
        result = self._verify_otp(chat_id, code)

        if result == "expired":
            self._auth_states[chat_id] = AUTH_IDLE
            self._auth_phones.pop(chat_id, None)
            await self.telegram.send_message(
                text=(
                    "⏰ <b>Kod muddati tugadi</b>\n\n"
                    "Qaytadan /start bosing."
                ),
                chat_id=chat_id,
                parse_mode="HTML"
            )
            return

        if result == "invalid":
            await self.telegram.send_message(
                text="❌ Kod noto'g'ri. Qayta kiriting:",
                chat_id=chat_id,
                parse_mode="HTML"
            )
            return

        # Tasdiqlandi
        otp_data = self._auth_otps.pop(chat_id, {})
        phone = otp_data.get("phone", self._auth_phones.get(chat_id, ""))
        business_id = otp_data.get("business_id")
        business_title = otp_data.get("business_title", "")

        self._auth_states[chat_id] = AUTH_VERIFIED
        self._verified_users[chat_id] = {
            "phone": phone,
            "business_id": business_id,
            "business_title": business_title,
            "verified_at": datetime.now().isoformat()
        }
        self._phone_to_chat[phone] = chat_id
        self._save_auth_users()
        self._auth_phones.pop(chat_id, None)

        await self.telegram.send_message(
            text=f"✅ <b>Muvaffaqiyatli!</b>\n\nXush kelibsiz, {business_title}!",
            chat_id=chat_id,
            parse_mode="HTML"
        )
        await self.send_stats_message(chat_id)

    # ===== AUTH METODLAR TUGADI =====

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
        # Text xabarlar (auth bilan)
        message = update.get("message")
        if message:
            text = message.get("text", "")
            chat_id = str(message.get("chat", {}).get("id", ""))
            chat_type = message.get("chat", {}).get("type", "private")

            # Guruh chatlarida hech qanday komandaga javob bermaslik
            if chat_type in ("group", "supergroup"):
                return

            # /start - har doim ishlaydi
            if text == "/start" or text.startswith("/start@"):
                logger.info(f"/start komandasi: {chat_id}")
                if self._is_authenticated(chat_id):
                    await self.send_stats_message(chat_id)
                else:
                    await self._start_auth_flow(chat_id)
                return

            # Auth flow - telefon kiritish
            auth_state = self._auth_states.get(chat_id, AUTH_IDLE)
            if auth_state == AUTH_AWAITING_PHONE and text:
                await self._handle_phone_input(chat_id, text)
                return

            # Auth flow - OTP kiritish
            if auth_state == AUTH_AWAITING_OTP and text:
                await self._handle_otp_input(chat_id, text)
                return

            # === Quyidagi barcha funksiyalar faqat tasdiqlangan foydalanuvchilar uchun ===
            if not self._is_authenticated(chat_id):
                await self.telegram.send_message(
                    text="🔒 Avval /start bosib autentifikatsiyadan o'ting.",
                    chat_id=chat_id,
                    parse_mode="HTML"
                )
                return

            if text == "/stats" or text.startswith("/stats@"):
                logger.info(f"/stats komandasi: {chat_id}")
                await self.send_stats_message(chat_id)
                return

            # Guruh ID kiritish kutilmoqda
            if chat_id in self._awaiting_group_input and text:
                biz_id = self._awaiting_group_input.pop(chat_id)
                msg_id = self._awaiting_message_id.pop(chat_id, None)
                group_id = text.strip()
                # Guruh ID avtomatik tuzatish - minus qo'shish
                if group_id.isdigit():
                    group_id = "-" + group_id
                self._business_groups[str(biz_id)] = group_id
                self._save_groups()
                logger.info(f"Biznes #{biz_id} uchun guruh ID saqlandi: {group_id}")
                if msg_id:
                    await self._show_business_detail(msg_id, chat_id, biz_id)
                return
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

        # Auth tekshirish - tasdiqlanmagan foydalanuvchi tugma bosa olmaydi
        if not self._is_authenticated(chat_id):
            await self.telegram.send_message(
                text="🔒 Avval /start bosib autentifikatsiyadan o'ting.",
                chat_id=chat_id,
                parse_mode="HTML"
            )
            return

        # Handle callback
        if data == "noop":
            return

        # Admin bo'lmagan foydalanuvchilar faqat ruxsat berilgan tugmalarni bosa oladi
        if not self._is_admin(chat_id):
            if data.startswith(CALLBACK_BIZ_ADD_GROUP):
                # Guruh qo'shish
                pass
            elif data.startswith(CALLBACK_BIZ_ITEM):
                # Biznes ko'rish
                pass
            elif data == CALLBACK_OWNER_ORDERS or data == "owner_orders":
                # Buyurtmalar ro'yxati - state ni reset qilish
                self._owner_orders_period[chat_id] = "daily"
                self._owner_orders_page[chat_id] = 0
                self._owner_orders_status[chat_id] = "all"
                await self._show_owner_orders(message_id, chat_id)
                return
            elif data == CALLBACK_OWNER_BACK or data == "owner_back":
                # Asosiy menyuga qaytish
                await self._update_business_owner_message(message_id, chat_id)
                return
            elif data.startswith(CALLBACK_OWNER_PERIOD):
                # Davr o'zgartirish
                period = data.replace(CALLBACK_OWNER_PERIOD, "")
                self._owner_orders_page[chat_id] = 0  # Sahifani reset
                await self._show_owner_orders(message_id, chat_id, period=period)
                return
            elif data.startswith(CALLBACK_OWNER_PAGE):
                # Sahifa o'zgartirish
                try:
                    page = int(data.replace(CALLBACK_OWNER_PAGE, ""))
                    await self._show_owner_orders(message_id, chat_id, page=page)
                except ValueError:
                    pass
                return
            elif data.startswith(CALLBACK_OWNER_STATUS):
                # Status filter o'zgartirish
                status = data.replace(CALLBACK_OWNER_STATUS, "")
                self._owner_orders_page[chat_id] = 0  # Sahifani reset
                await self._show_owner_orders(message_id, chat_id, status_filter=status)
                return
            elif data == CALLBACK_BIZ_BACK or data == CALLBACK_MENU_BACK:
                # Orqaga - oddiy ko'rinishga qaytarish
                user_data = self._verified_users.get(chat_id, {})
                biz_id = user_data.get("business_id")
                if biz_id:
                    await self._show_business_detail(message_id, chat_id, biz_id)
                return
            else:
                # Boshqa barcha tugmalar bloklangan
                return

        if data == CALLBACK_BACK:
            await self._show_main_stats(message_id, chat_id)
        elif data == CALLBACK_CALLS_BACK:
            await self._show_all_calls(message_id, chat_id)
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
            self._admin_orders_page[chat_id] = 0
            await self._show_orders_menu(message_id, chat_id, status_filter="accepted")
        elif data == CALLBACK_REJECTED:
            self._admin_orders_page[chat_id] = 0
            await self._show_orders_menu(message_id, chat_id, status_filter="rejected")
        elif data == CALLBACK_NO_TELEGRAM:
            self._admin_orders_page[chat_id] = 0
            await self._show_orders_menu(message_id, chat_id, status_filter="notg")
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
        # Menu tugmalari
        elif data == CALLBACK_MENU_BUSINESSES or data == CALLBACK_BIZ_REFRESH:
            await self._show_businesses(message_id, chat_id)
        elif data == CALLBACK_MENU_CALLS:
            await self._show_all_calls(message_id, chat_id)
        elif data == CALLBACK_MENU_ORDERS:
            self._admin_orders_page[chat_id] = 0
            self._admin_orders_status[chat_id] = "all"
            await self._show_orders_menu(message_id, chat_id)
        elif data == CALLBACK_MENU_BACK:
            await self._show_main_stats(message_id, chat_id)
        # Admin orders pagination va status filter
        elif data.startswith(CALLBACK_ADMIN_ORDERS_PAGE):
            try:
                page = int(data.replace(CALLBACK_ADMIN_ORDERS_PAGE, ""))
                await self._show_orders_menu(message_id, chat_id, page=page)
            except ValueError:
                pass
        elif data.startswith(CALLBACK_ADMIN_ORDERS_STATUS):
            status = data.replace(CALLBACK_ADMIN_ORDERS_STATUS, "")
            self._admin_orders_page[chat_id] = 0  # Sahifani reset
            await self._show_orders_menu(message_id, chat_id, status_filter=status)
        # Bizneslar pagination va region
        elif data.startswith(CALLBACK_BIZ_PAGE):
            page = int(data.replace(CALLBACK_BIZ_PAGE, ""))
            await self._show_businesses(message_id, chat_id, page=page)
        elif data.startswith(CALLBACK_BIZ_REGION):
            region_idx = int(data.replace(CALLBACK_BIZ_REGION, ""))
            await self._show_region_districts(message_id, chat_id, region_idx)
        elif data.startswith(CALLBACK_BIZ_REG_PAGE):
            parts = data.replace(CALLBACK_BIZ_REG_PAGE, "").split("_")
            region_idx, page = int(parts[0]), int(parts[1])
            await self._show_region_districts(message_id, chat_id, region_idx, page=page)
        elif data.startswith(CALLBACK_BIZ_DISTRICT):
            parts = data.replace(CALLBACK_BIZ_DISTRICT, "").split("_")
            region_idx, district_idx = int(parts[0]), int(parts[1])
            await self._show_district_businesses(message_id, chat_id, region_idx, district_idx)
        elif data.startswith(CALLBACK_BIZ_DIST_BACK):
            region_idx = int(data.replace(CALLBACK_BIZ_DIST_BACK, ""))
            await self._show_region_districts(message_id, chat_id, region_idx)
        elif data.startswith(CALLBACK_BIZ_ITEM):
            biz_id = int(data.replace(CALLBACK_BIZ_ITEM, ""))
            await self._show_business_detail(message_id, chat_id, biz_id)
        elif data.startswith(CALLBACK_BIZ_ADD_GROUP):
            biz_id = int(data.replace(CALLBACK_BIZ_ADD_GROUP, ""))
            # Admin bo'lmagan foydalanuvchilar faqat o'z biznesiga guruh qo'sha oladi
            if not self._is_admin(chat_id):
                user_biz_id = self._get_user_business_id(chat_id)
                if user_biz_id != biz_id:
                    await self.telegram.edit_message(
                        message_id=message_id,
                        text="🚫 Bu biznesga guruh qo'shishga ruxsat yo'q",
                        chat_id=chat_id,
                        parse_mode="HTML",
                        reply_markup={"inline_keyboard": [[{"text": "◀️ Orqaga", "callback_data": CALLBACK_MENU_BACK}]]}
                    )
                    return
            self._awaiting_group_input[chat_id] = biz_id
            self._awaiting_message_id[chat_id] = message_id
            await self.telegram.edit_message(
                message_id=message_id,
                text="📝 <b>Guruh ID sini yuboring:</b>\n\nMasalan: <code>-1001234567890</code>",
                chat_id=chat_id,
                parse_mode="HTML",
                reply_markup={"inline_keyboard": [[
                    {"text": "❌ Bekor qilish", "callback_data": f"{CALLBACK_BIZ_ITEM}{biz_id}"}
                ]]}
            )
        elif data == CALLBACK_BIZ_BACK:
            await self._show_businesses(message_id, chat_id)
        elif data == CALLBACK_OWNER_ORDERS or data == "owner_orders":
            # Buyurtmalar ro'yxati - state ni reset qilish
            self._owner_orders_period[chat_id] = "daily"
            self._owner_orders_page[chat_id] = 0
            self._owner_orders_status[chat_id] = "all"
            await self._show_owner_orders(message_id, chat_id)
        elif data == CALLBACK_OWNER_BACK or data == "owner_back":
            await self._update_business_owner_message(message_id, chat_id)
        elif data.startswith(CALLBACK_OWNER_PERIOD):
            # Davr o'zgartirish
            period = data.replace(CALLBACK_OWNER_PERIOD, "")
            self._owner_orders_page[chat_id] = 0  # Sahifani reset
            await self._show_owner_orders(message_id, chat_id, period=period)
        elif data.startswith(CALLBACK_OWNER_PAGE):
            # Sahifa o'zgartirish
            try:
                page = int(data.replace(CALLBACK_OWNER_PAGE, ""))
                await self._show_owner_orders(message_id, chat_id, page=page)
            except ValueError:
                pass
        elif data.startswith(CALLBACK_OWNER_STATUS):
            # Status filter o'zgartirish
            status = data.replace(CALLBACK_OWNER_STATUS, "")
            self._owner_orders_page[chat_id] = 0  # Sahifani reset
            await self._show_owner_orders(message_id, chat_id, status_filter=status)

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

        # Admin bo'lmagan foydalanuvchilar uchun oddiy ko'rinish
        if not self._is_admin(chat_id):
            return await self._send_business_owner_message(chat_id)

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

    async def _send_business_owner_message(self, chat_id: str) -> Optional[int]:
        """Biznes egasi uchun oddiy ko'rinish - faqat buyurtmalar va guruh"""
        user_data = self._verified_users.get(chat_id, {})
        biz_id = user_data.get("business_id")
        biz_title = user_data.get("business_title", "Noma'lum")
        user_phone = user_data.get("phone", "")

        # Guruh holati
        group_id = self._business_groups.get(str(biz_id), "") if biz_id else ""

        # Buyurtmalar statistikasi (foydalanuvchi telefoni bo'yicha)
        orders_today = 0
        accepted_today = 0
        rejected_today = 0
        if self.stats_service and user_phone:
            stats = self.stats_service.get_period_stats("daily")
            for record in stats.order_records:
                if record.get("seller_phone") == user_phone:
                    orders_today += 1
                    if record.get("result") == "accepted":
                        accepted_today += 1
                    elif record.get("result") == "rejected":
                        rejected_today += 1

        text = f"🏪 <b>{biz_title}</b>\n"
        text += f"━━━━━━━━━━━━━━━━━━━━\n\n"
        text += f"📦 <b>Bugungi buyurtmalar:</b> {orders_today} ta\n"
        text += f"├ ✅ Qabul qilindi: {accepted_today}\n"
        text += f"└ ❌ Bekor qilindi: {rejected_today}\n\n"

        if group_id:
            text += f"👥 <b>Guruh:</b> Ulangan ✅\n"
        else:
            text += f"👥 <b>Guruh:</b> Ulanmagan ❌\n"
            text += f"<i>Guruh qo'shsangiz, buyurtmalar haqida xabar keladi</i>\n"

        # Keyboard - ikki qatorda, oxirgisi o'rtada
        keyboard_rows = []

        # 1-qator: Buyurtmalar | Biznes guruh
        row1 = [{"text": "📦 Buyurtmalar", "callback_data": "owner_orders"}]
        if biz_id:
            if group_id:
                row1.append({"text": "✏️ Biznes guruh", "callback_data": f"{CALLBACK_BIZ_ADD_GROUP}{biz_id}"})
            else:
                row1.append({"text": "➕ Biznes guruh", "callback_data": f"{CALLBACK_BIZ_ADD_GROUP}{biz_id}"})
        keyboard_rows.append(row1)

        # 2-qator: Buyurtma berish | Biznesim (web app)
        keyboard_rows.append([
            {"text": "🛒 Buyurtma berish", "web_app": {"url": "https://nonbor.uz"}},
            {"text": "🏪 Biznesim", "web_app": {"url": "https://business.nonbor.uz"}}
        ])

        # 3-qator: Qo'llab quvvatlash (o'rtada)
        keyboard_rows.append([
            {"text": "🆘 Qo'llab quvvatlash", "url": "https://t.me/NonborSupportBot"}
        ])

        return await self.telegram.send_message(
            text=text,
            chat_id=chat_id,
            parse_mode="HTML",
            reply_markup={"inline_keyboard": keyboard_rows}
        )

    async def _update_business_owner_message(self, message_id: int, chat_id: str):
        """Biznes egasi uchun xabarni tahrirlash (orqaga qaytish)"""
        user_data = self._verified_users.get(chat_id, {})
        biz_id = user_data.get("business_id")
        biz_title = user_data.get("business_title", "Noma'lum")
        user_phone = user_data.get("phone", "")

        group_id = self._business_groups.get(str(biz_id), "") if biz_id else ""

        orders_today = 0
        accepted_today = 0
        rejected_today = 0
        if self.stats_service and user_phone:
            stats = self.stats_service.get_period_stats("daily")
            for record in stats.order_records:
                if record.get("seller_phone") == user_phone:
                    orders_today += 1
                    if record.get("result") == "accepted":
                        accepted_today += 1
                    elif record.get("result") == "rejected":
                        rejected_today += 1

        text = f"🏪 <b>{biz_title}</b>\n"
        text += f"━━━━━━━━━━━━━━━━━━━━\n\n"
        text += f"📦 <b>Bugungi buyurtmalar:</b> {orders_today} ta\n"
        text += f"├ ✅ Qabul qilindi: {accepted_today}\n"
        text += f"└ ❌ Bekor qilindi: {rejected_today}\n\n"

        if group_id:
            text += f"👥 <b>Guruh:</b> Ulangan ✅\n"
        else:
            text += f"👥 <b>Guruh:</b> Ulanmagan ❌\n"
            text += f"<i>Guruh qo'shsangiz, buyurtmalar haqida xabar keladi</i>\n"

        keyboard_rows = []
        row1 = [{"text": "📦 Buyurtmalar", "callback_data": "owner_orders"}]
        if biz_id:
            if group_id:
                row1.append({"text": "✏️ Biznes guruh", "callback_data": f"{CALLBACK_BIZ_ADD_GROUP}{biz_id}"})
            else:
                row1.append({"text": "➕ Biznes guruh", "callback_data": f"{CALLBACK_BIZ_ADD_GROUP}{biz_id}"})
        keyboard_rows.append(row1)

        keyboard_rows.append([
            {"text": "🛒 Buyurtma berish", "web_app": {"url": "https://nonbor.uz"}},
            {"text": "🏪 Biznesim", "web_app": {"url": "https://business.nonbor.uz"}}
        ])

        keyboard_rows.append([
            {"text": "🆘 Qo'llab quvvatlash", "url": "https://t.me/NonborSupportBot"}
        ])

        await self.telegram.edit_message(
            message_id=message_id,
            text=text,
            chat_id=chat_id,
            parse_mode="HTML",
            reply_markup={"inline_keyboard": keyboard_rows}
        )

    async def _show_owner_orders(self, message_id: int, chat_id: str, period: str = None, page: int = None, status_filter: str = None):
        """Biznes egasi uchun buyurtmalar ro'yxati - pagination va filtrlar bilan"""
        user_data = self._verified_users.get(chat_id, {})
        biz_title = user_data.get("business_title", "Noma'lum")
        user_phone = user_data.get("phone", "")

        # State dan olish (agar parametr berilmagan bo'lsa)
        if period is None:
            period = self._owner_orders_period.get(chat_id, "daily")
        if page is None:
            page = self._owner_orders_page.get(chat_id, 0)
        if status_filter is None:
            status_filter = self._owner_orders_status.get(chat_id, "all")

        # State ni yangilash
        self._owner_orders_period[chat_id] = period
        self._owner_orders_page[chat_id] = page
        self._owner_orders_status[chat_id] = status_filter

        # Davr nomlari
        period_names = {
            "daily": "Bugungi",
            "weekly": "Haftalik",
            "monthly": "Oylik",
            "yearly": "Yillik"
        }
        period_name = period_names.get(period, "Bugungi")

        # Buyurtmalarni olish
        orders_list = []
        if self.stats_service and user_phone:
            stats = self.stats_service.get_period_stats(period)
            for record in stats.order_records:
                if record.get("seller_phone") == user_phone:
                    # Status filter
                    if status_filter == "all":
                        orders_list.append(record)
                    elif status_filter == "accepted" and record.get("result") == "accepted":
                        orders_list.append(record)
                    elif status_filter == "rejected" and record.get("result") == "rejected":
                        orders_list.append(record)

        # Buyurtmalarni teskari tartibda (eng yangi birinchi)
        orders_list = list(reversed(orders_list))

        # Pagination
        ITEMS_PER_PAGE = 20
        total_orders = len(orders_list)
        total_pages = max(1, (total_orders + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)
        page = max(0, min(page, total_pages - 1))  # Valid page range

        start_idx = page * ITEMS_PER_PAGE
        end_idx = min(start_idx + ITEMS_PER_PAGE, total_orders)
        page_orders = orders_list[start_idx:end_idx]

        # Status nomi
        status_names = {"all": "Barchasi", "accepted": "Qabul qilingan", "rejected": "Bekor qilingan"}
        status_name = status_names.get(status_filter, "Barchasi")

        # Statistika
        accepted_count = sum(1 for o in orders_list if o.get("result") == "accepted") if status_filter == "all" else (total_orders if status_filter == "accepted" else 0)
        rejected_count = sum(1 for o in orders_list if o.get("result") == "rejected") if status_filter == "all" else (total_orders if status_filter == "rejected" else 0)

        # Matn
        text = f"📦 <b>{biz_title}</b>\n"
        text += f"━━━━━━━━━━━━━━━━━━━━\n"
        text += f"📅 {period_name} | 🔍 {status_name}\n"
        text += f"━━━━━━━━━━━━━━━━━━━━\n\n"

        if not page_orders:
            text += "<i>Buyurtmalar topilmadi</i>\n"
        else:
            for i, order in enumerate(page_orders, start_idx + 1):
                order_num = order.get("order_number", order.get("order_id", "?"))
                result = order.get("result", "?")
                client_name = order.get("client_name", "Noma'lum")[:15]
                product = order.get("product_name", "")[:20]
                price = order.get("price", 0)
                timestamp = order.get("timestamp", "")

                # Vaqtni format qilish
                time_str = ""
                if timestamp:
                    try:
                        dt = datetime.fromisoformat(timestamp)
                        time_str = dt.strftime("%H:%M")
                    except:
                        pass

                # Status emoji
                if result == "accepted":
                    emoji = "✅"
                elif result == "rejected":
                    emoji = "❌"
                else:
                    emoji = "⏳"

                # Qisqa format: raqam, mijoz, mahsulot, narx, vaqt
                text += f"{emoji} <b>#{order_num}</b>"
                if time_str:
                    text += f" ({time_str})"
                text += f"\n   {client_name}"
                if product:
                    text += f" - {product}"
                if price:
                    text += f"\n   💰 {price:,} so'm"
                text += "\n\n"

        # Footer
        text += f"━━━━━━━━━━━━━━━━━━━━\n"
        if status_filter == "all":
            text += f"📊 Jami: {total_orders} ta (✅{accepted_count} | ❌{rejected_count})\n"
        else:
            text += f"📊 Jami: {total_orders} ta\n"
        if total_pages > 1:
            text += f"📄 Sahifa: {page + 1}/{total_pages}"

        # Keyboard
        keyboard_rows = []

        # 1. Davr tugmalari
        period_row = []
        periods = [("📅", "daily"), ("📆", "weekly"), ("🗓", "monthly"), ("📊", "yearly")]
        for emoji, p in periods:
            if p == period:
                period_row.append({"text": f"✓ {emoji}", "callback_data": f"{CALLBACK_OWNER_PERIOD}{p}"})
            else:
                period_row.append({"text": emoji, "callback_data": f"{CALLBACK_OWNER_PERIOD}{p}"})
        keyboard_rows.append(period_row)

        # 2. Status filter tugmalari
        status_row = []
        statuses = [("📋", "all"), ("✅", "accepted"), ("❌", "rejected")]
        for emoji, s in statuses:
            if s == status_filter:
                status_row.append({"text": f"✓ {emoji}", "callback_data": f"{CALLBACK_OWNER_STATUS}{s}"})
            else:
                status_row.append({"text": emoji, "callback_data": f"{CALLBACK_OWNER_STATUS}{s}"})
        keyboard_rows.append(status_row)

        # 3. Pagination
        if total_pages > 1:
            nav_row = []
            if page > 0:
                nav_row.append({"text": "⬅️", "callback_data": f"{CALLBACK_OWNER_PAGE}{page - 1}"})
            else:
                nav_row.append({"text": "·", "callback_data": "noop"})

            nav_row.append({"text": f"{page + 1}/{total_pages}", "callback_data": "noop"})

            if page < total_pages - 1:
                nav_row.append({"text": "➡️", "callback_data": f"{CALLBACK_OWNER_PAGE}{page + 1}"})
            else:
                nav_row.append({"text": "·", "callback_data": "noop"})

            keyboard_rows.append(nav_row)

        # 4. Orqaga tugmasi
        keyboard_rows.append([{"text": "⬅️ Orqaga", "callback_data": CALLBACK_OWNER_BACK}])

        await self.telegram.edit_message(
            message_id=message_id,
            text=text,
            chat_id=chat_id,
            parse_mode="HTML",
            reply_markup={"inline_keyboard": keyboard_rows}
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
                    {"text": f"📞 Qo'ng'iroqlar ({stats.total_calls})", "callback_data": CALLBACK_MENU_CALLS},
                    {"text": f"📦 Buyurtmalar ({stats.total_orders})", "callback_data": CALLBACK_MENU_ORDERS}
                ],
                [
                    {"text": "👥 Bizneslar", "callback_data": CALLBACK_MENU_BUSINESSES}
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

    async def _show_businesses(self, message_id: int, chat_id: str, page: int = 0):
        """Bizneslar ro'yxati - pagination bilan"""
        if not self.nonbor_service:
            await self.telegram.edit_message(
                message_id=message_id,
                text="❌ Nonbor servisi ulanmagan",
                chat_id=chat_id,
                parse_mode="HTML",
                reply_markup={"inline_keyboard": [[{"text": "◀️ Orqaga", "callback_data": CALLBACK_MENU_BACK}]]}
            )
            return

        businesses = await self.nonbor_service.get_businesses()
        if not businesses:
            await self.telegram.edit_message(
                message_id=message_id,
                text="📭 Bizneslar topilmadi",
                chat_id=chat_id,
                parse_mode="HTML",
                reply_markup={"inline_keyboard": [
                    [{"text": "🔄 Yangilash", "callback_data": CALLBACK_BIZ_REFRESH}],
                    [{"text": "◀️ Orqaga", "callback_data": CALLBACK_MENU_BACK}]
                ]}
            )
            return

        # Admin bo'lmagan foydalanuvchilar faqat o'z biznesini ko'radi
        if not self._is_admin(chat_id):
            user_biz_id = self._get_user_business_id(chat_id)
            if user_biz_id:
                await self._show_business_detail(message_id, chat_id, user_biz_id)
                return
            else:
                await self.telegram.edit_message(
                    message_id=message_id,
                    text="❌ Sizning biznesingiz topilmadi",
                    chat_id=chat_id,
                    parse_mode="HTML",
                    reply_markup={"inline_keyboard": [[{"text": "◀️ Orqaga", "callback_data": CALLBACK_MENU_BACK}]]}
                )
                return

        # Viloyat bo'yicha guruhlash (cache uchun)
        regions = {}
        for biz in businesses:
            region = biz.get("region_name_uz") or "Noma'lum"
            if region not in regions:
                regions[region] = []
            regions[region].append(biz)

        self._biz_regions = sorted(regions.keys())
        self._biz_regions_data = regions
        self._biz_all = businesses

        # Pagination
        per_page = 10
        total = len(businesses)
        total_pages = max(1, (total + per_page - 1) // per_page)
        page = max(0, min(page, total_pages - 1))

        start = page * per_page
        end = min(start + per_page, total)
        page_businesses = businesses[start:end]

        # Xabar tuzish - bizneslar ma'lumotlari bilan
        text = f"👥 <b>BIZNESLAR</b> ({total} ta)\n"
        text += f"━━━━━━━━━━━━━━━━━━━━\n"
        text += f"📄 Sahifa {page + 1}/{total_pages}\n\n"

        for i, biz in enumerate(page_businesses, start + 1):
            title = biz.get("title", "Noma'lum")
            phone = biz.get("phone_number", "")
            owner_first = biz.get("owner_first_name") or ""
            owner_last = biz.get("owner_last_name") or ""
            owner = f"{owner_first} {owner_last}".strip()
            region = biz.get("region_name_uz") or ""
            district = biz.get("district_name_uz") or ""
            address = biz.get("address") or ""
            group_id = self._business_groups.get(str(biz.get("id", 0)), "")
            mark = " ✅" if group_id else ""

            text += f"<b>{i}. {title}</b>{mark}\n"
            if owner:
                text += f"   👤 {owner}"
                if phone:
                    text += f" | 📱 {phone}"
                text += "\n"
            elif phone:
                text += f"   📱 {phone}\n"
            # Manzil (address) yoki viloyat/tuman
            if address:
                text += f"   📍 {address}\n"
            elif region or district:
                loc = f"{region}"
                if district:
                    loc += f", {district}"
                text += f"   📍 {loc}\n"
            text += "\n"

        # Keyboard
        keyboard_rows = []

        # Raqam tugmalari (5 tadan 2 qatorga)
        num_row = []
        for i, biz in enumerate(page_businesses, start + 1):
            biz_id = biz.get("id", 0)
            num_row.append({"text": str(i), "callback_data": f"{CALLBACK_BIZ_ITEM}{biz_id}"})
            if len(num_row) == 5:
                keyboard_rows.append(num_row)
                num_row = []
        if num_row:
            keyboard_rows.append(num_row)

        # Pagination tugmalari
        nav_row = []
        if page > 0:
            nav_row.append({"text": "◀️ Oldingi", "callback_data": f"{CALLBACK_BIZ_PAGE}{page - 1}"})
        if page < total_pages - 1:
            nav_row.append({"text": "Keyingi ▶️", "callback_data": f"{CALLBACK_BIZ_PAGE}{page + 1}"})
        if nav_row:
            keyboard_rows.append(nav_row)

        # Viloyat tugmalari (2 tadan)
        keyboard_rows.append([{"text": "━━ Viloyatlar ━━", "callback_data": "noop"}])
        region_row = []
        for idx, region_name in enumerate(self._biz_regions):
            count = len(regions[region_name])
            btn_text = f"🏙 {region_name} ({count})"
            region_row.append({"text": btn_text, "callback_data": f"{CALLBACK_BIZ_REGION}{idx}"})
            if len(region_row) == 2:
                keyboard_rows.append(region_row)
                region_row = []
        if region_row:
            keyboard_rows.append(region_row)

        # Pastki tugmalar
        keyboard_rows.append([
            {"text": "🔄 Yangilash", "callback_data": CALLBACK_BIZ_REFRESH},
            {"text": "◀️ Orqaga", "callback_data": CALLBACK_MENU_BACK}
        ])

        await self.telegram.edit_message(
            message_id=message_id,
            text=text,
            chat_id=chat_id,
            parse_mode="HTML",
            reply_markup={"inline_keyboard": keyboard_rows}
        )

    async def _show_region_districts(self, message_id: int, chat_id: str, region_idx: int, page: int = 0):
        """Tanlangan viloyatdagi bizneslar (pagination) + tuman tugmalari"""
        if not hasattr(self, '_biz_regions') or region_idx >= len(self._biz_regions):
            await self._show_businesses(message_id, chat_id)
            return

        region_name = self._biz_regions[region_idx]
        region_businesses = self._biz_regions_data.get(region_name, [])

        # Tuman bo'yicha guruhlash
        districts = {}
        for biz in region_businesses:
            district = biz.get("district_name_uz") or "Noma'lum"
            if district not in districts:
                districts[district] = []
            districts[district].append(biz)

        # Cache tumanlar
        self._biz_current_districts = sorted(districts.keys())
        self._biz_current_districts_data = districts
        self._biz_current_region_idx = region_idx

        # Pagination
        per_page = 10
        total = len(region_businesses)
        total_pages = max(1, (total + per_page - 1) // per_page)
        page = max(0, min(page, total_pages - 1))

        start = page * per_page
        end = min(start + per_page, total)
        page_businesses = region_businesses[start:end]

        # Xabar tuzish
        text = f"🏙 <b>{region_name}</b> ({total} ta)\n"
        text += f"━━━━━━━━━━━━━━━━━━━━\n"
        text += f"📄 Sahifa {page + 1}/{total_pages}\n\n"

        # Biznes ro'yxati matnda - egasi, telefoni va manzili bilan
        for i, biz in enumerate(page_businesses, start + 1):
            title = biz.get("title", "Noma'lum")
            biz_id = biz.get("id", 0)
            phone = biz.get("phone_number", "")
            owner_first = biz.get("owner_first_name") or ""
            owner_last = biz.get("owner_last_name") or ""
            owner = f"{owner_first} {owner_last}".strip()
            address = biz.get("address", "")
            district = biz.get("district_name_uz") or ""
            group_id = self._business_groups.get(str(biz_id), "")
            mark = " ✅" if group_id else ""

            text += f"<b>{i}. {title}</b>{mark}\n"
            if owner:
                text += f"   👤 {owner}"
                if phone:
                    text += f" | 📱 {phone}"
                text += "\n"
            elif phone:
                text += f"   📱 {phone}\n"
            # Manzil yoki tuman
            if address:
                text += f"   📍 {address}\n"
            elif district:
                text += f"   📍 {district}\n"

        # Keyboard
        keyboard_rows = []

        # Biznes raqam tugmalari (5 tadan qatorga)
        num_row = []
        for i, biz in enumerate(page_businesses, start + 1):
            biz_id = biz.get("id", 0)
            num_row.append({"text": str(i), "callback_data": f"{CALLBACK_BIZ_ITEM}{biz_id}"})
            if len(num_row) == 5:
                keyboard_rows.append(num_row)
                num_row = []
        if num_row:
            keyboard_rows.append(num_row)

        # Pagination tugmalari
        nav_row = []
        if page > 0:
            nav_row.append({"text": "◀️ Oldingi", "callback_data": f"{CALLBACK_BIZ_REG_PAGE}{region_idx}_{page - 1}"})
        if page < total_pages - 1:
            nav_row.append({"text": "Keyingi ▶️", "callback_data": f"{CALLBACK_BIZ_REG_PAGE}{region_idx}_{page + 1}"})
        if nav_row:
            keyboard_rows.append(nav_row)

        # Tuman tugmalari (2 tadan qatorga)
        keyboard_rows.append([{"text": "━━ Tumanlar ━━", "callback_data": "noop"}])
        dist_row = []
        for idx, dist_name in enumerate(self._biz_current_districts):
            count = len(districts[dist_name])
            btn_text = f"📍 {dist_name} ({count})"
            dist_row.append({"text": btn_text, "callback_data": f"{CALLBACK_BIZ_DISTRICT}{region_idx}_{idx}"})
            if len(dist_row) == 2:
                keyboard_rows.append(dist_row)
                dist_row = []
        if dist_row:
            keyboard_rows.append(dist_row)

        # Pastki tugmalar
        keyboard_rows.append([
            {"text": "◀️ Viloyatlar", "callback_data": CALLBACK_BIZ_BACK}
        ])

        await self.telegram.edit_message(
            message_id=message_id,
            text=text,
            chat_id=chat_id,
            parse_mode="HTML",
            reply_markup={"inline_keyboard": keyboard_rows}
        )

    async def _show_district_businesses(self, message_id: int, chat_id: str, region_idx: int, district_idx: int):
        """Tanlangan tumandagi bizneslarni ko'rsatish"""
        if not hasattr(self, '_biz_current_districts') or district_idx >= len(self._biz_current_districts):
            await self._show_region_districts(message_id, chat_id, region_idx)
            return

        district_name = self._biz_current_districts[district_idx]
        district_businesses = self._biz_current_districts_data.get(district_name, [])
        region_name = self._biz_regions[region_idx] if region_idx < len(self._biz_regions) else ""

        # Xabar tuzish
        text = f"📍 <b>{district_name}</b> ({len(district_businesses)} ta)\n"
        text += f"🏙 {region_name}\n"
        text += f"━━━━━━━━━━━━━━━━━━━━\n\n"

        # Biznes ro'yxati matnda - egasi, telefoni va manzili bilan
        for i, biz in enumerate(district_businesses, 1):
            title = biz.get("title", "Noma'lum")
            biz_id = biz.get("id", 0)
            phone = biz.get("phone_number", "")
            owner_first = biz.get("owner_first_name") or ""
            owner_last = biz.get("owner_last_name") or ""
            owner = f"{owner_first} {owner_last}".strip()
            address = biz.get("address") or ""
            biz_region = biz.get("region_name_uz") or ""
            biz_district = biz.get("district_name_uz") or ""
            group_id = self._business_groups.get(str(biz_id), "")
            mark = " ✅" if group_id else ""

            text += f"<b>{i}. {title}</b>{mark}\n"
            if owner:
                text += f"   👤 {owner}"
                if phone:
                    text += f" | 📱 {phone}"
                text += "\n"
            elif phone:
                text += f"   📱 {phone}\n"
            # Manzil: address yoki viloyat+tuman
            if address:
                text += f"   📍 {address}\n"
            elif biz_region or biz_district:
                loc = biz_region
                if biz_district:
                    loc += f", {biz_district}" if loc else biz_district
                text += f"   📍 {loc}\n"
            text += "\n"

        # Keyboard
        keyboard_rows = []

        # Biznes raqam tugmalari (5 tadan qatorga)
        num_row = []
        for i, biz in enumerate(district_businesses, 1):
            biz_id = biz.get("id", 0)
            num_row.append({"text": str(i), "callback_data": f"{CALLBACK_BIZ_ITEM}{biz_id}"})
            if len(num_row) == 5:
                keyboard_rows.append(num_row)
                num_row = []
        if num_row:
            keyboard_rows.append(num_row)

        keyboard_rows.append([
            {"text": f"◀️ {region_name}", "callback_data": f"{CALLBACK_BIZ_DIST_BACK}{region_idx}"}
        ])

        await self.telegram.edit_message(
            message_id=message_id,
            text=text,
            chat_id=chat_id,
            parse_mode="HTML",
            reply_markup={"inline_keyboard": keyboard_rows}
        )

    async def _show_business_detail(self, message_id: int, chat_id: str, biz_id: int):
        """Biznes tafsilotlarini ko'rsatish"""
        # Awaiting state ni tozalash (agar bekor qilish bosilgan bo'lsa)
        self._awaiting_group_input.pop(chat_id, None)
        self._awaiting_message_id.pop(chat_id, None)

        # Admin bo'lmagan foydalanuvchilar faqat o'z biznesini ko'ra oladi
        if not self._is_admin(chat_id):
            user_biz_id = self._get_user_business_id(chat_id)
            if user_biz_id != biz_id:
                await self.telegram.edit_message(
                    message_id=message_id,
                    text="🚫 Bu biznesga kirishga ruxsat yo'q",
                    chat_id=chat_id,
                    parse_mode="HTML",
                    reply_markup={"inline_keyboard": [[{"text": "◀️ Orqaga", "callback_data": CALLBACK_MENU_BACK}]]}
                )
                return

        # Biznesni topish
        biz = None
        if hasattr(self, '_biz_all') and self._biz_all:
            for b in self._biz_all:
                if b.get("id") == biz_id:
                    biz = b
                    break

        if not biz and self.nonbor_service:
            businesses = await self.nonbor_service.get_businesses()
            for b in businesses:
                if b.get("id") == biz_id:
                    biz = b
                    break

        if not biz:
            await self.telegram.edit_message(
                message_id=message_id,
                text="❌ Biznes topilmadi",
                chat_id=chat_id,
                parse_mode="HTML",
                reply_markup={"inline_keyboard": [[{"text": "◀️ Orqaga", "callback_data": CALLBACK_BIZ_BACK}]]}
            )
            return

        title = biz.get("title", "Noma'lum")
        phone = biz.get("phone_number", "")
        region = biz.get("region_name_uz") or "Noma'lum"
        district = biz.get("district_name_uz") or "Noma'lum"
        address = biz.get("address") or "Ko'rsatilmagan"
        owner_first = biz.get("owner_first_name") or ""
        owner_last = biz.get("owner_last_name") or ""
        owner = f"{owner_first} {owner_last}".strip() or "Noma'lum"

        # Guruh ID
        group_id = self._business_groups.get(str(biz_id), "")

        text = f"🏪 <b>{title}</b>\n"
        text += f"━━━━━━━━━━━━━━━━━━━━\n\n"
        text += f"📱 <b>Telefon:</b> {phone}\n"
        text += f"👤 <b>Egasi:</b> {owner}\n"
        text += f"🏙 <b>Viloyat:</b> {region}\n"
        text += f"📍 <b>Tuman:</b> {district}\n"
        if group_id:
            text += f"👥 <b>Guruh:</b> <code>{group_id}</code>\n"
        else:
            if address and address != "Ko'rsatilmagan":
                text += f"🏠 <b>Manzil:</b> {address}\n"

        keyboard_rows = []
        if group_id:
            keyboard_rows.append([{"text": "✏️ Guruhni o'zgartirish", "callback_data": f"{CALLBACK_BIZ_ADD_GROUP}{biz_id}"}])
        else:
            keyboard_rows.append([{"text": "➕ Guruh qo'shish", "callback_data": f"{CALLBACK_BIZ_ADD_GROUP}{biz_id}"}])
        # Orqaga tugmasi faqat admin uchun
        if self._is_admin(chat_id):
            keyboard_rows.append([
                {"text": "◀️ Orqaga", "callback_data": CALLBACK_BIZ_BACK}
            ])

        await self.telegram.edit_message(
            message_id=message_id,
            text=text,
            chat_id=chat_id,
            parse_mode="HTML",
            reply_markup={"inline_keyboard": keyboard_rows}
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
                [{"text": "◀️ Orqaga", "callback_data": CALLBACK_CALLS_BACK}]
            ]
        }

        await self.telegram.edit_message(
            message_id=message_id,
            text=text,
            chat_id=chat_id,
            parse_mode="HTML",
            reply_markup=keyboard
        )

    async def _show_all_calls(self, message_id: int, chat_id: str):
        """Qo'ng'iroqlar bo'limi - filtrlar bilan"""
        if not self.stats_service:
            return

        stats = self.stats_service.get_period_stats(self._current_period)
        title = self._get_period_title()

        text = f"""📞 <b>{title} QO'NG'IROQLAR</b>
━━━━━━━━━━━━━━━━━━━━

📊 <b>Umumiy:</b> {stats.total_calls} ta qo'ng'iroq

<b>Urinishlar bo'yicha:</b>
├ 1️⃣ 1-urinishda: {stats.calls_1_attempt}
└ 2️⃣ 2-urinishda: {stats.calls_2_attempts}

<b>Natija bo'yicha:</b>
├ ✅ Javob berildi: {stats.answered_calls}
└ ❌ Javobsiz: {stats.unanswered_calls}

<i>Batafsil ko'rish uchun tugmalarni bosing:</i>"""

        keyboard = {
            "inline_keyboard": [
                [
                    {"text": f"1️⃣ 1-urinish ({stats.calls_1_attempt})", "callback_data": CALLBACK_CALLS_1},
                    {"text": f"2️⃣ 2-urinish ({stats.calls_2_attempts})", "callback_data": CALLBACK_CALLS_2}
                ],
                [
                    {"text": f"✅ Javob ({stats.answered_calls})", "callback_data": CALLBACK_ANSWERED},
                    {"text": f"❌ Javobsiz ({stats.unanswered_calls})", "callback_data": CALLBACK_UNANSWERED}
                ],
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
                [{"text": "◀️ Orqaga", "callback_data": CALLBACK_CALLS_BACK}]
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
                [{"text": "◀️ Orqaga", "callback_data": CALLBACK_CALLS_BACK}]
            ]
        }

        await self.telegram.edit_message(
            message_id=message_id,
            text=text,
            chat_id=chat_id,
            parse_mode="HTML",
            reply_markup=keyboard
        )

    async def _show_orders_menu(self, message_id: int, chat_id: str, page: int = None, status_filter: str = None):
        """Admin uchun buyurtmalar bo'limi - pagination va filtrlar bilan"""
        if not self.stats_service:
            return

        # State dan olish
        if page is None:
            page = self._admin_orders_page.get(chat_id, 0)
        if status_filter is None:
            status_filter = self._admin_orders_status.get(chat_id, "all")

        # State ni yangilash
        self._admin_orders_page[chat_id] = page
        self._admin_orders_status[chat_id] = status_filter

        stats = self.stats_service.get_period_stats(self._current_period)
        title = self._get_period_title()

        # Buyurtmalarni olish
        orders_list = []
        for record in stats.order_records:
            if status_filter == "all":
                orders_list.append(record)
            elif status_filter == "accepted" and record.get("result") == "accepted":
                orders_list.append(record)
            elif status_filter == "rejected" and record.get("result") == "rejected":
                orders_list.append(record)
            elif status_filter == "notg" and record.get("telegram_sent") == False:
                orders_list.append(record)

        # Teskari tartibda (eng yangi birinchi)
        orders_list = list(reversed(orders_list))

        # Pagination
        ITEMS_PER_PAGE = 20
        total_orders = len(orders_list)
        total_pages = max(1, (total_orders + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)
        page = max(0, min(page, total_pages - 1))

        start_idx = page * ITEMS_PER_PAGE
        end_idx = min(start_idx + ITEMS_PER_PAGE, total_orders)
        page_orders = orders_list[start_idx:end_idx]

        # Status nomi
        status_names = {
            "all": "Barchasi",
            "accepted": "Qabul qilingan",
            "rejected": "Bekor qilingan",
            "notg": "Telegram'siz"
        }
        status_name = status_names.get(status_filter, "Barchasi")

        # Matn
        text = f"📦 <b>{title} BUYURTMALAR</b>\n"
        text += f"━━━━━━━━━━━━━━━━━━━━\n"
        text += f"🔍 {status_name}\n"
        text += f"━━━━━━━━━━━━━━━━━━━━\n\n"

        if not page_orders:
            text += "<i>Buyurtmalar topilmadi</i>\n"
        else:
            for i, order in enumerate(page_orders, start_idx + 1):
                order_num = order.get("order_number", order.get("order_id", "?"))
                result = order.get("result", "?")
                client_name = order.get("client_name", "Noma'lum")[:15]
                seller_name = order.get("seller_name", "")[:15]
                product = order.get("product_name", "")[:20]
                price = order.get("price", 0)
                timestamp = order.get("timestamp", "")
                tg_sent = order.get("telegram_sent", True)

                # Vaqtni format qilish (sana + vaqt)
                time_str = ""
                if timestamp:
                    try:
                        dt = datetime.fromisoformat(timestamp)
                        time_str = dt.strftime("%d.%m %H:%M")
                    except:
                        pass

                # Status emoji
                if result == "accepted":
                    emoji = "✅"
                elif result == "rejected":
                    emoji = "❌"
                else:
                    emoji = "⏳"

                # Telegram'siz belgisi
                tg_mark = "" if tg_sent else " 🚀"

                # Tartib raqami + status emoji + buyurtma raqami
                text += f"<b>{i}.</b> {emoji} <b>#{order_num}</b>{tg_mark}"
                if time_str:
                    text += f" ({time_str})"
                text += f"\n   👤 {client_name}"
                if seller_name:
                    text += f" | 🏪 {seller_name}"
                if product:
                    text += f"\n   📦 {product}"
                if price:
                    text += f" | 💰 {price:,}"
                text += "\n\n"

        # Footer
        text += f"━━━━━━━━━━━━━━━━━━━━\n"
        text += f"📊 Jami: {total_orders} ta"
        if status_filter == "all":
            accepted = stats.accepted_orders
            rejected = stats.rejected_orders
            notg = stats.accepted_without_telegram
            text += f" (✅{accepted} | ❌{rejected} | 🚀{notg})"
        if total_pages > 1:
            text += f"\n📄 Sahifa: {page + 1}/{total_pages}"

        # Keyboard
        keyboard_rows = []

        # 1. Status filter tugmalari
        status_row1 = []
        status_row2 = []
        statuses = [
            ("📋 Barchasi", "all"),
            ("✅ Qabul", "accepted"),
            ("❌ Bekor", "rejected"),
            ("🚀 Tg'siz", "notg")
        ]
        for label, s in statuses[:2]:
            if s == status_filter:
                status_row1.append({"text": f"✓ {label}", "callback_data": f"{CALLBACK_ADMIN_ORDERS_STATUS}{s}"})
            else:
                status_row1.append({"text": label, "callback_data": f"{CALLBACK_ADMIN_ORDERS_STATUS}{s}"})
        for label, s in statuses[2:]:
            if s == status_filter:
                status_row2.append({"text": f"✓ {label}", "callback_data": f"{CALLBACK_ADMIN_ORDERS_STATUS}{s}"})
            else:
                status_row2.append({"text": label, "callback_data": f"{CALLBACK_ADMIN_ORDERS_STATUS}{s}"})

        keyboard_rows.append(status_row1)
        keyboard_rows.append(status_row2)

        # 2. Pagination
        if total_pages > 1:
            nav_row = []
            if page > 0:
                nav_row.append({"text": "⬅️", "callback_data": f"{CALLBACK_ADMIN_ORDERS_PAGE}{page - 1}"})
            else:
                nav_row.append({"text": "·", "callback_data": "noop"})

            nav_row.append({"text": f"{page + 1}/{total_pages}", "callback_data": "noop"})

            if page < total_pages - 1:
                nav_row.append({"text": "➡️", "callback_data": f"{CALLBACK_ADMIN_ORDERS_PAGE}{page + 1}"})
            else:
                nav_row.append({"text": "·", "callback_data": "noop"})

            keyboard_rows.append(nav_row)

        # 3. Orqaga tugmasi
        keyboard_rows.append([{"text": "◀️ Orqaga", "callback_data": CALLBACK_BACK}])

        await self.telegram.edit_message(
            message_id=message_id,
            text=text,
            chat_id=chat_id,
            parse_mode="HTML",
            reply_markup={"inline_keyboard": keyboard_rows}
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
