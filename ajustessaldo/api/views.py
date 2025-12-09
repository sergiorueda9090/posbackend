# ajustessaldo/api/views.py
from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from django.shortcuts import get_object_or_404
from django.db.models import Q

# Importar modelos y helpers
from user.api.permissions import RolePermission 
from clientes.models import Cliente
from ajustessaldo.models import AjusteSaldo # Usamos el modelo AjusteSaldo
from decimal import Decimal, InvalidOperation
from datetime import datetime, time

# Roles permitidos para gestionar ajustes de saldo
ADJUSTMENT_MANAGER_ROLES = ['admin', 'manager', 'contador'] 


# --- Ayudante de Serialización ---
def serialize_ajuste(ajuste: AjusteSaldo):
    """Serializa un objeto AjusteSaldo con formato de moneda."""
    
    try:
        # Formato: $1.250.000,00 (Asumiendo formato COP)
        valor_cop = "${:,.2f}".format(ajuste.valor).replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        valor_cop = f"${ajuste.valor}" 

    return {
        'id': ajuste.id,
        'valor': ajuste.valor, #valor_cop, # Valor formateado
        'valor_bruto': str(ajuste.valor), # Valor sin formato para cálculos
        'observacion': ajuste.observacion,
        'fecha_transaccion': ajuste.fecha_transaccion,
        
        # Información de las relaciones
        'cliente_id': ajuste.cliente_id,
        'cliente_nombre': ajuste.cliente.nombre if ajuste.cliente else "N/A",
        
        'creado_por_username': ajuste.creado_por.username if ajuste.creado_por else None,
        'created_at': ajuste.created_at,
        'updated_at': ajuste.updated_at,
        'deleted_at': ajuste.deleted_at,
    }


