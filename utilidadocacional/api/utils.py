# utilidadocacional/utils.py
from datetime import datetime, time
from decimal import Decimal
from django.db.models import Sum
from utilidadocacional.models import UtilidadOcasional # Importar el modelo UtilidadOcasional


def get_total_utilidad_ocasional(tarjeta_id=None, fechaInicio=None, fechaFin=None):
    """
    Calcula el total general de las utilidades ocasionales con filtros opcionales:
    - tarjeta_id: ID de la Tarjeta Bancaria
    - fechaInicio y fechaFin: rango de fechas (YYYY-MM-DD)

    Retorna un diccionario con el total bruto y el total formateado en COP.
    """
    try:
        # 1. Consulta base: filtramos por registros NO eliminados lógicamente
        utilidades = UtilidadOcasional.objects.filter(deleted_at__isnull=True)

        # --- Filtrar por tarjeta ---
        if tarjeta_id:
            utilidades = utilidades.filter(tarjeta_id=tarjeta_id)

        # --- Filtrar por rango de fechas ---
        
        # Ajustamos el manejo de fechas para incluir todo el día de inicio y fin.
        
        if fechaInicio:
            try:
                # Convertir a datetime al inicio del día (00:00:00)
                start_date = datetime.strptime(fechaInicio, "%Y-%m-%d").date()
                start_datetime = datetime.combine(start_date, time.min)
                utilidades = utilidades.filter(fecha_transaccion__gte=start_datetime)
            except ValueError:
                # Ignorar filtro si el formato es incorrecto
                pass

        if fechaFin:
            try:
                # Convertir a datetime al final del día (23:59:59.999999)
                end_date = datetime.strptime(fechaFin, "%Y-%m-%d").date()
                end_datetime = datetime.combine(end_date, time.max)
                utilidades = utilidades.filter(fecha_transaccion__lte=end_datetime)
            except ValueError:
                # Ignorar filtro si el formato es incorrecto
                pass

        # --- Calcular total ---
        # Si no hay utilidades, devuelve Decimal(0) para mantener la precisión
        total = utilidades.aggregate(total_valor=Sum('valor'))['total_valor'] or Decimal(0)

        # --- Formatear como moneda colombiana (COP) ---
        total_cop = "${:,.2f}".format(total).replace(",", "X").replace(".", ",").replace("X", ".")

        return {
            "total"     : total,  # Valor Decimal (para cálculos)
            "total_cop" : total_cop # Valor formateado (para visualización)
        }

    except Exception as e:
        print(f"Error en get_total_utilidad_ocasional: {e}")
        return {
            "total": Decimal(0),
            "total_cop": "$0,00",
            "error": str(e)
        }