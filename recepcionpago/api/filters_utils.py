# api/filters_utils.py
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Q, Sum
from datetime import datetime, time
from decimal import Decimal

def apply_filters_and_calculate_total(queryset, query_params, search_fields=None, date_field='created_at', extra_filters=None):
    """
    Aplica filtros genéricos (búsqueda de texto, rango de fechas) 
    y calcula el total de un campo 'valor' opcional.
    
    :param queryset: QuerySet base a filtrar (ej: Categoria.objects.all()).
    :param query_params: request.query_params del request.
    :param search_fields: Lista de campos del modelo para la búsqueda de texto (ej: ['nombre', 'descripcion']).
    :param date_field: Nombre del campo DateTimeField para filtrar por fecha (ej: 'created_at').
    :param extra_filters: Diccionario de filtros específicos a aplicar (ej: {'cliente_id': 'cliente_id'}).
    :returns: Tupla (queryset_filtrado, total_calculado, filtros_aplicados, response_error)
    """
    
    # 1. Copia del QuerySet original
    filtered_queryset = queryset 
    
    # 2. Obtener Parámetros
    search_query    = query_params.get('search', None)
    start_date_str  = query_params.get('start_date', None)
    end_date_str    = query_params.get('end_date', None)
    
    filtros_aplicados = {
        "search": search_query,
        "start_date": start_date_str,
        "end_date": end_date_str,
    }

    # 3. Aplicar Filtros Específicos (IDs, etc.)
    if extra_filters:
        for param_name, field_name in extra_filters.items():
            param_value = query_params.get(param_name, None)
            if param_value:
                filter_kwargs = {field_name: param_value}
                filtered_queryset = filtered_queryset.filter(**filter_kwargs)
                filtros_aplicados[param_name] = param_value
    
    # 4. Aplicar Filtro de Búsqueda de Texto
    if search_query and search_fields:
        q_objects = Q()
        for field in search_fields:
            q_objects |= Q(**{f'{field}__icontains': search_query})
        filtered_queryset = filtered_queryset.filter(q_objects)

    # 5. Aplicar Filtros de Rango de Fechas
    if start_date_str:
        try:
            fecha_inicio = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            start_datetime = datetime.combine(fecha_inicio, time.min)
            # Usa el campo de fecha dinámico
            filtered_queryset = filtered_queryset.filter(**{f'{date_field}__gte': start_datetime})
        except ValueError:
            return None, None, None, Response(
                {"error": "El formato de la fecha de inicio debe ser YYYY-MM-DD."},
                status=status.HTTP_400_BAD_REQUEST
            )

    if end_date_str:
        try:
            fecha_fin = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            end_datetime = datetime.combine(fecha_fin, time.max)
            # Usa el campo de fecha dinámico
            filtered_queryset = filtered_queryset.filter(**{f'{date_field}__lte': end_datetime})
        except ValueError:
            return None, None, None, Response(
                {"error": "El formato de la fecha de fin debe ser YYYY-MM-DD."},
                status=status.HTTP_400_BAD_REQUEST
            )
            
    # 6. Calcular Total (asumiendo un campo 'valor' o 'monto')
    # Intenta obtener el campo valor para calcular la suma
    try:
        total = filtered_queryset.aggregate(total_valor=Sum('valor'))['total_valor'] or Decimal(0)
    except Exception:
        # Si el modelo no tiene campo 'valor' o hay otro error, el total es 0
        total = Decimal(0) 

    # Formatear el total (ej. COP)
    total_cop = "${:,.2f}".format(total).replace(",", "X").replace(".", ",").replace("X", ".")

    return filtered_queryset, total_cop, filtros_aplicados, None