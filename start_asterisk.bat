@echo off
echo Starting WSL and Asterisk...
wsl -d Ubuntu -- sudo service asterisk start
echo Asterisk started!
wsl -d Ubuntu -- tail -f /dev/null
