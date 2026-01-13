"""
Telegram Bot Servisi
Xabar yuborish va boshqarish
"""

import logging
import aiohttp
import asyncio
from typing import Optional, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


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
            "parse_mode": parse_mode,
            "disable_notification": disable_notification
        }

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

        result = await self._make_request("deleteMessage", data)

        if result:
            logger.info(f"Telegram xabar o'chirildi: {message_id}")
            return True

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
            parse_mode="HTML"
        )

    def _format_seller_orders_alert(self, seller_orders: dict, call_attempts: int = 0) -> str:
        """Sotuvchi buyurtmalari xabarini formatlash"""
        seller_name = seller_orders.get("seller_name", "Noma'lum")
        seller_phone = seller_orders.get("seller_phone", "Noma'lum")
        seller_address = seller_orders.get("seller_address", "Noma'lum")
        orders = seller_orders.get("orders", [])
        orders_count = len(orders)

        # Umumiy narx
        total_price = sum(o.get("price", 0) or 0 for o in orders)
        total_price_str = f"{total_price:,.0f}".replace(",", " ") + " so'm"

        # Header
        text = f"""🚨 <b>DIQQAT! {orders_count} ta buyurtma qabul qilinmadi!</b>

<b>SOTUVCHI:</b>
  Nomi: {seller_name}
  Tel: {seller_phone}
  Manzil: {seller_address}

<b>━━━ BUYURTMALAR ━━━</b>
"""
        # Har bir buyurtma (mijoz)
        for i, order in enumerate(orders, 1):
            lead_id = order.get("lead_id", "N/A")
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

            text += f"""
<b>{i}. Buyurtma #{lead_id}</b>
   Mijoz: {client_name}
   Tel: {client_phone}
   Mahsulot: {product_name}
   Miqdor: {quantity} ta
   Narx: {price_str}
"""

        # Footer
        text += f"""
<b>━━━━━━━━━━━━━━━━━━━━━</b>
📦 Jami: <b>{orders_count}</b> ta buyurtma
💰 Umumiy: <b>{total_price_str}</b>

❌ Buyurtmalarni qabul qilmayapti!
📞 {call_attempts} marta qo'ng'iroq qilindi.
🔴 Zudlik bilan bog'laning!

📱 <a href="https://welltech.amocrm.ru/leads/pipeline/10154618">Buyurtmalarni ko'rish</a>"""

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

    def __init__(self, telegram_service: TelegramService):
        self.telegram = telegram_service
        self._active_message_ids: list = []  # Barcha yuborilgan xabarlar
        self._last_count = 0
        self._message_sent_at: Optional[datetime] = None

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

    async def notify_resolved(self, resolved_count: int, remaining_count: int):
        """
        Buyurtmalar tekshirildi xabari

        Agar hammasi tekshirilgan bo'lsa - barcha aktiv xabarlarni o'chiradi
        """
        if remaining_count == 0 and self._active_message_ids:
            # Barcha aktiv xabarlarni o'chirish
            for msg_id in self._active_message_ids:
                await self.telegram.delete_message(msg_id)
            self._active_message_ids = []
            self._message_sent_at = None

        self._last_count = remaining_count

    async def delete_all_notifications(self):
        """Barcha aktiv xabarlarni o'chirish"""
        for msg_id in self._active_message_ids:
            await self.telegram.delete_message(msg_id)
        self._active_message_ids = []
        self._message_sent_at = None

    def clear_notification(self):
        """Bildirishnoma holatini tozalash"""
        self._active_message_ids = []
        self._last_count = 0
        self._message_sent_at = None

    @property
    def has_active_notification(self) -> bool:
        """Aktiv bildirishnoma bormi"""
        return len(self._active_message_ids) > 0
