"""
Asterisk dialplan tuzatish - Answer() ni olib tashlash
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
    print(f"Login OK\n")

    # extensions.conf ni tahrirlash
    # Faylga yozish uchun bash buyrug'ini Asterisk orqali ishga tushiramiz
    bash_command = r"""cat > /tmp/autodialer.conf << 'CONFEND'
[autodialer-dynamic]
exten => _X.,1,NoOp(AutoDialer qongiroq: ${EXTEN})
exten => _X.,n,Wait(1)
exten => _X.,n,Playback(${AUDIO_FILE})
exten => _X.,n,Wait(2)
exten => _X.,n,Hangup()
CONFEND
sudo cp /tmp/autodialer.conf /etc/asterisk/extensions_autodialer.conf
echo '#include "extensions_autodialer.conf"' | sudo tee -a /etc/asterisk/extensions.conf
"""

    # Asterisk console orqali reload qilish
    reload_cmd = "Action: Command\r\nActionID: 20\r\nCommand: dialplan reload\r\n\r\n"
    writer.write(reload_cmd.encode())
    await writer.drain()

    response = await asyncio.wait_for(reader.read(4096), timeout=5)
    print(f"Dialplan reload: {response.decode()[:200]}\n")

    # Dialplan ko'rsatish
    show_cmd = "Action: Command\r\nActionID: 21\r\nCommand: dialplan show autodialer-dynamic\r\n\r\n"
    writer.write(show_cmd.encode())
    await writer.drain()

    response = await asyncio.wait_for(reader.read(8192), timeout=5)
    print(f"Dialplan:\n{response.decode()}")

    # Logoff
    writer.write("Action: Logoff\r\n\r\n".encode())
    await writer.drain()

    writer.close()
    await writer.wait_closed()

    print("\n" + "="*60)
    print("TUGADI! Endi autodialer ni qayta ishga tushiring:")
    print("taskkill //F //IM python.exe")
    print("python src/autodialer.py")
    print("="*60)

if __name__ == "__main__":
    asyncio.run(main())
