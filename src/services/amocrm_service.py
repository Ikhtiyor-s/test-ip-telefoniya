"""
amoCRM Integratsiya Servisi
Buyurtmalarni kuzatish va boshqarish
"""

import logging
import aiohttp
import asyncio
from typing import List, Dict, Optional, Set
from datetime import datetime

logger = logging.getLogger(__name__)


class AmoCRMService:
    """
    amoCRM bilan ishlash servisi

    Funksiyalar:
    - Yangi buyurtmalarni kuzatish (TEKSHIRILMOQDA status)
    - Buyurtmalar sonini olish
    - Status o'zgarishlarini kuzatish
    """

    def __init__(
        self,
        subdomain: str,
        access_token: str,
        status_name: str = "TEKSHIRILMOQDA"
    ):
        self.subdomain = subdomain
        self.access_token = access_token
        self.status_name = status_name
        self.base_url = f"https://{subdomain}.amocrm.ru/api/v4"
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }

        # Cache
        self._pipeline_id: Optional[int] = None
        self._status_id: Optional[int] = None
        self._known_leads: Set[int] = set()  # Ko'rilgan leadlar
        self._session: Optional[aiohttp.ClientSession] = None

        logger.info(f"amoCRM servisi ishga tushdi: {subdomain}")

    async def _get_session(self) -> aiohttp.ClientSession:
        """HTTP session olish"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(headers=self.headers)
        return self._session

    async def close(self):
        """Sessionni yopish"""
        if self._session and not self._session.closed:
            await self._session.close()

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        params: dict = None,
        json_data: dict = None
    ) -> Optional[dict]:
        """API so'rov yuborish"""
        session = await self._get_session()
        url = f"{self.base_url}/{endpoint}"

        try:
            async with session.request(
                method,
                url,
                params=params,
                json=json_data
            ) as response:
                if response.status == 200:
                    return await response.json()
                elif response.status == 204:
                    return {}
                elif response.status == 401:
                    logger.error("amoCRM: Token yaroqsiz (401)")
                    return None
                else:
                    text = await response.text()
                    logger.error(f"amoCRM xatosi: {response.status} - {text}")
                    return None

        except aiohttp.ClientError as e:
            logger.error(f"amoCRM ulanish xatosi: {e}")
            return None

    async def get_pipeline_and_status(self) -> bool:
        """
        Pipeline va status ID larni olish
        TEKSHIRILMOQDA statusini topish
        """
        if self._pipeline_id and self._status_id:
            return True

        data = await self._make_request("GET", "leads/pipelines")
        if not data:
            return False

        pipelines = data.get("_embedded", {}).get("pipelines", [])

        for pipeline in pipelines:
            statuses = pipeline.get("_embedded", {}).get("statuses", [])
            for status in statuses:
                # TEKSHIRILMOQDA yoki shunga o'xshash statusni qidirish
                if self.status_name.upper() in status.get("name", "").upper():
                    self._pipeline_id = pipeline.get("id")
                    self._status_id = status.get("id")
                    logger.info(
                        f"Pipeline topildi: {pipeline.get('name')} (ID: {self._pipeline_id}), "
                        f"Status: {status.get('name')} (ID: {self._status_id})"
                    )
                    return True

        logger.error(f"'{self.status_name}' statusi topilmadi")
        return False

    async def get_leads_by_status(self) -> List[Dict]:
        """
        TEKSHIRILMOQDA statusidagi barcha leadlarni olish

        Returns:
            Leadlar ro'yxati yoki None agar xato yuz bergan bo'lsa
        """
        try:
            if not await self.get_pipeline_and_status():
                return []

            params = {
                "filter[statuses][0][pipeline_id]": self._pipeline_id,
                "filter[statuses][0][status_id]": self._status_id,
                "limit": 250,
                "order[created_at]": "desc"
            }

            data = await self._make_request("GET", "leads", params=params)
            if not data:
                # MUHIM: Agar request xato bo'lsa, None qaytarish ([] emas!)
                # [] - buyurtmalar yo'q, None - xato yuz bergan
                return None

            leads = data.get("_embedded", {}).get("leads", [])
            logger.debug(f"TEKSHIRILMOQDA leadlar: {len(leads)} ta")

            return leads
        except Exception as e:
            logger.error(f"get_leads_by_status xatosi: {e}")
            # Xato yuz berganda None qaytarish
            return None

    async def get_pending_orders_count(self) -> int:
        """
        TEKSHIRILMOQDA dagi buyurtmalar sonini olish

        Returns:
            Buyurtmalar soni
        """
        leads = await self.get_leads_by_status()
        return len(leads)

    async def check_for_new_leads(self) -> tuple[int, List[int]]:
        """
        Yangi leadlarni tekshirish

        Returns:
            (jami_soni, barcha_hozirgi_lead_idlar) or (None, None) agar xato yuz bergan bo'lsa
            DIQQAT: Ikkinchi qiymat BARCHA hozirgi leadlar, faqat yangi emas!
        """
        try:
            leads = await self.get_leads_by_status()

            # MUHIM: Agar xato yuz bergan bo'lsa (None qaytgan), None qaytarish
            # Bu internet uzilib qolgan yoki boshqa xatolarni handle qiladi
            if leads is None:
                return None, None

            current_ids = {lead["id"] for lead in leads}

            # Yangi leadlar (faqat log uchun)
            new_ids = current_ids - self._known_leads

            # Cache yangilash
            self._known_leads = current_ids

            if new_ids:
                logger.info(f"Yangi leadlar: {len(new_ids)} ta, Jami: {len(leads)} ta")

            # BARCHA hozirgi lead IDlarni qaytarish (faqat yangi emas!)
            return len(leads), list(current_ids)
        except Exception as e:
            logger.error(f"check_for_new_leads xatosi: {e}")
            # Xato yuz berganda None qaytarish - bu poller tomonidan handle qilinadi
            return None, None

    async def check_status_changed(self) -> bool:
        """
        Status o'zgarganmi tekshirish
        (TEKSHIRILMOQDA dan boshqa statusga o'tganmi)

        Returns:
            True agar kamida 1 ta lead status o'zgartirgan bo'lsa
        """
        leads = await self.get_leads_by_status()
        current_ids = {lead["id"] for lead in leads}

        # Oldingi leadlardan qaysi biri yo'qoldi
        removed_ids = self._known_leads - current_ids

        if removed_ids:
            logger.info(f"Status o'zgargan leadlar: {len(removed_ids)} ta")
            self._known_leads = current_ids
            return True

        return False

    async def get_lead_details(self, lead_id: int) -> Optional[Dict]:
        """Lead to'liq ma'lumotlarini olish"""
        params = {"with": "contacts"}
        data = await self._make_request("GET", f"leads/{lead_id}", params=params)
        return data

    async def get_responsible_user(self, user_id: int) -> Optional[Dict]:
        """Mas'ul foydalanuvchi ma'lumotlarini olish"""
        data = await self._make_request("GET", f"users/{user_id}")
        return data

    async def get_contact(self, contact_id: int) -> Optional[Dict]:
        """Kontakt ma'lumotlarini olish"""
        data = await self._make_request("GET", f"contacts/{contact_id}")
        return data

    async def get_lead_notes(self, lead_id: int) -> List[Dict]:
        """Lead izohlarini olish"""
        data = await self._make_request("GET", f"leads/{lead_id}/notes")
        if not data:
            return []
        return data.get("_embedded", {}).get("notes", [])

    def _parse_note_text(self, text: str) -> Dict:
        """Note matnidan ma'lumotlarni ajratib olish"""
        result = {
            "seller_name": None,
            "seller_phone": None,
            "seller_address": None,
            "client_username": None,
            "product_name": None,
            "quantity": None,
            "order_price": None
        }

        import re

        # BIZNES bo'limini topish - FAQAT birinchi qator
        biznes_match = re.search(r'BIZNES:\s*\n\s*Nomi:\s*([^\n]+)', text)
        if biznes_match:
            result["seller_name"] = biznes_match.group(1).strip()

        # Tel raqam - FAQAT birinchi qator
        tel_match = re.search(r'BIZNES:[^\n]*\n[^\n]*\n\s*Tel:\s*(\d+)', text)
        if tel_match:
            result["seller_phone"] = tel_match.group(1).strip()

        # Manzil - FAQAT birinchi qator (MUHIM!)
        manzil_match = re.search(r'Manzil:\s*([^\n]+)', text)
        if manzil_match:
            result["seller_address"] = manzil_match.group(1).strip()

        # MIJOZ bo'limini topish - FAQAT birinchi qator
        mijoz_match = re.search(r'MIJOZ:\s*\n\s*Username:\s*([^\n]+)', text)
        if mijoz_match:
            result["client_username"] = mijoz_match.group(1).strip()

        # MAHSULOTLAR - FAQAT birinchi mahsulot
        product_match = re.search(r'MAHSULOTLAR:\s*\n\s*\d+\.\s*([^\n]+)', text)
        if product_match:
            result["product_name"] = product_match.group(1).strip()

        # Miqdor - FAQAT birinchi qiymat
        quantity_match = re.search(r'Miqdor:\s*(\d+)\s*ta', text)
        if quantity_match:
            result["quantity"] = int(quantity_match.group(1))

        # Narx - FAQAT birinchi qiymat
        price_match = re.search(r'Narx:\s*([\d\s]+)\s*so', text)
        if price_match:
            result["order_price"] = int(price_match.group(1).replace(" ", "").replace("\xa0", ""))

        return result

    async def get_order_full_data(self, lead_id: int) -> Dict:
        """
        Buyurtma uchun to'liq ma'lumotlarni olish

        Returns:
            dict: {
                lead_id, lead_name, seller_name, seller_phone, seller_address,
                client_name, client_phone, product_name, quantity, price
            }
        """
        result = {
            "lead_id": lead_id,
            "lead_name": "Noma'lum",
            "seller_name": "Noma'lum",
            "seller_phone": "Noma'lum",
            "seller_address": "Noma'lum",
            "client_name": "Noma'lum",
            "client_phone": "Noma'lum",
            "product_name": "Noma'lum",
            "quantity": 1,
            "price": 0
        }

        # Lead ma'lumotlari
        lead_data = await self.get_lead_details(lead_id)
        if not lead_data:
            return result

        result["lead_name"] = lead_data.get("name", "Noma'lum")
        result["price"] = lead_data.get("price", 0)

        # Lead nomidan buyurtma raqamini ajratib olish
        # Format: "#1570 | Bekzod Usarov | CASH | 1 010 000"
        import re
        lead_name = result["lead_name"]
        order_num_match = re.search(r'#(\d+)', lead_name)
        if order_num_match:
            result["order_number"] = order_num_match.group(1)
        else:
            result["order_number"] = str(lead_id)  # Fallback - lead_id

        # NOTE dan ma'lumotlarni olish
        notes = await self.get_lead_notes(lead_id)
        for note in notes:
            note_type = note.get("note_type")
            if note_type == "common":
                text = note.get("params", {}).get("text", "")
                if text:
                    parsed = self._parse_note_text(text)
                    if parsed["seller_name"]:
                        result["seller_name"] = parsed["seller_name"]
                    if parsed["seller_phone"]:
                        result["seller_phone"] = parsed["seller_phone"]
                    if parsed["seller_address"]:
                        result["seller_address"] = parsed["seller_address"]
                    if parsed["product_name"]:
                        result["product_name"] = parsed["product_name"]
                    if parsed["quantity"]:
                        result["quantity"] = parsed["quantity"]
                    if parsed["order_price"]:
                        result["price"] = parsed["order_price"]
                    if parsed["client_username"]:
                        result["client_phone"] = parsed["client_username"]
                break  # Birinchi note dan olish

        # Kontaktlar - mijoz ismini olish
        contacts = lead_data.get("_embedded", {}).get("contacts", [])
        for contact_link in contacts:
            contact_id = contact_link.get("id")
            if not contact_id:
                continue

            contact_data = await self.get_contact(contact_id)
            if not contact_data:
                continue

            contact_name = contact_data.get("name", "")
            if contact_name:
                result["client_name"] = contact_name

            # Kontaktdan telefon
            custom_fields_contact = contact_data.get("custom_fields_values", [])
            for field in custom_fields_contact or []:
                if field.get("field_code") == "PHONE":
                    values = field.get("values", [])
                    if values:
                        phone = values[0].get("value", "")
                        if phone and result["client_phone"] == "Noma'lum":
                            result["client_phone"] = phone
                        break

        return result

    def reset_known_leads(self):
        """Ko'rilgan leadlar ro'yxatini tozalash"""
        self._known_leads.clear()
        logger.debug("Known leads tozalandi")


