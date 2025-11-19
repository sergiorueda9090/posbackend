def remove_thousand_separators(value):
    """
        Elimina separadores de miles (puntos o comas) y deja solo dígitos y un punto decimal.
        Ejemplos:
        "1.200.000" → "1200000"
        "3,500.75" → "3500.75"
    """
    if not value:
        return "0"
    # Elimina todos los puntos y comas que no sean parte del decimal
    value = str(value).replace(".", "").replace(",", "")
    return value