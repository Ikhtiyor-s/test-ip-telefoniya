"""
Nonbor API Integratsiya Servisi
Buyurtmalarni kuzatish va boshqarish (amoCRM o'rniga)
"""

import logging
import os
import aiohttp
import asyncio
from typing import List, Dict, Optional, Set
from datetime import datetime

logger = logging.getLogger(__name__)

NONBOR_BASE_URL = os.getenv("NONBOR_BASE_URL", "https://test.nonbor.uz/api/v2")
NONBOR_SECRET = os.getenv("NONBOR_SECRET", "nonbor-secret-key")
# Domain ni base_url dan olish (orders endpoint uchun)
NONBOR_DOMAIN = NONBOR_BASE_URL.split("/api/")[0]  # https://nonbor.uz


class NonborService:
    """
    Nonbor API bilan ishlash servisi

    Funksiyalar:
    - Yangi buyurtmalarni kuzatish (CHECKING status)
    - Buyurtmalar sonini olish
    - Bizneslar (sotuvchilar) ma'lumotlarini olish
    - Status o'zgarishlarini kuzatish
    """

    def __init__(self, status_name: str = "CHECKING"):
        self.status_name = status_name
        self.base_url = NONBOR_BASE_URL
        self.headers = {
            "accept": "application/json",
            "X-Telegram-Bot-Secret": NONBOR_SECRET,
        }

        # Cache
        self._known_leads: Set[int] = set()
        self._businesses_cache: Dict[int, Dict] = {}
        self._session: Optional[aiohttp.ClientSession] = None
        self._consecutive_errors: int = 0

        logger.info(f"Nonbor servisi ishga tushdi")

    async def _get_session(self) -> aiohttp.ClientSession:
        """HTTP session olish"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(headers=self.headers)
        return self._session

    async def close(self):
        """Sessionni yopish"""
        if self._session and not self._session.closed:
            await self._session.close()

    async def _make_request(self, method: str, endpoint: str) -> Optional[dict]:
        """API so'rov yuborish"""
        session = await self._get_session()
        url = f"{self.base_url}/{endpoint}"
        timeout = aiohttp.ClientTimeout(total=15)

        try:
            async with session.request(method, url, timeout=timeout) as response:
                if response.status == 200:
                    self._consecutive_errors = 0  # Muvaffaqiyatli - reset
                    return await response.json()
                else:
                    self._consecutive_errors += 1
                    logger.error(f"Nonbor API xatosi: {response.status}")
                    return None
        except asyncio.TimeoutError:
            self._consecutive_errors += 1
            if self._consecutive_errors <= 3 or self._consecutive_errors % 10 == 0:
                logger.error(f"Nonbor API timeout: {endpoint} (ketma-ket: {self._consecutive_errors})")
            return None
        except aiohttp.ClientError as e:
            self._consecutive_errors += 1
            if self._consecutive_errors <= 3 or self._consecutive_errors % 10 == 0:
                logger.error(f"Nonbor API ulanish xatosi: {e} (ketma-ket: {self._consecutive_errors})")
            return None

    async def get_businesses(self) -> List[Dict]:
        """Barcha tasdiqlangan bizneslarni olish"""
        data = await self._make_request("GET", "telegram_bot/businesses/accepted/")
        if not data or not data.get("success"):
            return []

        businesses = data.get("result", [])
        # Cache yangilash
        for biz in businesses:
            self._businesses_cache[biz["id"]] = biz

        return businesses

    async def get_order_status(self, order_id: int) -> Optional[str]:
        """
        Bitta buyurtmaning haqiqiy statusini olish
        Admin panel endpointidan foydalanish: /orders/{id}/

        Returns:
            Status string (masalan: "CHECKING", "ACCEPTED", "CANCELLED") yoki None
        """
        session = await self._get_session()
        # Admin panel /orders/{id}/ endpointini ishlatish (base_url siz)
        url = f"{NONBOR_DOMAIN}/orders/{order_id}/"
        timeout = aiohttp.ClientTimeout(total=10)
        try:
            async with session.get(url, timeout=timeout) as response:
                if response.status == 200:
                    data = await response.json()
                    if isinstance(data, dict):
                        state = data.get("state") or data.get("result", {}).get("state")
                        if state:
                            return state.upper()
                else:
                    logger.debug(f"Order status endpoint: {response.status}")
        except Exception as e:
            logger.debug(f"Order status endpoint xato: {e}")
        return None

    async def get_order_details(self, order_id: int) -> Optional[Dict]:
        """
        Bitta buyurtmaning to'liq ma'lumotlarini olish
        /orders/{id}/ endpoint - telefon raqami va boshqa qo'shimcha ma'lumotlar uchun

        Returns:
            To'liq buyurtma ma'lumotlari dict yoki None
        """
        session = await self._get_session()
        url = f"{NONBOR_DOMAIN}/orders/{order_id}/"
        timeout = aiohttp.ClientTimeout(total=10)
        try:
            async with session.get(url, timeout=timeout) as response:
                if response.status == 200:
                    data = await response.json()
                    if isinstance(data, dict):
                        logger.debug(f"Order #{order_id} details: {list(data.keys())}")
                        return data
                else:
                    logger.debug(f"Order details endpoint: {response.status}")
        except Exception as e:
            logger.debug(f"Order details endpoint xato: {e}")
        return None

    async def get_orders(self) -> Optional[List[Dict]]:
        """
        Barcha buyurtmalarni olish

        Returns:
            Buyurtmalar ro'yxati yoki None agar xato yuz bergan bo'lsa
        """
        data = await self._make_request("GET", "telegram_bot/get-order-for-courier/")
        if data is None:
            return None

        if not data.get("success"):
            return None

        results = data.get("result", {}).get("results", [])
        if results:
            states = {}
            for o in results:
                s = o.get("state", "unknown")
                states[s] = states.get(s, 0) + 1
            logger.info(f"API buyurtmalar: {len(results)} ta, statuslar: {states}")
        return results

    async def get_leads_by_status(self) -> Optional[List[Dict]]:
        """
        CHECKING statusidagi barcha buyurtmalarni olish
        (AmoCRM get_leads_by_status() bilan mos)

        Returns:
            Buyurtmalar ro'yxati yoki None agar xato yuz bergan bo'lsa
        """
        orders = await self.get_orders()
        if orders is None:
            return None

        # CHECKING statusdagi buyurtmalarni filter qilish
        checking_orders = [
            order for order in orders
            if order.get("state", "").upper() == self.status_name.upper()
        ]

        logger.debug(f"CHECKING buyurtmalar: {len(checking_orders)} ta (jami: {len(orders)})")
        return checking_orders

    async def check_for_new_leads(self) -> tuple:
        """
        Yangi buyurtmalarni tekshirish
        (AmoCRM check_for_new_leads() bilan mos)

        Returns:
            (jami_soni, barcha_hozirgi_order_idlar) or (None, None) agar xato
        """
        try:
            leads = await self.get_leads_by_status()

            if leads is None:
                return None, None

            current_ids = {order["id"] for order in leads}

            # Yangi buyurtmalar (faqat log uchun)
            new_ids = current_ids - self._known_leads

            # Cache yangilash
            self._known_leads = current_ids

            if new_ids:
                logger.info(f"Yangi buyurtmalar: {len(new_ids)} ta, Jami: {len(leads)} ta")

            return len(leads), list(current_ids)
        except Exception as e:
            logger.error(f"check_for_new_leads xatosi: {e}")
            return None, None

    async def get_order_full_data(self, order_id: int) -> Dict:
        """
        Buyurtma uchun to'liq ma'lumotlarni olish
        (AmoCRM get_order_full_data() bilan mos)

        Returns:
            dict: {
                lead_id, lead_name, seller_name, seller_phone, seller_address,
                client_name, client_phone, product_name, quantity, price, order_number
            }
        """
        result = {
            "lead_id": order_id,
            "lead_name": "Noma'lum",
            "seller_name": "Noma'lum",
            "seller_phone": "Noma'lum",
            "seller_address": "Noma'lum",
            "client_name": "Noma'lum",
            "client_phone": "Noma'lum",
            "product_name": "Noma'lum",
            "quantity": 1,
            "price": 0,
            "order_number": str(order_id),
        }

        # Bizneslar cacheni yangilash (agar bo'sh bo'lsa)
        if not self._businesses_cache:
            await self.get_businesses()

        # Buyurtmalarni olish va kerakli buyurtmani topish
        orders = await self.get_orders()
        if not orders:
            return result

        order = None
        for o in orders:
            if o.get("id") == order_id:
                order = o
                break

        if not order:
            # Ro'yxatda topilmadi - individual endpoint dan olish
            order_details = await self.get_order_details(order_id)
            if order_details:
                order = order_details.get("result", order_details)
                logger.info(f"Buyurtma #{order_id} individual endpoint dan olindi")
            else:
                return result

        # Buyurtma ma'lumotlari
        result["lead_id"] = order.get("id", order_id)
        result["order_number"] = str(order.get("id", order_id))
        result["price"] = (order.get("total_price", 0) or 0) / 100

        # Biznes (sotuvchi) ma'lumotlari
        business = order.get("business", {})
        if business:
            result["business_id"] = business.get("id")
            result["seller_name"] = business.get("title", "Noma'lum")
            result["seller_address"] = business.get("address", "Noma'lum")

            # Biznes telefon raqamini olish (businesses API dan, title bo'yicha)
            biz_title = business.get("title", "")
            if biz_title:
                for cached_biz in self._businesses_cache.values():
                    if cached_biz.get("title", "").strip().lower() == biz_title.strip().lower():
                        phone = cached_biz.get("phone_number", "")
                        if phone:
                            result["seller_phone"] = f"+{phone}" if not phone.startswith("+") else phone
                        break

        # Mijoz ma'lumotlari
        user = order.get("user", {})
        if user:
            first_name = user.get("first_name", "")
            last_name = user.get("last_name", "")
            result["client_name"] = f"{first_name} {last_name}".strip() or "Noma'lum"
            result["client_phone"] = user.get("phone", "Noma'lum")

        # Mahsulotlar
        items = order.get("order_item") or order.get("items") or []
        if items:
            first_item = items[0]
            product = first_item.get("product", {})
            result["product_name"] = product.get("name") or product.get("title", "Noma'lum")
            result["quantity"] = first_item.get("count", 1)

        # Lead name format (amoCRM bilan mos)
        result["lead_name"] = f"#{order['id']} | {result['client_name']} | {order.get('payment_method', 'CASH')} | {result['price']}"

        return result

    def reset_known_leads(self):
        """Ko'rilgan buyurtmalar ro'yxatini tozalash"""
        self._known_leads.clear()
        logger.debug("Known leads tozalandi")


