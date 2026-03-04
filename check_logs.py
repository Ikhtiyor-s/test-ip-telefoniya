"""
Asterisk loglarini tekshirish
"""

import asyncio

async def main():
    reader, writer = await asyncio.open_connection("172.29.124.85", 5038)

    welcome = await reader.readline()

    # Login
    login_msg = "Action: Login\r\nActionID: 1\r\nUsername: autodialer\r\nSecret: autodialer123\r\n\r\n"
    writer.write(login_msg.encode())
    await writer.drain()

    await asyncio.wait_for(reader.read(4096), timeout=5)

    # So'nggi loglarni ko'rish
    log_cmd = "Action: Command\r\nActionID: 50\r\nCommand: core show channels verbose\r\n\r\n"
    writer.write(log_cmd.encode())
    await writer.drain()

    await asyncio.sleep(1)
    response = await reader.read(8192)
    print(f"Active channels:\n{response.decode()}")

    # Sounds directory
    sound_cmd = "Action: Command\r\nActionID: 51\r\nCommand: core show config /tmp/autodialer\r\n\r\n"
    writer.write(sound_cmd.encode())
    await writer.drain()

    await asyncio.sleep(1)
    response = await reader.read(8192)
    print(f"\nSounds check:\n{response.decode()}")

    writer.close()
    await writer.wait_closed()

if __name__ == "__main__":
    asyncio.run(main())
