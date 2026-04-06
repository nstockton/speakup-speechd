#!/bin/sh
install -m 755 -o root -g root -D src/speakup_speechd/main.py /usr/local/bin/speakup-speechd
install -m 644 -o root -g root -D extras/speakup-speechd.ini /usr/local/etc/speakup-speechd.ini
install -m 644 -o root -g root -D extras/speakup-speechd.service /usr/local/lib/systemd/system/speakup-speechd.service
echo "Install complete. Run 'systemctl enable speakup-speechd.service --now' to start the service."
