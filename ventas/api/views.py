from tarjetabancaria.models import TarjetaBancaria
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
from ventas.models import Venta, DetalleVenta, PagoVenta
from productos.models import Producto
from clientes.models import Cliente
from inventarioproducto.models import InventarioProducto
from proveedores.models import OrdenProveedorDetalle

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
            # Validar y obtener campos base
            # ===============================
            cliente_id    = data.get('cliente_id')
            tarjeta_id    = data.get('tarjeta_id')
            metodo_pago   = data.get('metodo_pago', 'Efectivo')
            recibido      = Decimal(data.get('recibido', '0'))
            cambio        = Decimal(data.get('cambio', '0'))
            subtotal      = Decimal(data.get('subtotal', '0'))
            descuento     = Decimal(data.get('descuento', '0'))
            impuesto      = Decimal(data.get('impuesto', '0'))
            total         = Decimal(data.get('total', '0'))
            items         = data.get('items', [])
            pagos         = data.get('pagos', [])

            # Decodificar pagos si llega como string JSON
            if isinstance(pagos, str):
                try:
                    pagos = json.loads(pagos)
                except json.JSONDecodeError:
                    return Response(
                        {"error": "Formato invalido para 'pagos'. Debe ser JSON valido."},
                        status=status.HTTP_400_BAD_REQUEST
                    )

            # Si no se envian pagos, mantener compatibilidad con el flujo anterior
            if not pagos:
                if not tarjeta_id:
                    return Response(
                        {"error": "El campo 'tarjeta_id' es obligatorio."},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                tarjeta = get_object_or_404(TarjetaBancaria, id=tarjeta_id)
            else:
                # Validar que pagos sea una lista con al menos un pago
                if not isinstance(pagos, list) or len(pagos) == 0:
                    return Response(
                        {"error": "'pagos' debe ser una lista con al menos un metodo de pago."},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                # Validar que la suma de los montos cubra al menos el total
                suma_pagos = sum(Decimal(str(p.get('monto', '0'))) for p in pagos)
                if suma_pagos < total - Decimal('0.99'):
                    return Response(
                        {"error": f"La suma de los pagos ({suma_pagos}) no cubre el total de la venta ({total})."},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                # Si el cliente pago de mas, registrar el cambio
                if suma_pagos > total:
                    cambio = suma_pagos - total

                # Determinar metodo_pago resumen
                metodos_usados = list(set(p.get('metodo_pago', '') for p in pagos))
                if len(metodos_usados) == 1:
                    metodo_pago = metodos_usados[0]
                else:
                    metodo_pago = 'Mixto'

                # tarjeta principal: la del primer pago que tenga tarjeta_id
                tarjeta_id = None
                tarjeta = None
                for p in pagos:
                    if p.get('tarjeta_id'):
                        tarjeta_id = p['tarjeta_id']
                        tarjeta = get_object_or_404(TarjetaBancaria, id=tarjeta_id)
                        break

            # Si items llega como string JSON, decodificarlo
            if isinstance(items, str):
                try:
                    items = json.loads(items)
                except json.JSONDecodeError:
                    return Response(
                        {"error": "Formato invalido para 'items'. Debe ser JSON valido."},
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
            # Crear venta principal
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
                creado_por  = request.user,
                tarjeta     = tarjeta
            )

            # ===============================
            # Crear registros de pagos
            # ===============================
            if pagos:
                for pago in pagos:
                    pago_tarjeta = None
                    if pago.get('tarjeta_id'):
                        pago_tarjeta = get_object_or_404(TarjetaBancaria, id=pago['tarjeta_id'])
                    PagoVenta.objects.create(
                        venta=venta,
                        metodo_pago=pago.get('metodo_pago', 'Efectivo'),
                        monto=Decimal(str(pago.get('monto', '0'))),
                        tarjeta=pago_tarjeta,
                    )
            else:
                # Compatibilidad: crear un solo PagoVenta con el metodo_pago original
                PagoVenta.objects.create(
                    venta=venta,
                    metodo_pago=metodo_pago,
                    monto=total,
                    tarjeta=tarjeta,
                )

            # ===============================
            # 🔹 Validar stock y crear detalles de venta
            # ===============================
            for item in items:
                producto_id     = item.get('id')
                cantidad        = int(item.get('quantity', 1))
                precio_unitario = Decimal(item.get('precio_final', '0'))
                is_combo        = item.get('isCombo', False)
                combo_id        = item.get('combo_id')
                combo_productos = item.get('combo_productos', [])

                # ======================================================
                # 🔹 CASO 1: Es un combo
                # ======================================================
                if is_combo and combo_id and combo_productos:
                    from combos.models import Combo
                    combo = get_object_or_404(Combo, id=combo_id)

                    # Validar stock para cada producto del combo
                    for cp in combo_productos:
                        producto_combo_id = cp.get('producto_id')
                        cantidad_combo = int(cp.get('cantidad', 1))
                        cantidad_total = cantidad_combo * cantidad  # cantidad del combo * cantidad de combos vendidos

                        producto = get_object_or_404(Producto, id=producto_combo_id)

                        # Calcular stock disponible
                        cantidad_recibida = (
                            OrdenProveedorDetalle.objects
                            .filter(
                                orden_proveedor__estado='recibida',
                                producto_id=producto_combo_id,
                                deleted_at__isnull=True
                            )
                            .aggregate(total=Sum('cantidad'))['total'] or 0
                        )

                        cantidad_vendida = (
                            DetalleVenta.objects
                            .filter(
                                producto_id=producto_combo_id,
                                deleted_at__isnull=True
                            )
                            .aggregate(total=Sum('cantidad'))['total'] or 0
                        )

                        stock_disponible = cantidad_recibida - cantidad_vendida

                        # Validar stock
                        if stock_disponible < cantidad_total:
                            raise IntegrityError(
                                f"Stock insuficiente para '{producto.nombre}' en combo '{combo.nombre}'. "
                                f"Disponible: {stock_disponible}, Solicitado: {cantidad_total}"
                            )

                        # Crear detalle de venta para cada producto del combo
                        DetalleVenta.objects.create(
                            venta           = venta,
                            producto        = producto,
                            cantidad        = cantidad_total,
                            precio_unitario = Decimal(cp.get('precio_combo', '0')),
                            combo           = combo,  # Referenciar el combo
                        )

                # ======================================================
                # 🔹 CASO 2: Es un producto individual
                # ======================================================
                else:
                    producto = get_object_or_404(Producto, id=producto_id)

                    # Calcular stock disponible
                    cantidad_recibida = (
                        OrdenProveedorDetalle.objects
                        .filter(
                            orden_proveedor__estado='recibida',
                            producto_id=producto_id,
                            deleted_at__isnull=True
                        )
                        .aggregate(total=Sum('cantidad'))['total'] or 0
                    )

                    cantidad_vendida = (
                        DetalleVenta.objects
                        .filter(
                            producto_id=producto_id,
                            deleted_at__isnull=True
                        )
                        .aggregate(total=Sum('cantidad'))['total'] or 0
                    )

                    stock_disponible = cantidad_recibida - cantidad_vendida

                    # Validar stock
                    if stock_disponible < cantidad:
                        raise IntegrityError(
                            f"Stock insuficiente para '{producto.nombre}'. "
                            f"Disponible: {stock_disponible}, Solicitado: {cantidad}"
                        )

                    # Crear detalle de venta
                    DetalleVenta.objects.create(
                        venta           = venta,
                        producto        = producto,
                        cantidad        = cantidad,
                        precio_unitario = precio_unitario,
                    )

            # ===============================
            # 🔹 Respuesta final
            # ===============================
            response_data = {
                "id"     : venta.id,
                "codigo" : venta.codigo,
                "cliente": venta.cliente.nombre if venta.cliente else "Venta rápida",
                "mensaje": "✅ Venta creada correctamente. Stock validado desde órdenes de proveedor."
            }

            return Response(response_data, status=status.HTTP_201_CREATED)

    except IntegrityError as e:
        return Response({"error": f"Error de integridad al crear la venta: {str(e)}"},
                        status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({"error": f"Error inesperado al crear la venta: {str(e)}"},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated, RolePermission(VENTA_MANAGER_ROLES)])
def get_siguiente_codigo_venta_v2(request):
    """
    Genera el siguiente código de venta consecutivo (versión robusta).
    Busca el número más alto en todos los códigos existentes.
    Formato: V-00001, V-00002, etc.
    """
    try:
        from django.db.models import Max
        from django.db.models.functions import Cast, Substr
        from django.db.models import IntegerField
        
        # Obtener todas las ventas y extraer el número más alto
        ventas = Venta.objects.all()
        
        if not ventas.exists():
            # Primera venta
            siguiente_numero = 1
        else:
            # Extraer números de todos los códigos y encontrar el máximo
            numeros = []
            for venta in ventas:
                if venta.codigo:
                    try:
                        # Extraer número del formato "V-00001"
                        numero = int(venta.codigo.split('-')[-1])
                        numeros.append(numero)
                    except (ValueError, IndexError):
                        continue
            
            if numeros:
                siguiente_numero = max(numeros) + 1
            else:
                siguiente_numero = 1
        
        # Formatear con ceros a la izquierda (5 dígitos)
        codigo_venta_formateado = f"V-{siguiente_numero:05d}"
        
        return Response({
            "siguiente_codigo": codigo_venta_formateado,
            "numero": siguiente_numero
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response(
            {"error": f"Error al generar código de venta: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    
# ======================================================
# Listar Ventas (GET)
# ======================================================
@api_view(['GET'])
@permission_classes([IsAuthenticated, RolePermission(VENTA_MANAGER_ROLES)])
def list_ventas(request):
    try:
        ventas = Venta.objects.select_related('cliente', 'creado_por').prefetch_related('detalles', 'pagos').all()

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
            pagos_list = [
                {
                    "metodo_pago": p.metodo_pago,
                    "monto": float(p.monto),
                    "tarjeta": p.tarjeta.nombre if p.tarjeta else None,
                }
                for p in v.pagos.all()
            ]
            data.append({
                "id": v.id,
                "codigo": v.codigo,
                "cliente": v.cliente.nombre if v.cliente else "Venta rápida",
                "metodo_pago": v.metodo_pago,
                "pagos": pagos_list,
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

    # === 2 Obtener ventas del rango ===
    ventas = (
        Venta.objects.filter(created_at__range=[inicio, fin])
        .select_related("cliente", "creado_por")
        .prefetch_related(
            Prefetch("detalles", queryset=DetalleVenta.objects.select_related("producto")),
            Prefetch("pagos"),
        )
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

    # === 5 Desglose por metodo de pago (desde PagoVenta) ===
    metodos_pago = (
        PagoVenta.objects.filter(venta__in=ventas, deleted_at__isnull=True)
        .values("metodo_pago")
        .annotate(total=Sum("monto"))
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

        pagos_detalle = [
            {
                "metodo_pago": p.metodo_pago,
                "monto": float(p.monto),
                "tarjeta": p.tarjeta.nombre if p.tarjeta else None,
            }
            for p in venta.pagos.all()
        ]

        detalle_ventas.append(
            {
                "id": venta.id,
                "codigo": venta.codigo,
                "cliente": venta.cliente.nombre if venta.cliente else "Cliente no registrado",
                "metodo_pago": venta.metodo_pago,
                "pagos": pagos_detalle,
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