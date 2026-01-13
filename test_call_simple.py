"""
Oddiy test qo'ng'iroq - audio tekshirish
"""

import asyncio
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from services import AsteriskAMI

async def main():
    # AMI ulanish
    ami = AsteriskAMI(
        host="172.29.124.85",
        port=5038,
        username="autodialer",
        password="autodialer123"
    )

    connected = await ami.connect()
    if not connected:
        print("AMI ulanish xatosi!")
        return

    print("AMI ulandi!")

    # Audio fayl - 1 ta buyurtma uchun
    # Matn: "Assalomu alaykum, men nonbor ovozli bot xizmatiman, sizda 1 ta buyurtma bor, iltimos, buyurtmangizni tekshiring."
    audio_file = "3f5f652ef7c02fd28a6d14c9aabc5952"  # 1 ta buyurtma hash

    # Qo'ng'iroq
    result = await ami.originate_call(
        phone_number="+998505019800",
        audio_file=audio_file
    )

    print(f"Qo'ng'iroq natijasi: {result}")

    # Kutish
    await asyncio.sleep(30)

    await ami.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
