from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from django.shortcuts import get_object_or_404
from django.db import IntegrityError, DatabaseError, transaction
from django.db.models import Q, Sum, F, DecimalField
from decimal import Decimal

from user.api.permissions import RolePermission
from combos.models import Combo, ProductoCombo
from productos.models import Producto
from proveedores.models import OrdenProveedorDetalle
from ventas.models import DetalleVenta

COMBO_MANAGER_ROLES = ['admin', 'vendedor']


# ======================================================
# Crear Combo (POST)
# ======================================================
@api_view(['POST'])
@permission_classes([IsAuthenticated, RolePermission(COMBO_MANAGER_ROLES)])
def create_combo(request):
    try:
        nombre = request.data.get('nombre')
        activo_raw = request.data.get('activo', True)

        if isinstance(activo_raw, str):
            activo = activo_raw.lower() in ['true', '1', 'yes']
        else:
            activo = bool(activo_raw)

        if not nombre:
            return Response(
                {"error": "El nombre del combo es obligatorio."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validar que no exista un combo con el mismo nombre
        if Combo.objects.filter(nombre__iexact=nombre).exists():
            return Response(
                {"error": "Ya existe un combo con ese nombre."},
                status=status.HTTP_400_BAD_REQUEST
            )

        combo = Combo.objects.create(
            nombre=nombre,
            activo=activo,
            creado_por=request.user
        )

        data = {
            "id": combo.id,
            "nombre": combo.nombre,
            "activo": combo.activo,
            "precio_total": float(combo.precio_total),
            "creado_por": combo.creado_por.username if combo.creado_por else None,
            "created_at": combo.created_at,
        }

        return Response(data, status=status.HTTP_201_CREATED)

    except IntegrityError:
        return Response(
            {"error": "Error de integridad al crear el combo."},
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        return Response(
            {"error": f"Error inesperado al crear el combo: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# ======================================================
# Listar Combos (GET)
# ======================================================
@api_view(['GET'])
@permission_classes([IsAuthenticated, RolePermission(COMBO_MANAGER_ROLES)])
def list_combos(request):
    try:
        combos = Combo.objects.select_related('creado_por').prefetch_related(
            'productos_combo__producto'
        ).all()

        search = request.query_params.get('search')
        activo = request.query_params.get('activo')

        if search:
            combos = combos.filter(
                Q(nombre__icontains=search)
            )

        if activo is not None:
            activo_bool = activo.lower() in ['true', '1', 'yes']
            combos = combos.filter(activo=activo_bool)

        combos = combos.order_by('-created_at')

        paginator = PageNumberPagination()
        paginator.page_size = 10
        page = paginator.paginate_queryset(combos, request)

        data = []
        for combo in page:
            data.append({
                "id": combo.id,
                "nombre": combo.nombre,
                "activo": combo.activo,
                "precio_total": float(combo.precio_total),
                "num_productos": combo.productos_combo.count(),
                "creado_por": combo.creado_por.username if combo.creado_por else None,
                "created_at": combo.created_at,
            })

        return paginator.get_paginated_response(data)

    except Exception as e:
        return Response(
            {"error": f"Error al listar los combos: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# ======================================================
# Obtener Combo por ID (GET /<id>/)
# ======================================================
@api_view(['GET'])
@permission_classes([IsAuthenticated, RolePermission(COMBO_MANAGER_ROLES)])
def get_combo(request, pk):
    combo = get_object_or_404(
        Combo.objects.prefetch_related('productos_combo__producto'),
        pk=pk
    )

    productos = []
    for pc in combo.productos_combo.all():
        productos.append({
            "id": pc.id,
            "producto_id": pc.producto.id,
            "producto_nombre": pc.producto.nombre,
            "precio_combo": float(pc.precio_combo),
            "cantidad": pc.cantidad,
            "subtotal": float(pc.precio_combo * pc.cantidad),
        })

    data = {
        "id": combo.id,
        "nombre": combo.nombre,
        "activo": combo.activo,
        "precio_total": float(combo.precio_total),
        "productos": productos,
        "creado_por": combo.creado_por.username if combo.creado_por else None,
        "created_at": combo.created_at,
    }

    return Response(data, status=status.HTTP_200_OK)


# ======================================================
# Actualizar Combo (PUT /<id>/update/)
# ======================================================
@api_view(['PUT', 'PATCH'])
@permission_classes([IsAuthenticated, RolePermission(COMBO_MANAGER_ROLES)])
def update_combo(request, pk):
    combo = get_object_or_404(Combo, pk=pk)

    try:
        nombre = request.data.get('nombre', combo.nombre)
        activo = request.data.get('activo', combo.activo)

        # Validar nombre único si cambió
        if nombre != combo.nombre:
            if Combo.objects.filter(nombre__iexact=nombre).exclude(id=combo.id).exists():
                return Response(
                    {"error": "Ya existe un combo con ese nombre."},
                    status=status.HTTP_400_BAD_REQUEST
                )

        combo.nombre = nombre
        combo.activo = activo
        combo.save()

        return Response(
            {"message": "Combo actualizado correctamente."},
            status=status.HTTP_200_OK
        )

    except Exception as e:
        return Response(
            {"error": f"Error al actualizar el combo: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# ======================================================
# Eliminar Combo (DELETE /<id>/delete/)
# ======================================================
@api_view(['DELETE'])
@permission_classes([IsAuthenticated, RolePermission(['admin'])])
def delete_combo(request, pk):
    combo = get_object_or_404(Combo, pk=pk)

    try:
        combo.delete()  # Soft delete
        return Response(
            {"message": "Combo eliminado correctamente."},
            status=status.HTTP_200_OK
        )
    except DatabaseError:
        return Response(
            {"error": "Error de base de datos al eliminar el combo."},
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        return Response(
            {"error": f"Error inesperado al eliminar el combo: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# ======================================================
# Agregar Producto a Combo (POST /<id>/add-product/)
# ======================================================
@api_view(['POST'])
@permission_classes([IsAuthenticated, RolePermission(COMBO_MANAGER_ROLES)])
def add_product_to_combo(request, pk):
    combo = get_object_or_404(Combo, pk=pk)

    try:
        producto_id = request.data.get('producto_id')
        precio_combo = request.data.get('precio_combo')
        cantidad = request.data.get('cantidad', 1)

        if not producto_id or not precio_combo:
            return Response(
                {"error": "producto_id y precio_combo son obligatorios."},
                status=status.HTTP_400_BAD_REQUEST
            )

        producto = get_object_or_404(Producto, id=producto_id)
        precio_combo = Decimal(precio_combo)
        cantidad = int(cantidad)

        if cantidad < 1:
            return Response(
                {"error": "La cantidad debe ser mayor a 0."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validar que el producto no esté ya en el combo
        if ProductoCombo.objects.filter(combo=combo, producto=producto).exists():
            return Response(
                {"error": "Este producto ya está en el combo."},
                status=status.HTTP_400_BAD_REQUEST
            )

        producto_combo = ProductoCombo.objects.create(
            combo=combo,
            producto=producto,
            precio_combo=precio_combo,
            cantidad=cantidad
        )

        data = {
            "id": producto_combo.id,
            "producto_id": producto.id,
            "producto_nombre": producto.nombre,
            "precio_combo": float(producto_combo.precio_combo),
            "cantidad": producto_combo.cantidad,
            "subtotal": float(producto_combo.precio_combo * producto_combo.cantidad),
        }

        return Response(data, status=status.HTTP_201_CREATED)

    except IntegrityError:
        return Response(
            {"error": "Error de integridad al agregar el producto."},
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        return Response(
            {"error": f"Error inesperado: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# ======================================================
# Eliminar Producto de Combo (DELETE /<combo_id>/remove-product/<producto_combo_id>/)
# ======================================================
@api_view(['DELETE'])
@permission_classes([IsAuthenticated, RolePermission(COMBO_MANAGER_ROLES)])
def remove_product_from_combo(request, pk, producto_combo_id):
    combo = get_object_or_404(Combo, pk=pk)
    producto_combo = get_object_or_404(ProductoCombo, id=producto_combo_id, combo=combo)

    try:
        producto_combo.delete()  # Soft delete
        return Response(
            {"message": "Producto eliminado del combo correctamente."},
            status=status.HTTP_200_OK
        )
    except Exception as e:
        return Response(
            {"error": f"Error al eliminar el producto: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# ======================================================
# Actualizar Precio de Producto en Combo (PUT /<combo_id>/update-product/<producto_combo_id>/)
# ======================================================
@api_view(['PUT', 'PATCH'])
@permission_classes([IsAuthenticated, RolePermission(COMBO_MANAGER_ROLES)])
def update_product_in_combo(request, pk, producto_combo_id):
    combo = get_object_or_404(Combo, pk=pk)
    producto_combo = get_object_or_404(ProductoCombo, id=producto_combo_id, combo=combo)

    try:
        precio_combo = request.data.get('precio_combo', producto_combo.precio_combo)
        cantidad = request.data.get('cantidad', producto_combo.cantidad)

        producto_combo.precio_combo = Decimal(precio_combo)
        producto_combo.cantidad = int(cantidad)

        if producto_combo.cantidad < 1:
            return Response(
                {"error": "La cantidad debe ser mayor a 0."},
                status=status.HTTP_400_BAD_REQUEST
            )

        producto_combo.save()

        return Response(
            {"message": "Producto actualizado en combo correctamente."},
            status=status.HTTP_200_OK
        )
    except Exception as e:
        return Response(
            {"error": f"Error al actualizar el producto: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# ======================================================
# Obtener Combos Activos para POS (GET /active/)
# ======================================================
@api_view(['GET'])
@permission_classes([IsAuthenticated, RolePermission(COMBO_MANAGER_ROLES)])
def get_active_combos(request):
    """
    Endpoint optimizado para el POS que retorna solo combos activos
    con información de stock disponible para cada producto.
    """
    try:
        combos = Combo.objects.filter(activo=True).prefetch_related(
            'productos_combo__producto'
        ).order_by('nombre')

        data = []

        for combo in combos:
            productos_info = []
            stock_minimo = float('inf')  # Para calcular cuántos combos se pueden vender

            for pc in combo.productos_combo.all():
                # Calcular stock disponible del producto
                cantidad_recibida = (
                    OrdenProveedorDetalle.objects
                    .filter(
                        orden_proveedor__estado='recibida',
                        producto_id=pc.producto.id,
                        deleted_at__isnull=True
                    )
                    .aggregate(total=Sum('cantidad'))['total'] or 0
                )

                cantidad_vendida = (
                    DetalleVenta.objects
                    .filter(
                        producto_id=pc.producto.id,
                        deleted_at__isnull=True
                    )
                    .aggregate(total=Sum('cantidad'))['total'] or 0
                )

                stock_disponible = cantidad_recibida - cantidad_vendida

                # Calcular cuántos combos se pueden hacer con este producto
                combos_posibles = stock_disponible // pc.cantidad if pc.cantidad > 0 else 0
                stock_minimo = min(stock_minimo, combos_posibles)

                productos_info.append({
                    "producto_id": pc.producto.id,
                    "producto_nombre": pc.producto.nombre,
                    "precio_combo": float(pc.precio_combo),
                    "cantidad": pc.cantidad,
                    "stock_disponible": stock_disponible,
                })

            # Si stock_minimo es infinito, significa que no hay productos en el combo
            cantidad_maxima_combos = int(stock_minimo) if stock_minimo != float('inf') else 0

            data.append({
                "id": combo.id,
                "nombre": combo.nombre,
                "precio_total": float(combo.precio_total),
                "productos": productos_info,
                "cantidadMaxima": cantidad_maxima_combos,
                "isCombo": True,
            })

        return Response(data, status=status.HTTP_200_OK)

    except Exception as e:
        return Response(
            {"error": f"Error al obtener combos activos: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
