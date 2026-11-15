"""Consumi annui per fascia F1/F2/F3 dalle statistiche orarie del recorder."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

ROMA = ZoneInfo("Europe/Rome")
GIORNI_MINIMI = 14


def pasqua(anno: int) -> date:
    """Domenica di Pasqua (algoritmo gregoriano anonimo)."""
    a, b, c = anno % 19, anno // 100, anno % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mese = (h + l - 7 * m + 114) // 31
    giorno = (h + l - 7 * m + 114) % 31 + 1
    return date(anno, mese, giorno)


def festivo(d: date) -> bool:
    if (d.month, d.day) in {(1, 1), (1, 6), (4, 25), (5, 1), (6, 2), (8, 15), (11, 1), (12, 8), (12, 25), (12, 26)}:
        return True
    return d == pasqua(d.year) + timedelta(days=1)


def fascia(t: datetime) -> str:
    """Fascia oraria ARERA dell'ora che inizia in t (ora locale italiana)."""
    t = t.astimezone(ROMA)
    h, wd = t.hour, t.weekday()
    if wd == 6 or festivo(t.date()):
        return "F3"
    if wd == 5:
        return "F2" if 7 <= h < 23 else "F3"
    if 8 <= h < 19:
        return "F1"
    if h == 7 or 19 <= h < 23:
        return "F2"
    return "F3"


def per_fascia(righe: list[tuple[datetime, float]]) -> tuple[dict[str, float], float]:
    """Somma i consumi orari per fascia e li porta su base annua.

    Ritorna (kWh/anno per fascia, giorni di dati usati).
    """
    tot = {"F1": 0.0, "F2": 0.0, "F3": 0.0}
    if not righe:
        return tot, 0.0
    for t, kwh in righe:
        if kwh and kwh > 0:
            tot[fascia(t)] += kwh
    inizio = min(t for t, _ in righe)
    fine = max(t for t, _ in righe) + timedelta(hours=1)
    giorni = (fine - inizio).total_seconds() / 86400
    if giorni < GIORNI_MINIMI:
        return tot, giorni
    k = 365 / min(giorni, 365)
    return {f: v * k for f, v in tot.items()}, giorni