class AmoCRMPoller:
    """
    amoCRM Polling - Real-time kuzatish

    Yangi buyurtmalar va status o'zgarishlarini kuzatadi
    """

    def __init__(
        self,
        amocrm_service: AmoCRMService,
        polling_interval: int = 3,
        on_new_orders: callable = None,
        on_orders_resolved: callable = None
    ):
        self.amocrm = amocrm_service
        self.polling_interval = polling_interval
        self.on_new_orders = on_new_orders
        self.on_orders_resolved = on_orders_resolved

        self._running = False
        self._last_count = 0
        self._task: Optional[asyncio.Task] = None

        logger.info(f"amoCRM Poller yaratildi: {polling_interval}s interval")

    async def start(self):
        """Polling boshlash"""
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._poll_loop())
        logger.info("amoCRM Polling boshlandi")

    async def stop(self):
        """Polling to'xtatish"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("amoCRM Polling to'xtatildi")

    async def _poll_loop(self):
        """Asosiy polling sikli"""
        while self._running:
            try:
                count, new_ids = await self.amocrm.check_for_new_leads()

                # MUHIM: Faqat muvaffaqiyatli so'rovdan keyin count ni yangilash
                # Agar count None bo'lsa (xato yuz bergan), o'tkazib yuborish
                if count is None:
                    await asyncio.sleep(self.polling_interval)
                    continue

                # Yangi buyurtmalar keldi
                if new_ids and self.on_new_orders:
                    await self.on_new_orders(count, new_ids)

                # Buyurtmalar kamaydi (status o'zgardi)
                # MUHIM: Faqat count < self._last_count bo'lganda va _last_count > 0 bo'lganda
                # Bu internet uzilib qolgan holatda xato triggered bo'lishini oldini oladi
                if self._last_count > 0 and count < self._last_count and self.on_orders_resolved:
                    resolved_count = self._last_count - count
                    await self.on_orders_resolved(resolved_count, count)

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
