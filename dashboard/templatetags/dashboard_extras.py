from django import template
import locale

register = template.Library()

@register.filter(name='get_item')
def get_item(dictionary, key):
    """
    Allows accessing a dictionary item by a variable key in Django templates.
    Usage: {{ my_dictionary|get_item:my_key }}
    """
    return dictionary.get(key)

@register.filter(name='format_currency')
def format_currency(value):
    """
    Formats a number as Indian Rupees (₹).
    e.g., 12345.67 -> ₹12,345.67
    """
    try:
        # Tries to use the Indian locale for currency formatting if available.
        locale.setlocale(locale.LC_MONETARY, 'en_IN')
        return locale.currency(float(value), grouping=True, symbol="₹")
    except (ValueError, TypeError, locale.Error):
        # Provides a reliable fallback if the locale is not installed
        # or if the input value is not a valid number.
        try:
            return f"₹{float(value):,.2f}"
        except (ValueError, TypeError):
            return value # Return original value if it cannot be converted to a float