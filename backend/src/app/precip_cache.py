"""Odczyt opadow z lokalnego cache (data/precip_cache/) — bez HTTP w runtime."""

from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path

CACHE_DIR = Path(os.getenv("PRECIP_CACHE_DIR", "/data/precip_cache"))


def read_precip_cache(station_id: str, year: int) -> dict[date, float]:
    path = CACHE_DIR / f"{station_id}_{year}.json"
    if not path.is_file():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {date.fromisoformat(k): float(v) for k, v in raw.items()}


def monthly_precip_sum(station_id: str, year: int) -> dict[int, float]:
    daily = read_precip_cache(station_id, year)
    monthly: dict[int, float] = {}
    for day, mm in daily.items():
        monthly[day.month] = monthly.get(day.month, 0.0) + mm
    return monthly
