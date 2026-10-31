from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal


def format_brl(value: Decimal) -> str:
    """Formata Decimal como moeda brasileira: R$ 1.234,56."""
    rounded = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    int_part = int(rounded)
    cents = abs(int(rounded * 100 % 100))
    negative = int_part < 0
    int_str = str(abs(int_part))
    groups: list[str] = []
    remaining = int_str
    while remaining:
        groups.append(remaining[-3:])
        remaining = remaining[:-3]
    with_thousands = ".".join(reversed(groups))
    sign = "-" if negative else ""
    return f"R$ {sign}{with_thousands},{cents:02d}"


def format_date(d: date) -> str:
    """Formata date como dd/mm/aaaa."""
    return d.strftime("%d/%m/%Y")
