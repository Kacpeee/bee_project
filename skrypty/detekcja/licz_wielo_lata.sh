#!/usr/bin/env bash
# Nadzorca liczenia map wstecz.
#
# PO CO
# wielo_lata.py potrafi paść z powodów niezależnych od danych: chwilowy błąd
# Earth Engine, zerwana sieć, blokada pliku na Windows. Bez nadzorcy proces
# stoi wtedy martwy do rana - tak straciliśmy jedną noc, mimo że każdy kafel
# był zapisany i wystarczyło uruchomić skrypt ponownie.
#
# Skrypt jest wznawialny z natury (kafle na dysku, blokada PID), więc restart
# jest bezpieczny: dolicza od miejsca przerwania.
#
# Uruchomienie:
#     bash skrypty/detekcja/licz_wielo_lata.sh

cd "$(dirname "$0")/../.." || exit 1
PY="C:/Users/kacpe/miniconda3/python.exe"
LOG="wyniki/log_wielo_lata.txt"
MAX=40

for i in $(seq 1 $MAX); do
    echo "=== podejscie $i/$MAX, $(date '+%H:%M:%S') ===" >> "$LOG"
    PYTHONIOENCODING=utf-8 "$PY" -u skrypty/detekcja/wielo_lata.py >> "$LOG" 2>&1
    kod=$?
    if grep -q "KONIEC" "$LOG"; then
        echo "=== ZAKONCZONE po $i podejsciach ===" >> "$LOG"
        exit 0
    fi
    # blokada zostaje po zabitym procesie - zwalniamy, bo to my go pilnujemy
    rm -f wyniki/cache/wielo_lata.lock
    echo "=== padlo (kod $kod), restart za 60 s ===" >> "$LOG"
    sleep 60
done
echo "=== poddaje sie po $MAX podejsciach ===" >> "$LOG"
