# utilidadocacional/api/views.py
from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from django.shortcuts import get_object_or_404
from django.db.models import Q, Sum

# Importar modelos y helpers
from user.api.permissions import RolePermission 
from tarjetabancaria.models import TarjetaBancaria
from utilidadocacional.models import UtilidadOcasional 
from decimal import Decimal, InvalidOperation
from datetime import datetime, time

# Roles permitidos para gestionar utilidades ocasionales
UTILITY_MANAGER_ROLES = ['admin', 'manager', 'contador'] 


# --- Ayudante de Serialización ---
def serialize_utilidad(utilidad: UtilidadOcasional):
    """Serializa un objeto UtilidadOcasional con formato de moneda."""
    
    try:
        # Formato: $1.250.000,00 (Asumiendo formato COP)
        valor_cop = "${:,.2f}".format(utilidad.valor).replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        valor_cop = f"${utilidad.valor}" 

    return {
        'id': utilidad.id,
        'valor': valor_cop, # Valor formateado
        'observacion': utilidad.observacion,
        'fecha_transaccion': utilidad.fecha_transaccion,
        
        # Información de las relaciones
        'tarjeta_id': utilidad.tarjeta_id,
        'tarjeta_nombre': utilidad.tarjeta.nombre if utilidad.tarjeta else "N/A",
        
        'creado_por_username': utilidad.creado_por.username if utilidad.creado_por else None,
        'created_at': utilidad.created_at,
        'updated_at': utilidad.updated_at,
        'deleted_at': utilidad.deleted_at,
    }


