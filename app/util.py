"""Small shared helpers for dates, intervals and schedule status."""
import re
from datetime import date

from dateutil.relativedelta import relativedelta

_UNIT_KW = {"day": "days", "week": "weeks", "month": "months", "year": "years"}
_CODE_UNIT = {"D": "day", "W": "week", "M": "month", "Y": "year"}


def add_interval(d: date, value: int, unit: str) -> date:
    kw = _UNIT_KW.get(unit, "months")
    return d + relativedelta(**{kw: value})


def add_months(d: date, months: int) -> date:
    return d + relativedelta(months=months)


def next_due_from(performed: date, value: int, unit: str) -> date:
    return add_interval(performed, value, unit)


def parse_frequency(code: str) -> tuple[int, str]:
    """Turn a label like '3M', '2W', '1Y', '6 months' into (value, unit). Defaults to (1, 'month')."""
    if not code:
        return 1, "month"
    m = re.match(r"^\s*(\d+)\s*([DWMY])\s*$", code.strip(), re.IGNORECASE)
    if m:
        return int(m.group(1)), _CODE_UNIT[m.group(2).upper()]
    m = re.match(r"^\s*(\d+)\s*(day|week|month|year)s?\s*$", code.strip(), re.IGNORECASE)
    if m:
        return int(m.group(1)), m.group(2).lower()
    return 1, "month"


def days_until(d: date) -> int:
    return (d - date.today()).days


def schedule_status(next_due: date) -> str:
    n = days_until(next_due)
    if n < 0:
        return "overdue"
    if n <= 7:
        return "due_soon"
    return "ok"
