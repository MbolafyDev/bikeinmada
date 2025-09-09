from django import template
import num2words

register = template.Library()

@register.filter
def intpoint(value):
    try:
        value = int(value)
        return f"{value:,}".replace(",", ".")
    except (ValueError, TypeError):
        return value

@register.filter
def int2words(value):
    try:
        return num2words.num2words(value, lang='fr')
    except:
        return value

@register.filter
def get_item(dct, key):
    return dct.get(key)