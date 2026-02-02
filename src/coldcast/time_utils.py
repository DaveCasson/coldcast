from __future__ import annotations

import datetime as dt
from typing import Iterable, List, Optional


def get_reference_time(delay_seconds: int = 0, base_time: Optional[dt.datetime] = None) -> dt.datetime:
    reference = base_time or dt.datetime.utcnow()
    return reference - dt.timedelta(seconds=delay_seconds)


def lead_time_strings(first_lead_time: int, lead_time: int, timestep: int) -> List[str]:
    return [f"{lt:03d}" for lt in range(first_lead_time, lead_time + timestep, timestep)]


def daterange(start_date: dt.date, end_date: dt.date) -> Iterable[dt.date]:
    current = start_date
    while current <= end_date:
        yield current
        current += dt.timedelta(days=1)
