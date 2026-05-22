import datetime
import re
import sys
import os

def get_resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller"""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

def format_currency(amount):
    """Formats a number into Indian Rupee style currency.
    Example: 1543200.50 -> ₹15,43,200.50
    """
    if amount is None:
        return "₹0.00"
    
    try:
        amount = float(amount)
    except ValueError:
        return "₹0.00"

    sign = "-" if amount < 0 else ""
    amount = abs(amount)
    
    # Split decimal and integer parts
    s = f"{amount:.2f}"
    parts = s.split('.')
    int_part = parts[0]
    dec_part = parts[1]
    
    # Indian numbering formatting logic
    if len(int_part) <= 3:
        formatted_int = int_part
    else:
        last_three = int_part[-3:]
        remaining = int_part[:-3]
        # Group remaining digits in twos
        chunks = []
        while remaining:
            chunks.append(remaining[-2:])
            remaining = remaining[:-2]
        chunks.reverse()
        formatted_int = ",".join(chunks) + "," + last_three
        
    return f"{sign}₹{formatted_int}.{dec_part}"

def format_date(date_str):
    """Formats a YYYY-MM-DD date string into DD-MM-YYYY for display."""
    if not date_str:
        return ""
    try:
        dt = datetime.datetime.strptime(date_str, "%Y-%m-%d")
        return dt.strftime("%d-%m-%Y")
    except ValueError:
        return date_str

def parse_date(date_str):
    """Validates and converts various date formats (e.g. DD-MM-YYYY or YYYY-MM-DD) to YYYY-MM-DD."""
    date_str = str(date_str).strip()
    
    # Try YYYY-MM-DD
    try:
        dt = datetime.datetime.strptime(date_str, "%Y-%m-%d")
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        pass
        
    # Try DD-MM-YYYY
    try:
        dt = datetime.datetime.strptime(date_str, "%d-%m-%y")
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        pass
        
    try:
        dt = datetime.datetime.strptime(date_str, "%d-%m-%Y")
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        pass
        
    raise ValueError("Invalid date format. Use DD-MM-YYYY or YYYY-MM-DD.")

def validate_positive_float(value, field_name="Field"):
    """Validates that a string is a positive float and returns it."""
    try:
        val = float(value)
        if val <= 0:
            raise ValueError(f"{field_name} must be greater than zero.")
        return val
    except ValueError as e:
        if "greater than zero" in str(e):
            raise
        raise ValueError(f"{field_name} must be a valid number.")

def validate_positive_int(value, field_name="Field"):
    """Validates that a string is a positive integer and returns it."""
    try:
        val = int(value)
        if val <= 0:
            raise ValueError(f"{field_name} must be greater than zero.")
        return val
    except ValueError as e:
        if "greater than zero" in str(e):
            raise
        raise ValueError(f"{field_name} must be a valid integer.")
