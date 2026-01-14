"""
Eski Telegram xabarlarni o'chirish scripti
===========================================

Telegram guruhdan eski xabarlarni o'chirish uchun.
Xabar ID larini qo'lda kiritish kerak.
"""

import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv

# .env yuklash
load_dotenv(Path(__file__).parent / ".env")

from src.services.telegram_service import TelegramService


async def cleanup_old_messages():
    """Eski xabarlarni o'chirish"""

    # Telegram service yaratish
    telegram = TelegramService(
        bot_token=os.getenv("TELEGRAM_BOT_TOKEN"),
        default_chat_id=os.getenv("TELEGRAM_CHAT_ID")
    )

    # Xabar ID larini kiriting (Telegram guruhdan olgan ID lar)
    # Masalan: message_ids = [123, 124, 125, 126, 127, 128, 129, 130, 131, 132, 133, 134]
    message_ids = [
        # Bu yerga Telegram guruhdan ko'rgan xabar ID larini qo'shing
        # Har bir ID yangi qatorda bo'lishi mumkin
    ]

    if not message_ids:
        print("❌ Xabar ID lari kiritilmagan!")
        print("Script faylini o'zgartiring va message_ids ro'yxatiga ID lar qo'shing.")
        return

    print(f"🗑️  {len(message_ids)} ta xabarni o'chirish boshlandi...")

    deleted_count = 0
    failed_count = 0

    for msg_id in message_ids:
        try:
            success = await telegram.delete_message(msg_id)
            if success:
                print(f"✅ Xabar #{msg_id} o'chirildi")
                deleted_count += 1
            else:
                print(f"❌ Xabar #{msg_id} o'chirilmadi")
                failed_count += 1
        except Exception as e:
            print(f"❌ Xabar #{msg_id} o'chirishda xato: {e}")
            failed_count += 1

        # Telegram API rate limit uchun kichik pauza
        await asyncio.sleep(0.5)

    print(f"\n📊 Natija:")
    print(f"   ✅ O'chirildi: {deleted_count} ta")
    print(f"   ❌ Muvaffaqiyatsiz: {failed_count} ta")
    print(f"   📝 Jami: {len(message_ids)} ta")


if __name__ == "__main__":
    asyncio.run(cleanup_old_messages())
