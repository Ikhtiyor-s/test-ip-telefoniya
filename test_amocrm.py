# -*- coding: utf-8 -*-
"""amoCRM ma'lumotlarini tekshirish"""
import asyncio
import os
import json
import sys
sys.stdout.reconfigure(encoding='utf-8')

from dotenv import load_dotenv
load_dotenv()

import aiohttp

async def test():
    subdomain = os.getenv("AMOCRM_SUBDOMAIN", "welltech")
    token = os.getenv("AMOCRM_TOKEN")

    base_url = f"https://{subdomain}.amocrm.ru/api/v4"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    async with aiohttp.ClientSession(headers=headers) as session:
        # Lead olish
        lead_id = 48763381  # Screenshotdagi lead ID

        # Lead ma'lumotlari
        async with session.get(f"{base_url}/leads/{lead_id}", params={"with": "contacts"}) as resp:
            lead_data = await resp.json()
            print("=" * 60)
            print("LEAD MA'LUMOTLARI:")
            print("=" * 60)
            print(json.dumps(lead_data, indent=2, ensure_ascii=False))

        # Notes (izohlar)
        async with session.get(f"{base_url}/leads/{lead_id}/notes") as resp:
            notes_data = await resp.json()
            print("\n" + "=" * 60)
            print("NOTES (IZOHLAR):")
            print("=" * 60)
            print(json.dumps(notes_data, indent=2, ensure_ascii=False))

        # Kontaktlar
        contacts = lead_data.get("_embedded", {}).get("contacts", [])
        for contact in contacts:
            contact_id = contact.get("id")
            async with session.get(f"{base_url}/contacts/{contact_id}") as resp:
                contact_data = await resp.json()
                print("\n" + "=" * 60)
                print(f"KONTAKT {contact_id}:")
                print("=" * 60)
                print(json.dumps(contact_data, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    asyncio.run(test())
