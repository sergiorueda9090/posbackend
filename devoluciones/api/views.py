from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from django.shortcuts import get_object_or_404
from datetime import datetime
from decimal import Decimal
from django.db.models import Q
from user.api.permissions import RolePermission
from devoluciones.models import Devoluciones
from ventas.models import Venta, DetalleVenta
from inventarioproducto.models import InventarioProducto
from productos.models import Producto

DEVOLUTION_MANAGER_ROLES = ['admin', 'manager', 'contador']

def serialize_devolucion(dev, productos_dict):
    return {
        "id": dev.id,
        "codigo_venta": dev.codigo_venta,
        "producto_id": dev.producto_id,
        "nombre_producto": productos_dict.get(dev.producto_id, "Producto no encontrado"),
        "cantidad": dev.cantidad,
        "created_at": dev.created_at,
    }

@api_view(['POST'])
@permission_classes([IsAuthenticated, RolePermission(DEVOLUTION_MANAGER_ROLES)])
def create_devolucion(request):

    venta_completa_id = request.data.get("venta_completa_id")
    detalle_venta_id  = request.data.get("detalle_venta_id")
    codigo_venta      = request.data.get("codigo_venta")
    producto_id       = request.data.get("producto_id")
    cantidad          = request.data.get("cantidad")

    if not venta_completa_id or not codigo_venta or not producto_id or not cantidad or not detalle_venta_id:
        return Response(
            {"error": "venta_completa_id, codigo_venta, producto_id, cantidad y detalle_venta_id son obligatorios."},
            status=status.HTTP_400_BAD_REQUEST
        )

    # =============================
    # 🔍 2. Validar cantidad
    # =============================
    try:
        cantidad = int(cantidad)
        if cantidad <= 0:
            raise ValueError
    except:
        return Response({"error": "Cantidad debe ser un número entero positivo."},
                        status=status.HTTP_400_BAD_REQUEST)

    # =============================
    # 🔍 1. Obtener venta
    # =============================
    venta = get_object_or_404(Venta, pk=venta_completa_id)

    # =============================
    # 🔍 2. Obtener detalle del producto
    # =============================
    try:
        detalle = DetalleVenta.objects.get(
            id=detalle_venta_id,
            venta_id=venta_completa_id,
            producto_id=producto_id
        )
    except DetalleVenta.DoesNotExist:
        return Response(
            {"error": "Este producto no pertenece a la venta indicada."},
            status=status.HTTP_400_BAD_REQUEST
        )

    # =============================
    # 🔍 3. Validar cantidad a devolver
    # =============================
    if cantidad > detalle.cantidad:
        return Response(
            {"error": f"No se pueden devolver más productos ({cantidad}) que los vendidos ({detalle.cantidad})."},
            status=status.HTTP_400_BAD_REQUEST
        )

    # =============================
    # 🔥 4. Registrar la devolución
    # =============================
    devolucion = Devoluciones.objects.create(
        codigo_venta=codigo_venta,
        producto_id=producto_id,
        cantidad=cantidad
    )

    # =============================
    # 🧮 5. Actualizar o eliminar el detalle de venta
    # =============================
    if cantidad == detalle.cantidad:
        detalle.delete()
    else:
        detalle.cantidad -= cantidad
        detalle.save()

    # =============================
    # 🔁 6. Recalcular subtotal, impuesto y total
    # =============================

    detalles_actuales = DetalleVenta.objects.filter(venta_id=venta_completa_id)

    nuevo_subtotal = Decimal('0.00')
    nuevo_impuesto = Decimal('0.00')

    for d in detalles_actuales:
        subtotal_item = d.precio_unitario * d.cantidad
        nuevo_subtotal += subtotal_item
        nuevo_impuesto += subtotal_item * Decimal("0.16")  # IVA 16%

    venta.subtotal = nuevo_subtotal
    venta.impuesto = nuevo_impuesto
    venta.total = nuevo_subtotal + nuevo_impuesto
    venta.save()

    # ======================================================
    # 7️⃣ SUMAR UNIDADES DEVUELTAS AL INVENTARIO (FIFO simple)
    # ======================================================
    try:
        producto = Producto.objects.get(pk=producto_id)

        # Obtener el inventario más reciente (FIFO básico)
        inventario = InventarioProducto.objects.filter(
            producto=producto
        ).order_by('-fecha_ingreso').first()

        if inventario:
            inventario.cantidad_unidades += cantidad
            inventario.save()
        else:
            # Si no existe inventario, crear una entrada nueva
            InventarioProducto.objects.create(
                producto=producto,
                cantidad_unidades=cantidad,
                creado_por=request.user
            )

    except Exception as e:
        print("⚠ Error al actualizar inventario:", str(e))

    # =============================
    # 8. Retornar resultado
    # =============================
    return Response({
        "message": "Devolución realizada correctamente.",
        "devolucion": serialize_devolucion(devolucion),
        "venta_actualizada": {
            "subtotal": venta.subtotal,
            "impuesto": venta.impuesto,
            "total": venta.total
        }
    }, status=status.HTTP_201_CREATED)

