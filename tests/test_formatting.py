from __future__ import annotations

from datetime import date
from decimal import Decimal

from emporio.formatting import format_brl, format_date


def test_format_brl_zero() -> None:
    assert format_brl(Decimal("0")) == "R$ 0,00"


def test_format_brl_cents() -> None:
    assert format_brl(Decimal("0.50")) == "R$ 0,50"
    assert format_brl(Decimal("0.05")) == "R$ 0,05"


def test_format_brl_thousands() -> None:
    assert format_brl(Decimal("1234.56")) == "R$ 1.234,56"
    assert format_brl(Decimal("11499")) == "R$ 11.499,00"


def test_format_brl_millions() -> None:
    assert format_brl(Decimal("1000000")) == "R$ 1.000.000,00"
    assert format_brl(Decimal("1234567.89")) == "R$ 1.234.567,89"


def test_format_brl_rounding() -> None:
    assert format_brl(Decimal("10.005")) == "R$ 10,01"
    assert format_brl(Decimal("10.004")) == "R$ 10,00"


def test_format_brl_negative() -> None:
    assert format_brl(Decimal("-50")) == "R$ -50,00"


def test_format_date() -> None:
    assert format_date(date(2026, 3, 15)) == "15/03/2026"
    assert format_date(date(2025, 10, 1)) == "01/10/2025"
    assert format_date(date(2026, 1, 31)) == "31/01/2026"
