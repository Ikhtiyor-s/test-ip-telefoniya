"""
Asterisk dialplan yaratish - AMI orqali
"""

import asyncio

async def main():
    # AMI ga ulanish
    reader, writer = await asyncio.open_connection("172.29.124.85", 5038)

    # Welcome
    welcome = await reader.readline()
    print(f"Welcome: {welcome.decode().strip()}")

    # Login
    login_msg = "Action: Login\r\nActionID: 1\r\nUsername: autodialer\r\nSecret: autodialer123\r\n\r\n"
    writer.write(login_msg.encode())
    await writer.drain()

    # Login response
    response = await asyncio.wait_for(reader.read(4096), timeout=5)
    print(f"Login response: {response.decode()}")

    # Dialplan yaratish - Command orqali
    dialplan_commands = [
        "dialplan remove context autodialer-dynamic",
        'dialplan add extension _X.,1,NoOp(AutoDialer) into autodialer-dynamic',
        'dialplan add extension _X.,2,Answer() into autodialer-dynamic',
        'dialplan add extension _X.,3,Wait(1) into autodialer-dynamic',
        'dialplan add extension _X.,4,Playback(${AUDIO_FILE}) into autodialer-dynamic',
        'dialplan add extension _X.,5,Wait(2) into autodialer-dynamic',
        'dialplan add extension _X.,6,Hangup() into autodialer-dynamic',
    ]

    for i, cmd in enumerate(dialplan_commands, start=10):
        action = f"Action: Command\r\nActionID: {i}\r\nCommand: {cmd}\r\n\r\n"
        writer.write(action.encode())
        await writer.drain()

        response = await asyncio.wait_for(reader.read(4096), timeout=5)
        print(f"Command '{cmd[:50]}': {response.decode().strip()[:100]}")

    # Dialplan ko'rsatish
    show_cmd = "Action: Command\r\nActionID: 100\r\nCommand: dialplan show autodialer-dynamic\r\n\r\n"
    writer.write(show_cmd.encode())
    await writer.drain()

    response = await asyncio.wait_for(reader.read(4096), timeout=5)
    print(f"\nDialplan:\n{response.decode()}")

    # Logoff
    writer.write("Action: Logoff\r\n\r\n".encode())
    await writer.drain()

    writer.close()
    await writer.wait_closed()

if __name__ == "__main__":
    asyncio.run(main())
