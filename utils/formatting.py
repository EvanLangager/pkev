def to_percent(value):
    """Format a decimal as a percentage string"""
    return f"{value * 100:.2f}%"

def to_chips(value):
    """Format a number as a chips string with 2 decimal places"""
    return f"{value:.2f} chips"