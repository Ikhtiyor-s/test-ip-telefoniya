# -*- coding: utf-8 -*-
"""Parse test"""
import asyncio
import os
import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, 'src')

from dotenv import load_dotenv
load_dotenv()

from services.amocrm_service import AmoCRMService

async def test():
    amocrm = AmoCRMService(
        subdomain=os.getenv("AMOCRM_SUBDOMAIN", "welltech"),
        access_token=os.getenv("AMOCRM_TOKEN"),
        status_name="TEKSHIRILMOQDA"
    )

    lead_id = 48763381
    data = await amocrm.get_order_full_data(lead_id)

    print("=" * 60)
    print("PARSED DATA:")
    print("=" * 60)
    for key, value in data.items():
        print(f"{key}: {value}")

    await amocrm.close()

if __name__ == "__main__":
    asyncio.run(test())
