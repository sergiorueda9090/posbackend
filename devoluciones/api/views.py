from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from django.shortcuts import get_object_or_404
from django.db.models import Q, Sum

# Importar modelos necesarios
from user.api.permissions import RolePermission 
from clientes.models import Cliente
from tarjetabancaria.models import TarjetaBancaria
from devoluciones.models import Devoluciones # Usamos el modelo 'Devoluciones' proporcionado por el usuario

from decimal import Decimal, InvalidOperation
from datetime import datetime, time

# Roles permitidos para gestionar devoluciones
DEVOLUTION_MANAGER_ROLES = ['admin', 'manager', 'contador'] 


# --- Ayudante de Serialización ---
def serialize_devolucion(devolucion: Devoluciones):
    """Serializa un objeto Devoluciones con formato de moneda COP."""
    
    try:
        # Formato: $1.250.000,00
        valor_cop = "${:,.2f}".format(devolucion.valor).replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        valor_cop = f"${devolucion.valor}" 

    return {
        'id': devolucion.id,
        'valor': valor_cop, # Valor formateado en COP
        'descripcion': devolucion.descripcion,
        'fecha_transaccion': devolucion.fecha_transaccion,
        
        # Información de las relaciones
        'cliente_id': devolucion.cliente_id,
        'cliente_nombre': devolucion.cliente.nombre,
        'tarjeta_id': devolucion.tarjeta_id,
        'tarjeta_nombre': devolucion.tarjeta.nombre,
        
        'creado_por_username': devolucion.creado_por.username if devolucion.creado_por else None,
        'created_at': devolucion.created_at,
        'updated_at': devolucion.updated_at,
        'deleted_at': devolucion.deleted_at,
    }


