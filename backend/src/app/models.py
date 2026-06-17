from datetime import date

from pydantic import BaseModel


class StationInfo(BaseModel):
    station_id: str
    station_name: str
    area_ha: float | None = None


class CellAtPoint(StationInfo):
    pass


class MeteoSeriesPoint(BaseModel):
    date: date
    t_min: float | None = None
    t_max: float | None = None
    t_mean: float | None = None
    gdd_daily: float | None = None
    gdd_cumulative: float | None = None
    precip_mm: float | None = None


class MeteoSeries(BaseModel):
    station_id: str
    station_name: str
    year: int
    plant_id: str
    points: list[MeteoSeriesPoint]


class MeteoMonthlyPoint(BaseModel):
    month: int
    t_mean: float | None = None
    gdd_monthly: float | None = None
    gdd_cumulative: float | None = None
    precip_mm: float | None = None


class MeteoMonthlySummary(BaseModel):
    station_id: str
    station_name: str
    year: int
    plant_id: str
    day_count: int
    t_mean_annual: float | None = None
    gdd_max: float | None = None
    precip_annual: float | None = None
    months: list[MeteoMonthlyPoint]


class BloomStatus(BaseModel):
    station_id: str
    station_name: str | None = None
    date: date
    plant_id: str
    plant_name: str
    gdd_cumulative: float
    bloom_day: int
    bloom_phase: str
    bloom_phase_label: str
    gdd_min: float
    gdd_max: float
