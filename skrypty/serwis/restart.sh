#!/bin/bash
# Restart mikroserwisu BEZ ubijania innych procesow Pythona.
#
# Wczesniej uzywalem "taskkill /F /IM python.exe", ktore zabija wszystko -
# w tym wielogodzinne liczenie w tle. Zdarzylo sie to raz i kosztowalo
# godzine. Tu ubijamy wylacznie proces trzymajacy port 8000.
#
# Uzycie:
#   bash skrypty/serwis/restart.sh           tylko ten komputer
#   bash skrypty/serwis/restart.sh --siec    takze inne urzadzenia w sieci
PORT=8000
ARG=""
[ "$1" = "--siec" ] && ARG="--siec"

PID=$(netstat -ano 2>/dev/null | grep ":$PORT " | grep LISTENING | awk '{print $NF}' | head -1)
if [ -n "$PID" ]; then
  taskkill //F //PID "$PID" > /dev/null 2>&1 && echo "zatrzymano serwis (PID $PID)"
fi
cd "$(dirname "$0")/../.." || exit 1
nohup bash -c "PYTHONIOENCODING=utf-8 PYTHONUNBUFFERED=1 \"C:/Users/kacpe/miniconda3/python.exe\" skrypty/serwis/serwis.py $ARG" > wyniki/log_serwis.txt 2>&1 &
sleep 10
curl -s -o /dev/null -w "serwis: HTTP %{http_code}\n" "http://127.0.0.1:$PORT/zdrowie"
grep "http://" wyniki/log_serwis.txt | sed 's/^/  /'
