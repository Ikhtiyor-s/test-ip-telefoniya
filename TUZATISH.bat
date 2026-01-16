@echo off
echo ===============================================
echo DIALPLAN MUAMMOSINI TUZATISH
echo ===============================================
echo.

wsl bash -c "cat > /tmp/extensions_autodialer.conf << 'EOF' && [autodialer-dynamic] && exten =^> _X.,1,NoOp(AutoDialer qongiroq: ${EXTEN}) && exten =^> _X.,n,Wait(1) && exten =^> _X.,n,Playback(${AUDIO_FILE}) && exten =^> _X.,n,Wait(2) && exten =^> _X.,n,Hangup() && EOF && sudo cp /tmp/extensions_autodialer.conf /etc/asterisk/ && echo '#include \"extensions_autodialer.conf\"' | sudo tee -a /etc/asterisk/extensions.conf && sudo asterisk -rx 'dialplan reload' && echo 'Dialplan yangilandi!' && sudo asterisk -rx 'dialplan show autodialer-dynamic'"

echo.
echo ===============================================
echo TAYYOR! Endi autodialer ni qayta ishga tushiring
echo ===============================================
pause
