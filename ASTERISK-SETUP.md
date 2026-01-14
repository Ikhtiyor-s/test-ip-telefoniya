# Asterisk Dialplan O'rnatish

## Muammo
Audio xabar to'liq eshitilmaydi - foydalanuvchi DTMF tugmasi bosganda yoki timeout tugaganda to'xtatiladi.

## Yechim

### 1. Asterisk extensions.conf ni tahrirlash

```bash
sudo nano /etc/asterisk/extensions.conf
```

### 2. Quyidagi konfiguratsiyani qo'shing:

```asterisk
[autodialer-dynamic]
; Qo'ng'iroq boshlanishi
exten => s,1,NoOp(=== Autodialer Call Starting ===)
    same => n,Answer()
    same => n,Wait(1)
    
    ; DTMF timeout ni o'chirish
    same => n,Set(TIMEOUT(digit)=0)
    same => n,Set(TIMEOUT(response)=20)
    
    ; Audio ni to'liq ijro etish (DTMF ni ignore qiladi)
    same => n,Playback(${AUDIO_FILE},noanswer)
    
    ; Audio tugagandan keyin kutish
    same => n,Wait(3)
    
    ; Tugash
    same => n,NoOp(=== Autodialer Call Completed ===)
    same => n,Hangup()

exten => h,1,NoOp(=== Call Ended ===)
```

### 3. Asterisk ni qayta yuklash

```bash
sudo asterisk -rx "dialplan reload"
```

yoki

```bash
sudo systemctl restart asterisk
```

### 4. Tekshirish

```bash
sudo asterisk -rx "dialplan show autodialer-dynamic"
```

## Muhim parametrlar

- `noanswer` - DTMF tugmasi bosilsa ham audio davom etadi
- `TIMEOUT(digit)=0` - DTMF kutmaslik
- `TIMEOUT(response)=20` - maksimal 20 soniya
- `Wait(3)` - audio tugagandan keyin 3 soniya kutish

## Audio fayl formati

- Format: WAV (PCM 16-bit)
- Sample rate: 8000 Hz
- Channels: 1 (mono)
- Location: /tmp/autodialer/

## Test qilish

Qo'ng'iroq qilish va audio to'liq eshitilishini tekshirish:

```bash
tail -f /var/log/asterisk/messages
```
