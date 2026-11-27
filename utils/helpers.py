"""Formatting and parsing helpers shared by the UI and exports."""
import datetime
import math
import os
import sys


def get_resource_path(relative_path):
    """Absolute path to a bundled file, in dev and inside the PyInstaller exe."""
    base = getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, relative_path)


def _indian_group(int_part):
    if len(int_part) <= 3:
        return int_part
    head, tail = int_part[:-3], int_part[-3:]
    chunks = []
    while head:
        chunks.append(head[-2:])
        head = head[:-2]
    return ",".join(reversed(chunks)) + "," + tail


def format_currency(amount, symbol="₹", decimals=2):
    """1543200.5 -> ₹15,43,200.50 (Indian grouping). Never shows '-₹0.00'."""
    try:
        amount = float(amount or 0)
    except (TypeError, ValueError):
        amount = 0.0
    if not math.isfinite(amount):
        amount = 0.0
    amount = round(amount, decimals)
    sign = "-" if amount < 0 else ""
    text = f"{abs(amount):.{decimals}f}"
    int_part, _, dec_part = text.partition(".")
    return f"{sign}{symbol}{_indian_group(int_part)}" + (f".{dec_part}" if decimals else "")


def format_compact(amount, symbol="₹"):
    """Short money for cards and chart axes: ₹1.25L, ₹3.4Cr, ₹950."""
    amount = float(amount or 0)
    sign, a = ("-" if amount < 0 else ""), abs(amount)
    if a >= 1e7:
        return f"{sign}{symbol}{a / 1e7:.2f}Cr"
    if a >= 1e5:
        return f"{sign}{symbol}{a / 1e5:.2f}L"
    if a >= 1e3:
        return f"{sign}{symbol}{a / 1e3:.1f}K"
    return f"{sign}{symbol}{a:.0f}"


def format_qty(qty, unit=None):
    """12.0 -> '12', 12.5 -> '12.5'; optional unit suffix."""
    qty = float(qty or 0)
    text = f"{qty:.2f}".rstrip("0").rstrip(".")
    if text == "-0":
        text = "0"
    return f"{text} {unit}" if unit else text


def format_date(date_str, fmt="%d-%m-%Y"):
    """'2026-05-21' -> '21-05-2026'. Returns the input if it is not a date."""
    if not date_str:
        return ""
    try:
        return datetime.datetime.strptime(str(date_str)[:10], "%Y-%m-%d").strftime(fmt)
    except ValueError:
        return str(date_str)


def parse_date(text):
    """Accept DD-MM-YYYY, DD/MM/YYYY, DD-MM-YY or YYYY-MM-DD; return YYYY-MM-DD."""
    text = str(text).strip().replace("/", "-").replace(".", "-")
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d-%m-%y"):
        try:
            return datetime.datetime.strptime(text, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    raise ValueError("Enter the date as DD-MM-YYYY.")


def parse_number(text, field="Value", minimum=None, allow_zero=True):
    """Parse a user-typed number (commas and ₹ allowed); reject nan/inf."""
    cleaned = str(text).replace(",", "").replace("₹", "").strip()
    if not cleaned:
        raise ValueError(f"{field} is required.")
    try:
        value = float(cleaned)
    except ValueError:
        raise ValueError(f"{field} must be a number.")
    if not math.isfinite(value):
        raise ValueError(f"{field} must be a number.")
    if minimum is not None and value < minimum:
        raise ValueError(f"{field} cannot be less than {minimum:g}.")
    if not allow_zero and value == 0:
        raise ValueError(f"{field} must be greater than zero.")
    return value
