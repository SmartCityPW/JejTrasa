"""Pozycja Słońca (algorytm NOAA) - wschód, zachód i "poziom dziennego światła".

Zamiast sztywnego progu dzień/noc używamy wysokości Słońca nad horyzontem:
światło dzienne płynnie zanika w trakcie zmierzchu cywilnego (od +6° do -6°).
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone


def _julian_day(dt_utc: datetime) -> float:
    return dt_utc.timestamp() / 86400.0 + 2440587.5


def solar_elevation(dt: datetime, lat: float, lon: float) -> float:
    """Wysokość Słońca w stopniach dla świadomego strefy czasowej `dt`."""
    dt_utc = dt.astimezone(timezone.utc)
    jc = (_julian_day(dt_utc) - 2451545.0) / 36525.0
    geom_mean_long = (280.46646 + jc * (36000.76983 + jc * 0.0003032)) % 360
    geom_mean_anom = 357.52911 + jc * (35999.05029 - 0.0001537 * jc)
    ecc = 0.016708634 - jc * (0.000042037 + 0.0000001267 * jc)
    m = math.radians(geom_mean_anom)
    eq_ctr = (math.sin(m) * (1.914602 - jc * (0.004817 + 0.000014 * jc))
              + math.sin(2 * m) * (0.019993 - 0.000101 * jc) + math.sin(3 * m) * 0.000289)
    true_long = geom_mean_long + eq_ctr
    omega = 125.04 - 1934.136 * jc
    app_long = true_long - 0.00569 - 0.00478 * math.sin(math.radians(omega))
    mean_obliq = 23 + (26 + ((21.448 - jc * (46.815 + jc * (0.00059 - jc * 0.001813)))) / 60) / 60
    obliq = mean_obliq + 0.00256 * math.cos(math.radians(omega))
    decl = math.degrees(math.asin(math.sin(math.radians(obliq)) * math.sin(math.radians(app_long))))
    y = math.tan(math.radians(obliq / 2)) ** 2
    l0 = math.radians(geom_mean_long)
    eq_time = 4 * math.degrees(
        y * math.sin(2 * l0) - 2 * ecc * math.sin(m) + 4 * ecc * y * math.sin(m) * math.cos(2 * l0)
        - 0.5 * y * y * math.sin(4 * l0) - 1.25 * ecc * ecc * math.sin(2 * m)
    )
    minutes = dt_utc.hour * 60 + dt_utc.minute + dt_utc.second / 60
    true_solar = (minutes + eq_time + 4 * lon) % 1440
    hour_angle = true_solar / 4 - 180
    zen = math.degrees(math.acos(
        math.sin(math.radians(lat)) * math.sin(math.radians(decl))
        + math.cos(math.radians(lat)) * math.cos(math.radians(decl)) * math.cos(math.radians(hour_angle))
    ))
    return 90 - zen


def daylight_factor(dt: datetime, lat: float, lon: float) -> float:
    """1.0 = pełny dzień, 0.0 = noc; liniowo w zakresie wysokości Słońca -6°..+6°."""
    elev = solar_elevation(dt, lat, lon)
    return max(0.0, min(1.0, (elev + 6) / 12))


def _crossing(day_start: datetime, lat: float, lon: float, target: float, rising: bool) -> datetime | None:
    step = timedelta(minutes=5)
    t = day_start
    prev = solar_elevation(t, lat, lon)
    for _ in range(288):
        t2 = t + step
        cur = solar_elevation(t2, lat, lon)
        if (rising and prev < target <= cur) or (not rising and prev > target >= cur):
            frac = (target - prev) / (cur - prev)
            return t + step * frac
        t, prev = t2, cur
    return None


def sun_times(dt: datetime, lat: float, lon: float) -> dict:
    day_start = dt.replace(hour=0, minute=0, second=0, microsecond=0)
    return {
        "sunrise": _crossing(day_start, lat, lon, -0.833, True),
        "sunset": _crossing(day_start, lat, lon, -0.833, False),
        "dawn": _crossing(day_start, lat, lon, -6, True),
        "dusk": _crossing(day_start, lat, lon, -6, False),
    }
