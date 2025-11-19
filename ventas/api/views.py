from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from django.shortcuts import get_object_or_404
from django.db import transaction, IntegrityError, DatabaseError
from decimal import Decimal
from django.db.models import Q, Sum, F, DecimalField, ExpressionWrapper, Prefetch
from django.utils.timezone import now
from django.utils import timezone
from datetime import datetime, timedelta

from user.api.permissions import RolePermission
from ventas.models import Venta, DetalleVenta
from productos.models import Producto
from clientes.models import Cliente
from inventarioproducto.models import InventarioProducto

import json
VENTA_MANAGER_ROLES = ['admin', 'vendedor']  # Ajusta según tu modelo de permisos

# ======================================================
# Crear Venta (POST)
# ======================================================
@api_view(['POST'])
@permission_classes([IsAuthenticated, RolePermission(VENTA_MANAGER_ROLES)])
def create_venta(request):
    try:
        with transaction.atomic():
            data = request.data

            # ===============================
            # 🔹 Validar y obtener campos base
            # ===============================
            cliente_id    = data.get('cliente_id')
            metodo_pago   = data.get('metodo_pago', 'Efectivo')
            recibido      = Decimal(data.get('recibido', '0'))
            cambio        = Decimal(data.get('cambio', '0'))
            subtotal      = Decimal(data.get('subtotal', '0'))
            descuento     = Decimal(data.get('descuento', '0'))
            impuesto      = Decimal(data.get('impuesto', '0'))
            total         = Decimal(data.get('total', '0'))
            items         = data.get('items', [])

            # Si items llega como string JSON, decodificarlo
            if isinstance(items, str):
                try:
                    items = json.loads(items)
                except json.JSONDecodeError:
                    return Response(
                        {"error": "Formato inválido para 'items'. Debe ser JSON válido."},
                        status=status.HTTP_400_BAD_REQUEST
                    )

            if not isinstance(items, list):
                return Response(
                    {"error": "'items' debe ser una lista de productos."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            if not items:
                return Response(
                    {"error": "Debe incluir al menos un producto en la venta."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # ===============================
            # 🔹 Crear venta principal
            # ===============================
            cliente = get_object_or_404(Cliente, id=cliente_id) if cliente_id else None

            venta = Venta.objects.create(
                codigo      = f"V-{Venta.objects.count() + 1:05d}",
                cliente     = cliente,
                metodo_pago = metodo_pago,
                recibido    = recibido,
                cambio      = cambio,
                subtotal    = subtotal,
                descuento   = descuento,
                impuesto    = impuesto,
                total       = total,
                creado_por  = request.user
            )

            # ===============================
            # 🔹 Crear detalle y actualizar inventario (FIFO)
            # ===============================
            for item in items:
                producto_id     = item.get('id')
                cantidad        = int(item.get('quantity', 1))
                precio_unitario = Decimal(item.get('precio_final', '0'))

                producto = get_object_or_404(Producto, id=producto_id)

                # Crear detalle de venta
                DetalleVenta.objects.create(
                    venta           = venta,
                    producto        = producto,
                    cantidad        = cantidad,
                    precio_unitario = precio_unitario,
                )

                # ======================================================
                # 🔹 Descontar unidades del inventario (FIFO)
                # ======================================================
                inventarios = InventarioProducto.objects.filter(
                    producto=producto
                ).order_by('fecha_ingreso')  # FIFO: más antiguo primero

                cantidad_restante = cantidad

                for inv in inventarios:
                    if cantidad_restante <= 0:
                        break

                    if inv.cantidad_unidades >= cantidad_restante:
                        inv.cantidad_unidades -= cantidad_restante
                        inv.save(update_fields=['cantidad_unidades', 'fecha_actualizacion'])
                        cantidad_restante = 0
                    else:
                        cantidad_restante -= inv.cantidad_unidades
                        inv.cantidad_unidades = 0
                        inv.save(update_fields=['cantidad_unidades', 'fecha_actualizacion'])

                # Si no hay suficiente stock, lanzar error
                if cantidad_restante > 0:
                    raise IntegrityError(f"Inventario insuficiente para el producto {producto.nombre}")

            # ===============================
            # 🔹 Respuesta final
            # ===============================
            response_data = {
                "id"     : venta.id,
                "codigo" : venta.codigo,
                "cliente": venta.cliente.nombre if venta.cliente else "Venta rápida",
                "mensaje": "✅ Venta creada correctamente y stock actualizado (FIFO)."
            }

            return Response(response_data, status=status.HTTP_201_CREATED)

    except IntegrityError as e:
        return Response({"error": f"Error de integridad al crear la venta: {str(e)}"},
                        status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({"error": f"Error inesperado al crear la venta: {str(e)}"},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ======================================================
# Listar Ventas (GET)
# ======================================================
@api_view(['GET'])
@permission_classes([IsAuthenticated, RolePermission(VENTA_MANAGER_ROLES)])
def list_ventas(request):
    try:
        ventas = Venta.objects.select_related('cliente', 'creado_por').prefetch_related('detalles').all()

        search = request.query_params.get('search')
        metodo_pago = request.query_params.get('metodo_pago')

        if search:
            ventas = ventas.filter(
                Q(codigo__icontains=search) |
                Q(cliente__nombre__icontains=search)
            )
        if metodo_pago:
            ventas = ventas.filter(metodo_pago=metodo_pago)

        ventas = ventas.order_by('-creado_en')

        paginator = PageNumberPagination()
        paginator.page_size = 10
        page = paginator.paginate_queryset(ventas, request)

        data = []
        for v in page:
            data.append({
                "id": v.id,
                "codigo": v.codigo,
                "cliente": v.cliente.nombre if v.cliente else "Venta rápida",
                "metodo_pago": v.metodo_pago,
                "subtotal": float(v.subtotal),
                "impuesto": float(v.impuesto),
                "total": float(v.total),
                "recibido": float(v.recibido),
                "cambio": float(v.cambio),
                "creado_por": v.creado_por.username if v.creado_por else None,
                "fecha": v.creado_en,
                "num_productos": v.detalles.aggregate(total=Sum('cantidad'))['total'] or 0
            })

        return paginator.get_paginated_response(data)

    except Exception as e:
        return Response({"error": f"Error al listar las ventas: {str(e)}"},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ======================================================
# Obtener Venta por ID (GET /ventas/<id>/)
# ======================================================
@api_view(['GET'])
@permission_classes([IsAuthenticated, RolePermission(VENTA_MANAGER_ROLES)])
def get_venta(request, pk):
    venta = get_object_or_404(Venta.objects.select_related('cliente', 'creado_por').prefetch_related('detalles__producto'), pk=pk)

    detalles = [{
        "producto": d.producto.nombre,
        "cantidad": d.cantidad,
        "precio_unitario": float(d.precio_unitario),
        "subtotal": float(d.subtotal),
        "impuesto": float(d.impuesto),
        "total": float(d.total)
    } for d in venta.detalles.all()]

    data = {
        "id": venta.id,
        "codigo": venta.codigo,
        "cliente": venta.cliente.nombre if venta.cliente else None,
        "metodo_pago": venta.metodo_pago,
        "subtotal": float(venta.subtotal),
        "impuesto": float(venta.impuesto),
        "total": float(venta.total),
        "recibido": float(venta.recibido),
        "cambio": float(venta.cambio),
        "detalles": detalles,
        "observaciones": venta.observaciones,
        "creado_por": venta.creado_por.username if venta.creado_por else None,
        "fecha": venta.creado_en,
    }

    return Response(data, status=status.HTTP_200_OK)


# ======================================================
# Eliminar Venta (DELETE /ventas/<id>/delete/)
# ======================================================
@api_view(['DELETE'])
@permission_classes([IsAuthenticated, RolePermission(['admin'])])
def delete_venta(request, pk):
    venta = get_object_or_404(Venta, pk=pk)
    try:
        venta.delete()
        return Response({"message": "Venta eliminada correctamente."}, status=status.HTTP_200_OK)
    except DatabaseError:
        return Response({"error": "Error de base de datos al eliminar la venta."},
                        status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({"error": f"Error inesperado al eliminar la venta: {str(e)}"},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated, RolePermission(['admin'])])
def resumen_ventas_view(request):
    """
    Retorna el total de ventas y unidades vendidas del día actual o de un rango personalizado.
    Parámetros opcionales:
      - fecha_inicio (YYYY-MM-DD)
      - fecha_fin (YYYY-MM-DD)
    """
    try:
        # Obtener parámetros GET (si existen)
        fecha_inicio = request.GET.get("start_date")
        fecha_fin = request.GET.get("end_date")

        if fecha_inicio and fecha_fin:
            # ✅ Si se envía rango de fechas
            fecha_inicio = datetime.strptime(fecha_inicio, "%Y-%m-%d")
            fecha_fin = datetime.strptime(fecha_fin, "%Y-%m-%d") + timedelta(days=1)

            ventas = Venta.objects.filter(created_at__range=(fecha_inicio, fecha_fin))
            detalles = DetalleVenta.objects.filter(venta__created_at__range=(fecha_inicio, fecha_fin))

        else:
            # ✅ Si no se envían fechas: mostrar solo las ventas de hoy
            hoy = timezone.now().date()
            ventas = Venta.objects.filter(created_at__date=hoy)
            detalles = DetalleVenta.objects.filter(venta__created_at__date=hoy)

        # 💰 Total de ventas
        total_ventas = ventas.aggregate(total=Sum("total"))["total"] or 0

        # 📦 Total de unidades vendidas
        total_unidades = detalles.aggregate(total=Sum("cantidad"))["total"] or 0

        # 📊 Total de transacciones
        total_transacciones = ventas.count()

        #Respuesta JSON

        return Response({
            "status": "sucess",
            "fecha_inicio": fecha_inicio.strftime("%Y-%m-%d") if fecha_inicio else str(hoy),
            "fecha_fin": (fecha_fin - timedelta(days=1)).strftime("%Y-%m-%d") if fecha_fin else str(hoy),
            "total_ventas": float(total_ventas),
            "total_unidades_vendidas": int(total_unidades),
            "total_transacciones": total_transacciones
        }, status=status.HTTP_200_OK)


    except Exception as e:
        return Response({"error": f"Error al obtener el resumen de ventas: {str(e)}"},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def reporte_ventas(request):
    """
    🧾 Reporte detallado y entendible de ventas.
    
    Permite obtener un resumen general, desglose por métodos de pago,
    listado de productos más vendidos y detalle completo de cada venta
    (incluyendo los productos comprados por el cliente).

    Parámetros opcionales:
    - fecha_inicio: YYYY-MM-DD
    - fecha_fin: YYYY-MM-DD

    Ejemplos:
    - GET /api/ventas/reporte/                     → Reporte del día actual
    - GET /api/ventas/reporte/?fecha_inicio=2025-11-01&fecha_fin=2025-11-07
    """

    # === 1️⃣ Definir rango de fechas ===
    fecha_inicio = request.GET.get("start_date")
    fecha_fin    = request.GET.get("end_date")

    try:
        if fecha_inicio and fecha_fin:
            inicio = datetime.strptime(fecha_inicio, "%Y-%m-%d")
            fin = datetime.strptime(fecha_fin, "%Y-%m-%d") + timedelta(days=1)
            rango_texto = f"📆 Desde {fecha_inicio} hasta {fecha_fin}"
        else:
            hoy = now().date()
            inicio = hoy
            fin = hoy + timedelta(days=1)
            rango_texto = f"📅 Reporte del día: {hoy.strftime('%Y-%m-%d')}"
    except ValueError:
        return Response(
            {"error": "Formato de fecha inválido. Use YYYY-MM-DD."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # === 2️⃣ Obtener ventas del rango ===
    ventas = (
        Venta.objects.filter(created_at__range=[inicio, fin])
        .select_related("cliente", "creado_por")
        .prefetch_related(Prefetch("detalles", queryset=DetalleVenta.objects.select_related("producto")))
        .order_by("-created_at")
    )

    if not ventas.exists():
        return Response(
            {
                "mensaje": "No se encontraron ventas en el rango seleccionado.",
                "rango": rango_texto,
                "resumen_general": {},
            },
            status=status.HTTP_200_OK,
        )

    # === 3️⃣ Cálculos generales ===
    total_ventas = ventas.aggregate(total=Sum("total"))["total"] or 0
    total_descuentos = ventas.aggregate(descuento=Sum("descuento"))["descuento"] or 0
    total_impuestos = ventas.aggregate(impuesto=Sum("impuesto"))["impuesto"] or 0
    cantidad_ventas = ventas.count()

    # === 4️⃣ Unidades vendidas ===
    detalles = DetalleVenta.objects.filter(venta__in=ventas)
    total_unidades_vendidas = detalles.aggregate(total_unidades=Sum("cantidad"))[
        "total_unidades"
    ] or 0

    # === 5️⃣ Desglose por método de pago ===
    metodos_pago = (
        ventas.values("metodo_pago")
        .annotate(total=Sum("total"))
        .order_by("metodo_pago")
    )

    # === 6️⃣ Productos más vendidos ===
    productos_top = (
        detalles.values(nombre=F("producto__nombre"))
        .annotate(total_vendido=Sum("cantidad"))
        .order_by("-total_vendido")[:10]
    )

    # === 7️⃣ Detalle de ventas con productos incluidos ===
    detalle_ventas = []

    for venta in ventas:
        productos_detalle = [ 
            {
                "venta_id"          : d.id,
                "venta_completa_id" : venta.id,
                "codigo_venta"      : venta.codigo,
                "producto_id"       : d.producto.id,
                "producto"          : d.producto.nombre,
                "cantidad"          : d.cantidad,
                "precio_unitario"   : float(d.precio_unitario),
                "subtotal_producto" : float(d.cantidad * d.precio_unitario),
            }
            for d in venta.detalles.all()
        ]

        detalle_ventas.append(
            {
                "id": venta.id,
                "codigo": venta.codigo,
                "cliente": venta.cliente.nombre if venta.cliente else "Cliente no registrado",
                "metodo_pago": venta.metodo_pago,
                "subtotal": float(venta.subtotal),
                "descuento": float(venta.descuento),
                "impuesto": float(venta.impuesto),
                "total": float(venta.total),
                "fecha": venta.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                "creado_por": venta.creado_por.username if venta.creado_por else "No asignado",
                "productos_comprados": productos_detalle,
            }
        )

    # === 8️⃣ Totales contables (para el pie de tabla) ===
    totales_tabla = {
        "subtotal_general": round(sum(v["subtotal"] for v in detalle_ventas), 2),
        "impuesto_general": round(sum(v["impuesto"] for v in detalle_ventas), 2),
        "total_general": round(sum(v["total"] for v in detalle_ventas), 2),
    }

    # === 9️⃣ Construcción final del reporte ===
    reporte = {
        "rango_consulta": rango_texto,
        "resumen_general": {
            "total_ventas": round(total_ventas, 2),
            "total_descuentos": round(total_descuentos, 2),
            "total_impuestos": round(total_impuestos, 2),
            "cantidad_ventas": cantidad_ventas,
            "total_unidades_vendidas": total_unidades_vendidas,
        },
        "por_metodo_pago": list(metodos_pago),
        "productos_top": list(productos_top),
        "detalle_ventas": detalle_ventas,
        "totales_tabla": totales_tabla,
    }

    return Response(reporte, status=status.HTTP_200_OK)