## 1. Crear Ajuste (POST)
@api_view(['POST'])
@permission_classes([IsAuthenticated, RolePermission(ADJUSTMENT_MANAGER_ROLES)])
def create_ajuste(request):
    cliente_id  = request.data.get('cliente_id')
    valor_str   = request.data.get('valor')
    observacion = request.data.get('observacion', '')
    
    # 1. Validaciones de entrada
    if not all([cliente_id, valor_str]):
        return Response(
            {"error": "Los campos 'cliente_id' y 'valor' son obligatorios."},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        valor = Decimal(valor_str)
        if valor == 0:
            return Response(
                {"error": "El valor del ajuste de saldo no puede ser cero."},
                status=status.HTTP_400_BAD_REQUEST
            )
    except InvalidOperation:
        return Response(
            {"error": "El valor del ajuste debe ser un número válido."},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        # 2. Verificar existencia de Cliente
        # Usamos Cliente.objects.get() porque el campo del modelo es null=True, 
        # pero para crear un registro *nuevo* y válido, necesitamos un cliente.
        cliente = get_object_or_404(Cliente, pk=cliente_id)
        
        # 3. Creación del objeto
        ajuste = AjusteSaldo.objects.create(
            cliente=cliente,
            valor=valor,
            observacion=observacion,
            creado_por=request.user
        )

        # Recargar las relaciones para serializar correctamente
        ajuste_created = AjusteSaldo.objects.select_related('cliente', 'creado_por').get(pk=ajuste.pk)

        return Response(serialize_ajuste(ajuste_created), status=status.HTTP_201_CREATED)

    except Exception as e:
        return Response(
            {"error": f"Error al registrar el ajuste de saldo: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


## 2. Listar Ajustes (GET) - CON FILTROS
@api_view(['GET'])
@permission_classes([IsAuthenticated, RolePermission(ADJUSTMENT_MANAGER_ROLES)])
def list_ajustes(request):
    try:
        # Consulta base: solo ajustes NO eliminados lógicamente
        ajustes = AjusteSaldo.objects.select_related('cliente', 'creado_por').filter(deleted_at__isnull=True)
        
        # --- Obtener parámetros de filtros ---
        search_query = request.query_params.get('search', None)
        cliente_id_filter = request.query_params.get('cliente_id', None)
        start_date_str = request.query_params.get('start_date', None) 
        end_date_str = request.query_params.get('end_date', None) 
        
        # --- 1. Aplicar Filtros de Búsqueda (Texto) ---
        if search_query:
            # Búsqueda por observación o nombre de cliente
            ajustes = ajustes.filter(
                Q(observacion__icontains=search_query) |
                Q(cliente__nombre__icontains=search_query)
            )
        
        # --- 2. Filtro por Cliente Específico ---
        if cliente_id_filter:
            ajustes = ajustes.filter(cliente_id=cliente_id_filter)

        # --- 3. Aplicar Filtros de Fecha (Rango en fecha_transaccion) ---
        if start_date_str:
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                start_datetime = datetime.combine(start_date, time.min)
                ajustes = ajustes.filter(fecha_transaccion__gte=start_datetime)
            except ValueError:
                return Response({"error": "Formato de fecha de inicio inválido (YYYY-MM-DD)."}, status=status.HTTP_400_BAD_REQUEST)

        if end_date_str:
            try:
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
                end_datetime = datetime.combine(end_date, time.max)
                ajustes = ajustes.filter(fecha_transaccion__lte=end_datetime)
            except ValueError:
                return Response({"error": "Formato de fecha de fin inválido (YYYY-MM-DD)."}, status=status.HTTP_400_BAD_REQUEST)

        # Ordenación (viene del Meta del modelo, pero se asegura)
        ajustes = ajustes.order_by('-fecha_transaccion')

        # --- 4. Paginación ---
        paginator = PageNumberPagination()
        paginator.page_size = 15 
        paginated_ajustes = paginator.paginate_queryset(ajustes, request)

        # --- 5. Serialización ---
        data = [serialize_ajuste(a) for a in paginated_ajustes]
        return paginator.get_paginated_response(data)

        return paginator.get_paginated_response({
            "results": data,
            "filtros_aplicados": {
                "search": search_query,
                "cliente_id": cliente_id_filter,
                "start_date": start_date_str, 
                "end_date": end_date_str,
            }
        })

    except Exception as e:
        return Response(
            {"error": f"Error al obtener la lista de ajustes de saldo: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


## 3. Obtener Detalle de Ajuste (GET)
@api_view(['GET'])
@permission_classes([IsAuthenticated, RolePermission(ADJUSTMENT_MANAGER_ROLES)])
def get_ajuste(request, pk):
    # Solo busca ajustes NO eliminados
    ajuste = get_object_or_404(
        AjusteSaldo.objects.select_related('cliente', 'creado_por').filter(deleted_at__isnull=True), 
        pk=pk
    )
    
    return Response(serialize_ajuste(ajuste), status=status.HTTP_200_OK)


## 4. Actualizar Ajuste (PUT/PATCH)
@api_view(['PUT', 'PATCH'])
@permission_classes([IsAuthenticated, RolePermission(ADJUSTMENT_MANAGER_ROLES)])
def update_ajuste(request, pk):
    try:
        # Solo permite actualizar ajustes NO eliminados
        ajuste = get_object_or_404(AjusteSaldo.objects.filter(deleted_at__isnull=True), pk=pk)
        
        valor_str = request.data.get('valor')
        observacion = request.data.get('observacion', ajuste.observacion)
        cliente_id = request.data.get('cliente_id', ajuste.cliente_id)
        
        # Validación y asignación de valor
        if valor_str:
            try:
                new_valor = Decimal(valor_str)
                if new_valor == 0:
                    raise InvalidOperation
                ajuste.valor = new_valor
            except InvalidOperation:
                return Response(
                    {"error": "El valor del ajuste debe ser un número válido y no puede ser cero."},
                    status=status.HTTP_400_BAD_REQUEST
                )

        # Asignación de Cliente
        if cliente_id != ajuste.cliente_id:
            # Verificar si el cliente existe y está activo (asumiendo que get_object_or_404 lo manejará)
            ajuste.cliente = get_object_or_404(Cliente, pk=cliente_id)

        ajuste.observacion = observacion
        ajuste.save()

        # Recargar para serializar las relaciones actualizadas
        ajuste_updated = AjusteSaldo.objects.select_related('cliente', 'creado_por').get(pk=pk)

        return Response(serialize_ajuste(ajuste_updated), status=status.HTTP_200_OK)

    except Exception as e:
        return Response(
            {"error": f"Error al actualizar el ajuste de saldo: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


## 5. Eliminar Ajuste (DELETE) - Eliminación Lógica
@api_view(['DELETE'])
@permission_classes([IsAuthenticated, RolePermission(ADJUSTMENT_MANAGER_ROLES)])
def delete_ajuste(request, pk):
    try:
        # Solo busca ajustes NO eliminados
        ajuste = get_object_or_404(AjusteSaldo.objects.filter(deleted_at__isnull=True), pk=pk)
        
        # Ejecuta el soft delete (establece deleted_at)
        ajuste.delete() # Asumiendo que BaseModel maneja la eliminación lógica.
        
        return Response(
            {"message": "Ajuste de saldo eliminado lógicamente exitosamente", "deleted_at": ajuste.deleted_at}, 
            status=status.HTTP_200_OK
        )
    except Exception as e:
        return Response(
            {"error": f"Error al ejecutar la eliminación lógica del ajuste: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )