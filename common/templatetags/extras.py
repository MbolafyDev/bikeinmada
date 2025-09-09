from django import template
from datetime import datetime

register = template.Library()

@register.filter
def get_month_name(value):
    try:
        return datetime(1900, int(value), 1).strftime('%B').capitalize()
    except:
        return value

@register.filter
def get_years(current_year, num=5):
    try:
        current_year = int(current_year)
        return [current_year - i for i in range(num)]
    except:
        return []
        
@register.filter
def to(start, end):
    return range(start, end + 1)

@register.filter
def dict_get(d, key):
    return d.get(key, 0) if isinstance(d, dict) else 0

@register.simple_tag
def nested_dict_get(dictionnaire, cle1, cle2):
    return dictionnaire.get(cle1, {}).get(cle2, 0)

@register.filter
def get_item(d, key):
    if isinstance(d, dict):
        return d.get(key, 0)
    return 0
