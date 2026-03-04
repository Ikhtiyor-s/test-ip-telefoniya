"""
Dialplan tekshirish
"""

import asyncio

async def main():
    reader, writer = await asyncio.open_connection("172.29.124.85", 5038)

    welcome = await reader.readline()
    print(f"Welcome: {welcome.decode().strip()}")

    # Login
    login_msg = "Action: Login\r\nActionID: 1\r\nUsername: autodialer\r\nSecret: autodialer123\r\n\r\n"
    writer.write(login_msg.encode())
    await writer.drain()

    response = await asyncio.wait_for(reader.read(4096), timeout=5)

    # Dialplan ko'rsatish
    show_cmd = "Action: Command\r\nActionID: 100\r\nCommand: dialplan show autodialer-dynamic\r\n\r\n"
    writer.write(show_cmd.encode())
    await writer.drain()

    await asyncio.sleep(1)
    response = await reader.read(8192)
    print(f"\nDialplan:\n{response.decode()}")

    writer.close()
    await writer.wait_closed()

if __name__ == "__main__":
    asyncio.run(main())