@api_view(['GET'])
@permission_classes([IsAuthenticated, RolePermission(DEVOLUTION_MANAGER_ROLES)])
def list_devoluciones(request):
    queryset = Devoluciones.objects.filter(deleted_at__isnull=True)

    # ===============================
    # 🔎 BUSCADOR GLOBAL (search)
    # ===============================
    search = request.query_params.get("search")
    if search:

        # 1️⃣ Buscar por código de venta
        condiciones = Q(codigo_venta__icontains=search)

        # 2️⃣ Buscar por nombre del producto (JOIN manual)
        productos = Producto.objects.filter(nombre__icontains=search)

        if productos.exists():
            producto_ids = productos.values_list("id", flat=True)
            condiciones |= Q(producto_id__in=producto_ids)

        # 3️⃣ Buscar por producto_id cuando search es número
        if search.isdigit():
            condiciones |= Q(producto_id=int(search))

        queryset = queryset.filter(condiciones)

    # ===============================
    # Rango de fechas
    # ===============================
    fecha_inicio = request.query_params.get("start_date")
    fecha_fin = request.query_params.get("end_date")

    if fecha_inicio:
        fi = datetime.strptime(fecha_inicio, "%Y-%m-%d")
        queryset = queryset.filter(created_at__date__gte=fi)

    if fecha_fin:
        ff = datetime.strptime(fecha_fin, "%Y-%m-%d")
        queryset = queryset.filter(created_at__date__lte=ff)

    queryset = queryset.order_by("-created_at")

    # ===============================
    # ⚡ OPTIMIZACIÓN
    # ===============================
    producto_ids = queryset.values_list("producto_id", flat=True).distinct()
    productos_dict = {
        p.id: p.nombre
        for p in Producto.objects.filter(id__in=producto_ids)
    }

    # ===============================
    # PAGINACIÓN
    # ===============================
    paginator = PageNumberPagination()
    paginator.page_size = 20
    page = paginator.paginate_queryset(queryset, request)

    data = [serialize_devolucion(dev, productos_dict) for dev in page]

    return paginator.get_paginated_response(data)

@api_view(['GET'])
@permission_classes([IsAuthenticated, RolePermission(DEVOLUTION_MANAGER_ROLES)])
def get_devolucion(request, pk):
    dev = get_object_or_404(
        Devoluciones.objects.filter(deleted_at__isnull=True),
        pk=pk
    )
    return Response(serialize_devolucion(dev), status=status.HTTP_200_OK)

@api_view(['PUT', 'PATCH'])
@permission_classes([IsAuthenticated, RolePermission(DEVOLUTION_MANAGER_ROLES)])
def update_devolucion(request, pk):
    dev = get_object_or_404(Devoluciones.objects.filter(deleted_at__isnull=True), pk=pk)

    codigo_venta = request.data.get("codigo_venta", dev.codigo_venta)
    producto_id = request.data.get("producto_id", dev.producto_id)
    cantidad = request.data.get("cantidad", dev.cantidad)

    try:
        cantidad = int(cantidad)
        if cantidad <= 0:
            raise ValueError
    except:
        return Response({"error": "Cantidad debe ser un número entero positivo."},
                        status=status.HTTP_400_BAD_REQUEST)

    dev.codigo_venta = codigo_venta
    dev.producto_id = producto_id
    dev.cantidad = cantidad
    dev.save()

    return Response(serialize_devolucion(dev), status=status.HTTP_200_OK)


    dev = get_object_or_404(Devoluciones.objects.filter(deleted_at__isnull=True), pk=pk)

    dev.delete()  # BaseModel debe manejar deleted_at

    return Response(
        {"message": "Devolución eliminada correctamente", "deleted_at": dev.deleted_at},
        status=status.HTTP_200_OK
    )