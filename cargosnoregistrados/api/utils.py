from decimal import Decimal
from django.db.models import Q, Sum
from datetime import datetime, time
from cargosnoregistrados.models import CargosNoRegistrados


def get_total_cargos_no_registrados(
    cliente_id=None,
    tarjeta_id=None,
    search_query=None,
    start_date=None,
    end_date=None
):
    """
    Calcula el total de cargos no registrados (suma del campo 'valor').

    Permite filtros opcionales:
      - Por cliente
      - Por tarjeta
      - Por búsqueda (descripcion, cliente.nombre, tarjeta.nombre)
      - Por rango de fechas (fecha_transaccion)

    Parámetros:
        cliente_id (int | None): ID del cliente opcional.
        tarjeta_id (int | None): ID de la tarjeta opcional.
        search_query (str | None): Texto opcional de búsqueda.
        start_date (str | None): Fecha inicial (YYYY-MM-DD).
        end_date (str | None): Fecha final (YYYY-MM-DD).

    Retorna:
        dict: {
            "total": Decimal,
            "total_cop": str
        }
    """

    # --- Base Query: registros activos (no eliminados) ---
    cargos = CargosNoRegistrados.objects.filter(deleted_at__isnull=True)

    # --- Filtros principales ---
    if cliente_id:
        cargos = cargos.filter(cliente_id=cliente_id)
    elif tarjeta_id:
        cargos = cargos.filter(tarjeta_id=tarjeta_id)

    # --- Filtro por búsqueda ---
    if search_query:
        cargos = cargos.filter(
            Q(descripcion__icontains=search_query) |
            Q(cliente__nombre__icontains=search_query) |
            Q(tarjeta__nombre__icontains=search_query)
        )

    # --- Filtros por rango de fechas ---
    if start_date:
        try:
            start_date_obj = datetime.strptime(start_date, "%Y-%m-%d").date()
            start_datetime = datetime.combine(start_date_obj, time.min)
            cargos = cargos.filter(fecha_transaccion__gte=start_datetime)
        except ValueError:
            pass  # Ignorar formato incorrecto

    if end_date:
        try:
            end_date_obj = datetime.strptime(end_date, "%Y-%m-%d").date()
            end_datetime = datetime.combine(end_date_obj, time.max)
            cargos = cargos.filter(fecha_transaccion__lte=end_datetime)
        except ValueError:
            pass  # Ignorar formato incorrecto

    # --- Calcular el total ---
    total = cargos.aggregate(total_valor=Sum('valor'))['total_valor'] or Decimal(0)

    # --- Formato en COP ---
    total_cop = "${:,.2f}".format(total).replace(",", "X").replace(".", ",").replace("X", ".")

    return {
        "total": total,
        "total_cop": total_cop
    }