## 1. Crear Utilidad (POST)
@api_view(['POST'])
@permission_classes([IsAuthenticated, RolePermission(UTILITY_MANAGER_ROLES)])
def create_utilidad(request):
    tarjeta_id = request.data.get('tarjeta_id')
    valor_str = request.data.get('valor')
    observacion = request.data.get('observacion', '')
    
    # 1. Validaciones de entrada
    if not all([tarjeta_id, valor_str]):
        return Response(
            {"error": "Los campos 'tarjeta_id' y 'valor' son obligatorios."},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        valor = Decimal(valor_str)
        if valor <= 0:
            return Response(
                {"error": "El valor de la utilidad debe ser un número positivo."},
                status=status.HTTP_400_BAD_REQUEST
            )
    except InvalidOperation:
        return Response(
            {"error": "El valor de la utilidad debe ser un número válido."},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        # 2. Verificar existencia de Tarjeta
        tarjeta = get_object_or_404(TarjetaBancaria, pk=tarjeta_id)
        
        # 3. Creación del objeto
        utilidad = UtilidadOcasional.objects.create(
            tarjeta=tarjeta,
            valor=valor,
            observacion=observacion,
            creado_por=request.user
        )

        # Recargar las relaciones para serializar correctamente
        utilidad_created = UtilidadOcasional.objects.select_related('tarjeta', 'creado_por').get(pk=utilidad.pk)

        return Response(serialize_utilidad(utilidad_created), status=status.HTTP_201_CREATED)

    except Exception as e:
        return Response(
            {"error": f"Error al registrar la utilidad ocasional: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


## 2. Listar Utilidades (GET) - CON FILTROS
@api_view(['GET'])
@permission_classes([IsAuthenticated, RolePermission(UTILITY_MANAGER_ROLES)])
def list_utilidades(request):
    try:
        # Consulta base: solo utilidades NO eliminadas lógicamente
        utilidades = UtilidadOcasional.objects.select_related('tarjeta', 'creado_por').filter(deleted_at__isnull=True)
        
        # --- Obtener parámetros de filtros ---
        search_query = request.query_params.get('search', None)
        tarjeta_id_filter = request.query_params.get('tarjeta_id', None)
        start_date_str = request.query_params.get('start_date', None) 
        end_date_str = request.query_params.get('end_date', None) 
        
        # --- 1. Aplicar Filtros de Búsqueda (Texto) ---
        if search_query:
            # Búsqueda por observación o nombre de tarjeta
            utilidades = utilidades.filter(
                Q(observacion__icontains=search_query) |
                Q(tarjeta__nombre__icontains=search_query)
            )
        
        # --- 2. Filtro por Tarjeta Específica ---
        if tarjeta_id_filter:
            utilidades = utilidades.filter(tarjeta_id=tarjeta_id_filter)

        # --- 3. Aplicar Filtros de Fecha (Rango en fecha_transaccion) ---
        if start_date_str:
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                start_datetime = datetime.combine(start_date, time.min)
                utilidades = utilidades.filter(fecha_transaccion__gte=start_datetime)
            except ValueError:
                return Response({"error": "Formato de fecha de inicio inválido (YYYY-MM-DD)."}, status=status.HTTP_400_BAD_REQUEST)

        if end_date_str:
            try:
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
                end_datetime = datetime.combine(end_date, time.max)
                utilidades = utilidades.filter(fecha_transaccion__lte=end_datetime)
            except ValueError:
                return Response({"error": "Formato de fecha de fin inválido (YYYY-MM-DD)."}, status=status.HTTP_400_BAD_REQUEST)

        # Ordenación 
        utilidades = utilidades.order_by('-fecha_transaccion')
        
        # --- 4. Paginación ---
        paginator = PageNumberPagination()
        paginator.page_size = 15 
        paginated_utilidades = paginator.paginate_queryset(utilidades, request)

        # --- 5. Serialización ---
        data = [serialize_utilidad(u) for u in paginated_utilidades]
        
        # --- 6. Calcular total ganado (opcional, pero útil) ---
        total_utilidad = utilidades.aggregate(total_valor=Sum('valor'))['total_valor'] or Decimal(0)
        total_cop = "${:,.2f}".format(total_utilidad).replace(",", "X").replace(".", ",").replace("X", ".")


        return paginator.get_paginated_response({
            "results": data,
            "total_utilidad": total_cop,
            "filtros_aplicados": {
                "search": search_query,
                "tarjeta_id": tarjeta_id_filter,
                "start_date": start_date_str, 
                "end_date": end_date_str,
            }
        })

    except Exception as e:
        return Response(
            {"error": f"Error al obtener la lista de utilidades ocasionales: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


## 3. Obtener Detalle de Utilidad (GET)
@api_view(['GET'])
@permission_classes([IsAuthenticated, RolePermission(UTILITY_MANAGER_ROLES)])
def get_utilidad(request, pk):
    # Solo busca utilidades NO eliminadas
    utilidad = get_object_or_404(
        UtilidadOcasional.objects.select_related('tarjeta', 'creado_por').filter(deleted_at__isnull=True), 
        pk=pk
    )
    
    return Response(serialize_utilidad(utilidad), status=status.HTTP_200_OK)


## 4. Actualizar Utilidad (PUT/PATCH)
@api_view(['PUT', 'PATCH'])
@permission_classes([IsAuthenticated, RolePermission(UTILITY_MANAGER_ROLES)])
def update_utilidad(request, pk):
    try:
        # Solo permite actualizar utilidades NO eliminadas
        utilidad = get_object_or_404(UtilidadOcasional.objects.filter(deleted_at__isnull=True), pk=pk)
        
        valor_str = request.data.get('valor')
        observacion = request.data.get('observacion', utilidad.observacion)
        tarjeta_id = request.data.get('tarjeta_id', utilidad.tarjeta_id)
        
        # Validación y asignación de valor
        if valor_str:
            try:
                new_valor = Decimal(valor_str)
                if new_valor <= 0:
                    raise InvalidOperation
                utilidad.valor = new_valor
            except InvalidOperation:
                return Response(
                    {"error": "El valor de la utilidad debe ser un número positivo válido."},
                    status=status.HTTP_400_BAD_REQUEST
                )

        # Asignación de Tarjeta
        if tarjeta_id != utilidad.tarjeta_id:
            utilidad.tarjeta = get_object_or_404(TarjetaBancaria, pk=tarjeta_id)

        utilidad.observacion = observacion
        utilidad.save()

        # Recargar para serializar las relaciones actualizadas
        utilidad_updated = UtilidadOcasional.objects.select_related('tarjeta', 'creado_por').get(pk=pk)

        return Response(serialize_utilidad(utilidad_updated), status=status.HTTP_200_OK)

    except Exception as e:
        return Response(
            {"error": f"Error al actualizar la utilidad ocasional: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


## 5. Eliminar Utilidad (DELETE) - Eliminación Lógica
@api_view(['DELETE'])
@permission_classes([IsAuthenticated, RolePermission(UTILITY_MANAGER_ROLES)])
def delete_utilidad(request, pk):
    try:
        # Solo busca utilidades NO eliminadas
        utilidad = get_object_or_404(UtilidadOcasional.objects.filter(deleted_at__isnull=True), pk=pk)
        
        # Ejecuta el soft delete (establece deleted_at)
        utilidad.delete() 
        
        return Response(
            {"message": "Utilidad ocasional eliminada lógicamente exitosamente", "deleted_at": utilidad.deleted_at}, 
            status=status.HTTP_200_OK
        )
    except Exception as e:
        return Response(
            {"error": f"Error al ejecutar la eliminación lógica de la utilidad: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )