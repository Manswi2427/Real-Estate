from django import template

register = template.Library()

FALLBACK_IMAGES = [
    "https://images.unsplash.com/photo-1568605114967-8130f3a36994?auto=format&fit=crop&w=800&q=80",
    "https://images.unsplash.com/photo-1600596542815-ffad4c1539a9?auto=format&fit=crop&w=800&q=80",
    "https://images.unsplash.com/photo-1600585154340-be6161a56a0c?auto=format&fit=crop&w=800&q=80",
    "https://images.unsplash.com/photo-1512917774080-9991f1c4c750?auto=format&fit=crop&w=800&q=80",
    "https://images.unsplash.com/photo-1613977257363-707ba9348227?auto=format&fit=crop&w=800&q=80",
    "https://images.unsplash.com/photo-1580587771525-78b9dba3b914?auto=format&fit=crop&w=800&q=80",
    "https://images.unsplash.com/photo-1582268611958-ebfd161ef9cf?auto=format&fit=crop&w=800&q=80",
    "https://images.unsplash.com/photo-1600607687939-ce8a6c25118c?auto=format&fit=crop&w=800&q=80",
]


@register.filter
def fallback_image(property_obj):
    """
    Return the property's primary gallery image URL (V3),
    falling back to the legacy Property.image field,
    or a stable stock photo based on its id.
    """
    # V3: check gallery images
    try:
        primary = property_obj.images.filter(is_primary=True).first()
        if primary and primary.image:
            return primary.image.url
    except Exception:
        pass

    # Legacy single image field
    if getattr(property_obj, "image", None) and hasattr(property_obj.image, "url") and property_obj.image:
        return property_obj.image.url

    # Stable stock photo fallback
    index = (property_obj.id or 0) % len(FALLBACK_IMAGES)
    return FALLBACK_IMAGES[index]


@register.filter
def format_inr(value):
    """Format a number in Indian numbering system format (e.g. 25,00,000)."""
    if value is None:
        return ""
    try:
        val_int = int(float(value))
    except (ValueError, TypeError):
        return str(value)

    is_negative = val_int < 0
    val_int = abs(val_int)
    s = str(val_int)
    if len(s) <= 3:
        result = s
    else:
        last3 = s[-3:]
        rest = s[:-3]
        groups = []
        while rest:
            groups.insert(0, rest[-2:])
            rest = rest[:-2]
        result = ",".join(groups) + "," + last3
    return f"-{result}" if is_negative else result


@register.filter
def price_label(value):
    """Return a clean formatted string like '25 Lakh' or '1.2 Crore' for rupees."""
    if value is None:
        return ""
    try:
        val_float = float(value)
    except (ValueError, TypeError):
        return str(value)

    if val_float >= 10000000:  # 1 Crore
        cr = val_float / 10000000
        return f"{cr:.2f} Cr" if cr != int(cr) else f"{int(cr)} Cr"
    elif val_float >= 100000:  # 1 Lakh
        lk = val_float / 100000
        return f"{lk:.2f} Lakh" if lk != int(lk) else f"{int(lk)} Lakh"
    else:
        return format_inr(val_float)
