from datetime import datetime
from django.db.models import Sum
from recepcionpago.models import RecepcionPago


def get_total_recepcion_de_pago(cliente_id=None, tarjeta_id=None, fechaInicio=None, fechaFin=None):
    """
    Calcula el total general de las recepciones de pago con filtros opcionales:
    - cliente_id: ID del cliente
    - tarjeta_id: ID de la tarjeta
    - fechaInicio y fechaFin: rango de fechas (YYYY-MM-DD)

    Retorna un diccionario con el total formateado en COP y los filtros aplicados.
    """
    try:
        pagos = RecepcionPago.objects.all()

        # --- Filtrar por cliente ---
        if cliente_id:
            pagos = pagos.filter(cliente_id=cliente_id)

        # --- Filtrar por tarjeta ---
        if tarjeta_id:
            pagos = pagos.filter(tarjeta_id=tarjeta_id)

        # --- Filtrar por rango de fechas ---
        fecha_inicio = None
        fecha_fin = None

        if fechaInicio:
            try:
                fecha_inicio = datetime.strptime(fechaInicio, "%Y-%m-%d")
                pagos = pagos.filter(fecha_transaccion__date__gte=fecha_inicio)
            except ValueError:
                pass

        if fechaFin:
            try:
                fecha_fin = datetime.strptime(fechaFin, "%Y-%m-%d")
                pagos = pagos.filter(fecha_transaccion__date__lte=fecha_fin)
            except ValueError:
                pass

        # --- Calcular total ---
        total = pagos.aggregate(total_valor=Sum('valor'))['total_valor'] or 0

        # --- Formatear como moneda colombiana ---
        total_cop = "${:,.2f}".format(total).replace(",", "X").replace(".", ",").replace("X", ".")

        return {
            "total"     : total,
            "total_cop" : total_cop
        }

        # return {
        #     "total": total_cop,
        #     "filtros": {
        #         "cliente_id": cliente_id,
        #         "tarjeta_id": tarjeta_id,
        #         "fechaInicio": fecha_inicio.strftime("%Y-%m-%d") if fecha_inicio else None,
        #         "fechaFin": fecha_fin.strftime("%Y-%m-%d") if fecha_fin else None
        #     }
        # }

    except Exception as e:
        print(f"Error en get_total_recepcion_de_pago: {e}")
        return {
            "total": 0,
            "error": str(e)
        }
