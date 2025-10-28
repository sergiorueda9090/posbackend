from decimal import Decimal
from django.db.models import Q, Sum
from datetime import datetime, time
from devoluciones.models import Devoluciones


def get_total_devoluciones(cliente_id=None, tarjeta_id=None, search_query=None, start_date=None, end_date=None):
    """
    Calcula el total de devoluciones (suma del campo 'valor'), 
    con filtros opcionales por cliente, tarjeta, texto o rango de fechas.

    Parámetros:
        cliente_id (int | None): ID del cliente opcional.
        tarjeta_id (int | None): ID de la tarjeta opcional.
        search_query (str | None): Texto opcional para búsqueda en descripción, cliente o tarjeta.
        start_date (str | None): Fecha de inicio (formato 'YYYY-MM-DD').
        end_date (str | None): Fecha final (formato 'YYYY-MM-DD').

    Retorna:
        dict: {
            "total": Decimal,
            "total_cop": str
        }
    """

    # Base: devoluciones activas (no eliminadas)
    devoluciones = Devoluciones.objects.filter(deleted_at__isnull=True)

    # --- Filtro por cliente o tarjeta ---
    if cliente_id:
        devoluciones = devoluciones.filter(cliente_id=cliente_id)
    elif tarjeta_id:
        devoluciones = devoluciones.filter(tarjeta_id=tarjeta_id)

    # --- Filtro por texto (búsqueda) ---
    if search_query:
        devoluciones = devoluciones.filter(
            Q(descripcion__icontains=search_query) |
            Q(cliente__nombre__icontains=search_query) |
            Q(tarjeta__nombre__icontains=search_query)
        )

    # --- Filtros por rango de fechas ---
    if start_date:
        try:
            start_date_obj = datetime.strptime(start_date, "%Y-%m-%d").date()
            start_datetime = datetime.combine(start_date_obj, time.min)
            devoluciones = devoluciones.filter(fecha_transaccion__gte=start_datetime)
        except ValueError:
            pass  # Ignorar si el formato no es válido

    if end_date:
        try:
            end_date_obj = datetime.strptime(end_date, "%Y-%m-%d").date()
            end_datetime = datetime.combine(end_date_obj, time.max)
            devoluciones = devoluciones.filter(fecha_transaccion__lte=end_datetime)
        except ValueError:
            pass  # Ignorar si el formato no es válido

    # --- Calcular total ---
    total = devoluciones.aggregate(total_valor=Sum('valor'))['total_valor'] or Decimal(0)

    # --- Formato COP ---
    total_cop = "${:,.2f}".format(total).replace(",", "X").replace(".", ",").replace("X", ".")

    return {
        "total": total,
        "total_cop": total_cop
    }