class NonborPoller:
    """
    Nonbor API Polling - Real-time kuzatish
    (AmoCRMPoller bilan mos)

    Yangi buyurtmalar va status o'zgarishlarini kuzatadi
    """

    def __init__(
        self,
        nonbor_service: NonborService,
        polling_interval: int = 5,
        on_new_orders: callable = None,
        on_orders_resolved: callable = None
    ):
        self.nonbor = nonbor_service
        self.polling_interval = polling_interval
        self.on_new_orders = on_new_orders
        self.on_orders_resolved = on_orders_resolved

        self._running = False
        self._last_count = 0
        self._last_ids: Set[int] = set()  # Oldingi polling dagi ID lar
        self._task: Optional[asyncio.Task] = None

        logger.info(f"Nonbor Poller yaratildi: {polling_interval}s interval")

    async def start(self):
        """Polling boshlash"""
        if self._running:
            return

        self._running = True

        # Birinchi ishga tushganda bizneslarni cache qilish
        await self.nonbor.get_businesses()

        self._task = asyncio.create_task(self._poll_loop())
        logger.info("Nonbor Polling boshlandi")

    async def stop(self):
        """Polling to'xtatish"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Nonbor Polling to'xtatildi")

    async def _poll_loop(self):
        """Asosiy polling sikli - exponential backoff bilan"""
        while self._running:
            try:
                count, current_ids = await self.nonbor.check_for_new_leads()

                if count is None:
                    # Xatolik — backoff hisoblash (5s, 10s, 20s, 40s, 60s max)
                    errors = self.nonbor._consecutive_errors
                    backoff = min(self.polling_interval * (2 ** min(errors - 1, 4)), 60)

                    # Bo'lakli kutish: har 5s da API ni tekshirib turadi
                    waited = 0
                    while waited < backoff and self._running:
                        await asyncio.sleep(self.polling_interval)
                        waited += self.polling_interval

                        # Har bo'lakda API ni tekshirish
                        test_count, test_ids = await self.nonbor.check_for_new_leads()
                        if test_count is not None:
                            # API tiklandi — darhol normal rejimga qaytish
                            count, current_ids = test_count, test_ids
                            logger.info(f"API tiklandi! Normal rejimga qaytildi ({waited}s da)")
                            break
                    else:
                        # Backoff tugadi, API hali ham ishlamayapti
                        continue

                current_id_set = set(current_ids) if current_ids else set()

                # Faqat ID lar o'zgarganda callback chaqirish
                if current_id_set != self._last_ids:
                    new_ids = current_id_set - self._last_ids
                    removed_ids = self._last_ids - current_id_set

                    # Yangi buyurtmalar keldi
                    if new_ids and self.on_new_orders:
                        await self.on_new_orders(count, list(current_id_set))

                    # Buyurtmalar hal qilindi (status o'zgardi)
                    if removed_ids and self.on_orders_resolved:
                        await self.on_orders_resolved(list(removed_ids), count)

                    self._last_ids = current_id_set

                self._last_count = count

                await asyncio.sleep(self.polling_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Polling xatosi: {e}")
                await asyncio.sleep(self.polling_interval)

    @property
    def current_count(self) -> int:
        """Hozirgi buyurtmalar soni"""
        return self._last_count
