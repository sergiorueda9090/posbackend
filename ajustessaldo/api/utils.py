# ajustessaldo/utils.py
from datetime import datetime, time
from decimal import Decimal
from django.db.models import Sum
from ajustessaldo.models import AjusteSaldo # Importar el modelo AjusteSaldo


def get_total_ajuste_saldo(cliente_id=None, fechaInicio=None, fechaFin=None):
    """
    Calcula el total neto de los ajustes de saldo (suma de valores positivos y negativos) 
    con filtros opcionales por cliente y rango de fechas.

    Retorna un diccionario con el total bruto y el total formateado en COP.
    """
    try:
        # 1. Consulta base: filtramos por registros NO eliminados lógicamente
        ajustes = AjusteSaldo.objects.filter(deleted_at__isnull=True)

        # --- Filtrar por cliente ---
        if cliente_id:
            ajustes = ajustes.filter(cliente_id=cliente_id)

        # --- Filtrar por rango de fechas ---
        
        if fechaInicio:
            try:
                # Convertir a datetime al inicio del día (00:00:00)
                start_date = datetime.strptime(fechaInicio, "%Y-%m-%d").date()
                start_datetime = datetime.combine(start_date, time.min)
                ajustes = ajustes.filter(fecha_transaccion__gte=start_datetime)
            except ValueError:
                pass

        if fechaFin:
            try:
                # Convertir a datetime al final del día (23:59:59.999999)
                end_date = datetime.strptime(fechaFin, "%Y-%m-%d").date()
                end_datetime = datetime.combine(end_date, time.max)
                ajustes = ajustes.filter(fecha_transaccion__lte=end_datetime)
            except ValueError:
                pass

        # --- Calcular total NETO (Sumar valores, incluyendo negativos) ---
        total = ajustes.aggregate(total_valor=Sum('valor'))['total_valor'] or Decimal(0)

        # --- Formatear como moneda colombiana (COP) ---
        # Note: El formato manejará el signo negativo si aplica.
        total_cop = "${:,.2f}".format(total).replace(",", "X").replace(".", ",").replace("X", ".")

        return {
            "total"     : total,  # Valor Decimal (para cálculos)
            "total_cop" : total_cop # Valor formateado (para visualización)
        }

    except Exception as e:
        print(f"Error en get_total_ajuste_saldo: {e}")
        return {
            "total": Decimal(0),
            "total_cop": "$0,00",
            "error": str(e)
        }