from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from django.shortcuts import get_object_or_404, get_list_or_404
from django.db.models import Q, Sum
from decimal import Decimal
from datetime import datetime, time

# --- Importaciones del proyecto ---
from user.api.permissions import RolePermission
from productos.models import Producto
from inventarioproducto.models import InventarioProducto

# Roles que pueden gestionar inventarios
INVENTORY_MANAGER_ROLES = ['admin', 'manager', 'almacenista']


# --- Serializador manual ---
def serialize_inventario(inventario: InventarioProducto):
    """Serializa un objeto InventarioProducto."""
    return {
        'id': inventario.id,
        'producto_id': inventario.producto_id,
        'producto_nombre': inventario.producto.nombre if inventario.producto else None,
        'cantidad_unidades': inventario.cantidad_unidades,
        'fecha_ingreso': inventario.fecha_ingreso,
        'fecha_actualizacion': inventario.fecha_actualizacion,
        'creado_por_username': inventario.creado_por.username if inventario.creado_por else None,
        'deleted_at': inventario.deleted_at,
    }


# --- 1. Crear Inventario ---
@api_view(['POST'])
@permission_classes([IsAuthenticated, RolePermission(INVENTORY_MANAGER_ROLES)])
def create_inventario(request):
    producto_id  = request.data.get('producto_id')
    cantidad_str = request.data.get('cantidad_unidades')

    if not producto_id or cantidad_str is None:
        return Response(
            {"error": "Los campos 'producto_id' y 'cantidad_unidades' son obligatorios."},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        cantidad = int(cantidad_str)
        if cantidad < 0:
            raise ValueError("La cantidad no puede ser negativa.")
    except ValueError as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        producto = get_object_or_404(Producto, pk=producto_id)

        inventario = InventarioProducto.objects.create(
            producto=producto,
            cantidad_unidades=cantidad,
            creado_por=request.user
        )

        inventario_recargado = InventarioProducto.objects.select_related('producto', 'creado_por').get(pk=inventario.pk)
        return Response(serialize_inventario(inventario_recargado), status=status.HTTP_201_CREATED)

    except Exception as e:
        return Response(
            {"error": f"Error al crear el inventario: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# --- 2. Listar Inventarios (GET) con filtros ---
@api_view(['GET'])
@permission_classes([IsAuthenticated, RolePermission(INVENTORY_MANAGER_ROLES)])
def list_inventarios(request):
    try:
        inventarios = InventarioProducto.objects.select_related('producto', 'creado_por').filter(deleted_at__isnull=True)

        search_query = request.query_params.get('search', None)
        start_date_str = request.query_params.get('start_date', None)
        end_date_str = request.query_params.get('end_date', None)

        # --- Filtro de texto ---
        if search_query:
            inventarios = inventarios.filter(
                Q(producto__nombre__icontains=search_query)
            )

        # --- Filtros por fechas ---
        if start_date_str:
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                start_datetime = datetime.combine(start_date, time.min)
                inventarios = inventarios.filter(fecha_ingreso__gte=start_datetime)
            except ValueError:
                return Response({"error": "Formato de fecha de inicio inválido (YYYY-MM-DD)."}, status=status.HTTP_400_BAD_REQUEST)

        if end_date_str:
            try:
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
                end_datetime = datetime.combine(end_date, time.max)
                inventarios = inventarios.filter(fecha_ingreso__lte=end_datetime)
            except ValueError:
                return Response({"error": "Formato de fecha de fin inválido (YYYY-MM-DD)."}, status=status.HTTP_400_BAD_REQUEST)

        inventarios = inventarios.order_by('-fecha_actualizacion')

        # --- Paginación ---
        paginator = PageNumberPagination()
        paginator.page_size = 15
        paginated_inventarios = paginator.paginate_queryset(inventarios, request)

        data = [serialize_inventario(i) for i in paginated_inventarios]

        # --- Total de unidades ---
        total_unidades = inventarios.aggregate(total=Sum('cantidad_unidades'))['total'] or 0

        return paginator.get_paginated_response({
            "results": data,
            "total_unidades": total_unidades,
            "filtros_aplicados": {
                "search": search_query,
                "start_date": start_date_str,
                "end_date": end_date_str,
            }
        })

    except Exception as e:
        return Response(
            {"error": f"Error al obtener el listado de inventarios: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# --- 3. Obtener detalle de Inventario ---
@api_view(['GET'])
@permission_classes([IsAuthenticated, RolePermission(INVENTORY_MANAGER_ROLES)])
def get_inventario(request, pk):
    inventario = get_object_or_404(
        InventarioProducto.objects.select_related('producto', 'creado_por').filter(deleted_at__isnull=True),
        pk=pk
    )
    return Response(serialize_inventario(inventario), status=status.HTTP_200_OK)


# --- 4. Actualizar Inventario ---
@api_view(['PUT', 'PATCH'])
@permission_classes([IsAuthenticated, RolePermission(INVENTORY_MANAGER_ROLES)])
def update_inventario(request, pk):
    try:
        inventario = get_object_or_404(InventarioProducto.objects.filter(deleted_at__isnull=True), pk=pk)

        cantidad_str = request.data.get('cantidad_unidades', inventario.cantidad_unidades)
        producto_id = request.data.get('producto_id', inventario.producto_id)

        try:
            cantidad = int(cantidad_str)
            if cantidad < 0:
                raise ValueError("La cantidad no puede ser negativa.")
            inventario.cantidad_unidades = cantidad
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        # Actualizar producto si es diferente
        if producto_id != inventario.producto_id:
            producto = get_object_or_404(Producto, pk=producto_id)
            inventario.producto = producto

        inventario.save()

        inventario_updated = InventarioProducto.objects.select_related('producto', 'creado_por').get(pk=pk)
        return Response(serialize_inventario(inventario_updated), status=status.HTTP_200_OK)

    except Exception as e:
        return Response(
            {"error": f"Error al actualizar el inventario: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# --- 5. Eliminar Inventario (Soft Delete) ---
@api_view(['DELETE'])
@permission_classes([IsAuthenticated, RolePermission(INVENTORY_MANAGER_ROLES)])
def delete_inventario(request, pk):
    try:
        inventario = get_object_or_404(InventarioProducto.objects.filter(deleted_at__isnull=True), pk=pk)
        inventario.delete()  # Se asume que BaseModel implementa soft delete
        return Response(
            {"message": "Inventario eliminado lógicamente exitosamente", "deleted_at": inventario.deleted_at},
            status=status.HTTP_200_OK
        )
    except Exception as e:
        return Response(
            {"error": f"Error al eliminar el inventario: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
@permission_classes([IsAuthenticated, RolePermission(INVENTORY_MANAGER_ROLES)])
def get_total_unidades_producto(request, producto_id):
    """
    Retorna la cantidad total de unidades disponibles para un producto,
    sumando todos los registros de inventario activos.
    """
    try:
        total = (
            InventarioProducto.objects
            .filter(producto_id=producto_id, deleted_at__isnull=True)
            .aggregate(total_unidades=Sum('cantidad_unidades'))['total_unidades'] or 0
        )

        return Response({
            "producto_id": producto_id,
            "total_unidades": total
        }, status=status.HTTP_200_OK)

    except Exception as e:
        return Response(
            {"error": f"Error al obtener el total de unidades: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
@permission_classes([RolePermission(INVENTORY_MANAGER_ROLES)])
def get_inventario_by_producto(request, producto_id):
    """
    🔍 Obtener inventario(s) por ID de producto

    Devuelve todos los inventarios activos asociados a un producto.

    Ejemplo:
      GET /api/inventario/producto/12/

    Respuesta esperada:
    [
      {
        "id": 5,
        "producto_id": 12,
        "producto_nombre": "Mouse Logitech M720",
        "cantidad_unidades": 80,
        "fecha_ingreso": "2025-10-02T15:34:21Z",
        "fecha_actualizacion": "2025-11-07T17:10:03Z",
        "creado_por_username": "sergio",
        "deleted_at": null
      }
    ]
    """

    # 🔹 Obtener todos los inventarios activos asociados al producto
    inventarios = get_list_or_404(
        InventarioProducto.objects.select_related('producto', 'creado_por').filter(deleted_at__isnull=True),
        producto__id=producto_id
    )

    # 🔹 Construir respuesta manual (sin serializer)
    data = [
        {
            "id": inv.id,
            "producto_id": inv.producto_id,
            "producto_nombre": inv.producto.nombre if inv.producto else None,
            "cantidad_unidades": inv.cantidad_unidades,
            "fecha_ingreso": inv.fecha_ingreso,
            "fecha_actualizacion": inv.fecha_actualizacion,
            "creado_por_username": inv.creado_por.username if inv.creado_por else None,
            "deleted_at": inv.deleted_at,
        }
        for inv in inventarios
    ]

    return Response(data, status=status.HTTP_200_OK)
  
def get_total_unidades_producto_call(producto_id):
    """
        Retorna la cantidad total de unidades disponibles para un producto,
        sumando todos los registros de inventario activos.
    """
    try:
        total = (
            InventarioProducto.objects
            .filter(producto_id=producto_id, deleted_at__isnull=True)
            .aggregate(total_unidades=Sum('cantidad_unidades'))['total_unidades'] or 0
        )
        return total
    except Exception as e:
        return 0