## 1. Crear Devolución (POST)
@api_view(['POST'])
@permission_classes([IsAuthenticated, RolePermission(DEVOLUTION_MANAGER_ROLES)])
def create_devolucion(request):
    cliente_id = request.data.get('cliente_id')
    tarjeta_id = request.data.get('tarjeta_id')
    valor_str = request.data.get('valor')
    descripcion = request.data.get('descripcion', '')
    
    # 1. Validaciones de entrada
    if not all([cliente_id, tarjeta_id, valor_str]):
        return Response(
            {"error": "Los campos 'cliente_id', 'tarjeta_id' y 'valor' son obligatorios."},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        valor = Decimal(valor_str)
        if valor <= 0:
            raise InvalidOperation
    except InvalidOperation:
        return Response(
            {"error": "El valor de la devolución debe ser un número positivo válido."},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        # 2. Verificar existencia de Cliente y Tarjeta (solo activos)
        cliente = get_object_or_404(Cliente, pk=cliente_id)
        tarjeta = get_object_or_404(TarjetaBancaria, pk=tarjeta_id)
        
        # 3. Creación del objeto
        devolucion = Devoluciones.objects.create(
            cliente=cliente,
            tarjeta=tarjeta,
            valor=valor,
            descripcion=descripcion,
            creado_por=request.user
        )

        # Recargar las relaciones para serializar correctamente
        devolucion_created = Devoluciones.objects.select_related('cliente', 'tarjeta', 'creado_por').get(pk=devolucion.pk)

        return Response(serialize_devolucion(devolucion_created), status=status.HTTP_201_CREATED)

    except Exception as e:
        return Response(
            {"error": f"Error al registrar la devolución: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


## 2. Listar Devoluciones (GET) - CON FILTROS
@api_view(['GET'])
@permission_classes([IsAuthenticated, RolePermission(DEVOLUTION_MANAGER_ROLES)])
def list_devoluciones(request):
    try:
        # Consulta base: solo devoluciones NO eliminadas lógicamente
        devoluciones = Devoluciones.objects.select_related('cliente', 'tarjeta', 'creado_por').filter(deleted_at__isnull=True)
        
        # --- Obtener parámetros de filtros ---
        search_query = request.query_params.get('search', None)
        cliente_id_filter = request.query_params.get('cliente_id', None)
        start_date_str = request.query_params.get('start_date', None) 
        end_date_str = request.query_params.get('end_date', None) 
        
        # --- 1. Aplicar Filtros de Búsqueda (Texto) ---
        if search_query:
            # Búsqueda por descripción, nombre de cliente o nombre de tarjeta
            devoluciones = devoluciones.filter(
                Q(descripcion__icontains=search_query) |
                Q(cliente__nombre__icontains=search_query) |
                Q(tarjeta__nombre__icontains=search_query)
            )
        
        # --- 2. Filtro por Cliente Específico ---
        if cliente_id_filter:
            devoluciones = devoluciones.filter(cliente_id=cliente_id_filter)

        # --- 3. Aplicar Filtros de Fecha (Rango en fecha_transaccion) ---
        if start_date_str:
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                start_datetime = datetime.combine(start_date, time.min)
                devoluciones = devoluciones.filter(fecha_transaccion__gte=start_datetime)
            except ValueError:
                return Response({"error": "Formato de fecha de inicio inválido (YYYY-MM-DD)."}, status=status.HTTP_400_BAD_REQUEST)

        if end_date_str:
            try:
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
                end_datetime = datetime.combine(end_date, time.max)
                devoluciones = devoluciones.filter(fecha_transaccion__lte=end_datetime)
            except ValueError:
                return Response({"error": "Formato de fecha de fin inválido (YYYY-MM-DD)."}, status=status.HTTP_400_BAD_REQUEST)

        # La ordenación por defecto viene del Meta del modelo ('-fecha_transaccion'), pero se puede forzar:
        devoluciones = devoluciones.order_by('-fecha_transaccion')

        # --- 4. Paginación ---
        paginator = PageNumberPagination()
        paginator.page_size = 15 
        paginated_devoluciones = paginator.paginate_queryset(devoluciones, request)

        # --- 5. Serialización ---
        data = [serialize_devolucion(d) for d in paginated_devoluciones]

        # --- 6. Calcular total devuelto (usando el mismo queryset *filtrado*) ---
        total_devuelto = devoluciones.aggregate(total_valor=Sum('valor'))['total_valor'] or Decimal(0)
        total_cop = "${:,.2f}".format(total_devuelto).replace(",", "X").replace(".", ",").replace("X", ".")
        
        return paginator.get_paginated_response({
            "results": data,
            "total_devoluciones": total_cop,
            "filtros_aplicados": {
                "search": search_query,
                "cliente_id": cliente_id_filter,
                "start_date": start_date_str, 
                "end_date": end_date_str,
            }
        })

    except Exception as e:
        print(f"Error en list_devoluciones: {e}") 
        return Response(
            {"error": f"Error al obtener la lista de devoluciones: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

## 3. Obtener Detalle de Devolución (GET)
@api_view(['GET'])
@permission_classes([IsAuthenticated, RolePermission(DEVOLUTION_MANAGER_ROLES)])
def get_devolucion(request, pk):
    # Solo busca devoluciones NO eliminadas
    devolucion = get_object_or_404(
        Devoluciones.objects.select_related('cliente', 'tarjeta', 'creado_por').filter(deleted_at__isnull=True), 
        pk=pk
    )
    
    return Response(serialize_devolucion(devolucion), status=status.HTTP_200_OK)


## 4. Actualizar Devolución (PUT/PATCH)
@api_view(['PUT', 'PATCH'])
@permission_classes([IsAuthenticated, RolePermission(DEVOLUTION_MANAGER_ROLES)])
def update_devolucion(request, pk):
    try:
        # Solo permite actualizar devoluciones NO eliminadas
        devolucion = get_object_or_404(Devoluciones.objects.filter(deleted_at__isnull=True), pk=pk)
        
        valor_str = request.data.get('valor')
        descripcion = request.data.get('descripcion', devolucion.descripcion)
        cliente_id = request.data.get('cliente_id', devolucion.cliente_id)
        tarjeta_id = request.data.get('tarjeta_id', devolucion.tarjeta_id)
        
        # Validación y asignación de valor
        if valor_str:
            try:
                new_valor = Decimal(valor_str)
                if new_valor <= 0:
                    raise InvalidOperation
                devolucion.valor = new_valor
            except InvalidOperation:
                return Response(
                    {"error": "El valor de la devolución debe ser un número positivo válido."},
                    status=status.HTTP_400_BAD_REQUEST
                )

        # Asignación de Cliente
        if cliente_id != devolucion.cliente_id:
            devolucion.cliente = get_object_or_404(Cliente, pk=cliente_id)

        # Asignación de Tarjeta
        if tarjeta_id != devolucion.tarjeta_id:
            devolucion.tarjeta = get_object_or_404(TarjetaBancaria, pk=tarjeta_id)

        devolucion.descripcion = descripcion
        devolucion.save()

        # Recargar para serializar las relaciones actualizadas
        devolucion_updated = Devoluciones.objects.select_related('cliente', 'tarjeta', 'creado_por').get(pk=pk)

        return Response(serialize_devolucion(devolucion_updated), status=status.HTTP_200_OK)

    except Exception as e:
        return Response(
            {"error": f"Error al actualizar la devolución: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


## 5. Eliminar Devolución (DELETE) - Eliminación Lógica
@api_view(['DELETE'])
@permission_classes([IsAuthenticated, RolePermission(DEVOLUTION_MANAGER_ROLES)])
def delete_devolucion(request, pk):
    try:
        # Solo busca devoluciones NO eliminadas
        devolucion = get_object_or_404(Devoluciones.objects.filter(deleted_at__isnull=True), pk=pk)
        
        # Ejecuta el soft delete (establece deleted_at)
        devolucion.delete() # Asumiendo que BaseModel o SoftDeleteManager manejan la lógica.
        
        return Response(
            {"message": "Devolución eliminada lógicamente exitosamente", "deleted_at": devolucion.deleted_at}, 
            status=status.HTTP_200_OK
        )
    except Exception as e:
        return Response(
            {"error": f"Error al ejecutar la eliminación lógica de la devolución: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

