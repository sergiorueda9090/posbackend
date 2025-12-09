# proveedor/views.py
from rest_framework.response import Response
from django.db.models import Sum, Count
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from django.shortcuts import get_object_or_404
from django.db import DatabaseError, transaction
from proveedores.models import Proveedor, OrdenProveedor, OrdenProveedorDetalle
from user.api.permissions import RolePermission 

from django.db.models import Q      # Necesario para el buscador
from datetime import datetime, time # Necesario para el manejo de fechas
from decimal import Decimal

# ReportLab para generación de PDF
from django.http import HttpResponse
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
import io
# ========================================

# Roles permitidos para gestionar proveedores (admin y contador/manager)
SUPPLIER_MANAGER_ROLES = ['admin', 'contador'] 

## Crear Proveedor (POST)
@api_view(['POST'])
@permission_classes([IsAuthenticated, RolePermission(SUPPLIER_MANAGER_ROLES)])
def create_supplier(request):
    try:
        nombre_empresa = request.data.get('nombre_empresa')
        ciudad           = request.data.get('ciudad')
        descripcion      = request.data.get('descripcion')
        # ruc              = request.data.get('ruc', 'Prueba')
        # email            = request.data.get('email', 'pruebas@mail.com')

        # Validación de campos obligatorios
        if not nombre_empresa:
            return Response(
                {"error": "El nombre del proveedor es obligatorio."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not ciudad:
            return Response(
                {"error": "La ciudad es obligatoria."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not descripcion:
            return Response(
                {"error": "La descripción es obligatoria."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validación de unicidad contra registros NO eliminados
        if Proveedor.objects.filter(nombre_empresa__iexact=nombre_empresa).exists():
            return Response(
                {"error": "Ya existe un proveedor con ese nombre."},
                status=status.HTTP_400_BAD_REQUEST
            )
        # if ruc and Proveedor.objects.filter(ruc=ruc).exists():
        #     return Response(
        #         {"error": "Ya existe un proveedor con ese RUC/Tax ID."},
        #         status=status.HTTP_400_BAD_REQUEST
        #     )
        # if email and Proveedor.objects.filter(email=email).exists():
        #     return Response(
        #         {"error": "Ya existe un proveedor con ese email."},
        #         status=status.HTTP_400_BAD_REQUEST
        #     )

        proveedor = Proveedor.objects.create(
            nombre_empresa = nombre_empresa,
            ciudad           = ciudad,
            descripcion      = descripcion,
            # contacto_principal  = request.data.get('contacto_principal'),
            # ruc                  = ruc,
            # email                = email,
            # telefono             = request.data.get('telefono'),
            # direccion            = request.data.get('direccion'),
            creado_por       = request.user
        )

        data = {
            "id"               : proveedor.id,
            "nombre_empresa"   : proveedor.nombre_empresa,
            "ciudad"           : proveedor.ciudad,
            "descripcion"      : proveedor.descripcion,
            "creado_por"       : proveedor.creado_por.username
        }
        return Response(data, status=status.HTTP_201_CREATED)

    except DatabaseError as e:
        return Response(
            {"error": f"Error de base de datos al crear el proveedor: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    except Exception as e:
        return Response(
            {"error": f"Error inesperado al crear el proveedor: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

## Listar Proveedores (GET)
@api_view(['GET'])
@permission_classes([IsAuthenticated, RolePermission(SUPPLIER_MANAGER_ROLES)])
def list_suppliers(request):
    try:
        # Consulta inicial (SoftDeleteManager ya filtra por no eliminados)
        proveedores = Proveedor.objects.select_related('creado_por').all()
        
        # 1. Aplicar FILTROS
        
        # --- Filtro de Buscador (Search) ---
        search_query = request.query_params.get('search', None)
        if search_query:
            # Filtra por varios campos del proveedor
            proveedores = proveedores.filter(
                Q(nombre_empresa__icontains=search_query) |
                Q(ciudad__icontains=search_query) |
                Q(descripcion__icontains=search_query)
                # Q(contacto_principal__icontains=search_query) |
                # Q(ruc__icontains=search_query) |
                # Q(email__icontains=search_query) |
                # Q(telefono__icontains=search_query) 
            )

        # --- Filtros de Fecha de Inicio y Fecha de Fin (Date Range) ---
        start_date_str = request.query_params.get('start_date', None)
        end_date_str = request.query_params.get('end_date', None)

        if start_date_str:
            try:
                # Convertir la cadena a objeto datetime.date
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                # Incluye todo el día de inicio (desde 00:00:00)
                start_datetime = datetime.combine(start_date, time.min)
                proveedores = proveedores.filter(created_at__gte=start_datetime)
            except ValueError:
                return Response(
                    {"error": "El formato de la fecha de inicio debe ser YYYY-MM-DD."},
                    status=status.HTTP_400_BAD_REQUEST
                )

        if end_date_str:
            try:
                # Convertir la cadena a objeto datetime.date
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
                # Incluye todo el día de fin (hasta 23:59:59.999999)
                end_datetime = datetime.combine(end_date, time.max)
                proveedores = proveedores.filter(created_at__lte=end_datetime)
            except ValueError:
                return Response(
                    {"error": "El formato de la fecha de fin debe ser YYYY-MM-DD."},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # 2. Aplicar la ordenación (después de los filtros)
        proveedores = proveedores.order_by('nombre_empresa')
        
        # 3. Aplicar paginación
        paginator = PageNumberPagination()
        paginator.page_size = 10 
        paginated_suppliers = paginator.paginate_queryset(proveedores, request)

        # 4. Serialización manual de los datos
        data = [{
            'id': p.id,
            'nombre_empresa'      : p.nombre_empresa,
            'ciudad'              : p.ciudad,
            'descripcion'         : p.descripcion,
            # 'contacto_principal'  : p.contacto_principal,
            # 'ruc'                 : p.ruc,
            # 'email'               : p.email,
            # 'telefono'            : p.telefono,
            'creado_por_username' : p.creado_por.username if p.creado_por else None,
            'created_at'          : p.created_at,
            'updated_at'          : p.updated_at,
        } for p in paginated_suppliers]

        return paginator.get_paginated_response(data)

    except Exception as e:
        return Response(
            {"error": f"Error al obtener la lista de proveedores: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

## Obtener Proveedor por ID (GET)
@api_view(['GET'])
@permission_classes([IsAuthenticated, RolePermission(SUPPLIER_MANAGER_ROLES)])
def get_supplier(request, pk):
    try:
        # Solo busca proveedores NO eliminados
        proveedor = get_object_or_404(Proveedor.objects.select_related('creado_por'), pk=pk)
        
        data = {
            "id"                : proveedor.id,
            "nombre_empresa"    : proveedor.nombre_empresa,
            "ciudad"            : proveedor.ciudad,
            "descripcion"       : proveedor.descripcion,
            # "contacto_principal": proveedor.contacto_principal,
            # "ruc"               : proveedor.ruc,
            # "email"             : proveedor.email,
            # "telefono"          : proveedor.telefono,
            # "direccion"         : proveedor.direccion,
            "creado_por"        : proveedor.creado_por.username if proveedor.creado_por else None,
            "created_at"        : proveedor.created_at,
            "updated_at"        : proveedor.updated_at,
            "deleted_at"        : proveedor.deleted_at,
        }
        return Response(data, status=status.HTTP_200_OK)

    except Exception as e:
        return Response(
            {"error": f"Error al obtener el proveedor: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

## Actualizar Proveedor (PUT)
@api_view(['PUT'])
@permission_classes([IsAuthenticated, RolePermission(SUPPLIER_MANAGER_ROLES)])
def update_supplier(request, pk):
    try:
        # Solo permite actualizar proveedores NO eliminados
        proveedor = get_object_or_404(Proveedor, pk=pk)
        
        # Obtener datos de la solicitud
        nombre_empresa = request.data.get('nombre_empresa', proveedor.nombre_empresa)
        ciudad           = request.data.get('ciudad', proveedor.ciudad)
        descripcion      = request.data.get('descripcion', proveedor.descripcion)
        # ruc              = request.data.get('ruc', proveedor.ruc)
        # email            = request.data.get('email', proveedor.email)

        # Validación de campos obligatorios
        if not nombre_empresa:
            return Response(
                {"error": "El nombre del proveedor es obligatorio."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not ciudad:
            return Response(
                {"error": "La ciudad es obligatoria."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not descripcion:
            return Response(
                {"error": "La descripción es obligatoria."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validación de unicidad para nombre_empresa
        if nombre_empresa != proveedor.nombre_empresa and Proveedor.objects.filter(nombre_empresa__iexact=nombre_empresa).exists():
             return Response(
                {"error": "Ya existe otro proveedor (activo) con ese nombre."},
                status=status.HTTP_400_BAD_REQUEST
            )
        # # Validación de unicidad para RUC
        # if ruc and ruc != proveedor.ruc and Proveedor.objects.filter(ruc=ruc).exists():
        #      return Response(
        #         {"error": "Ya existe otro proveedor (activo) con ese RUC/Tax ID."},
        #         status=status.HTTP_400_BAD_REQUEST
        #     )
        # # Validación de unicidad para Email
        # if email and email != proveedor.email and Proveedor.objects.filter(email=email).exists():
        #      return Response(
        #         {"error": "Ya existe otro proveedor (activo) con ese email."},
        #         status=status.HTTP_400_BAD_REQUEST
        #     )

        # Asignar campos
        proveedor.nombre_empresa = nombre_empresa
        proveedor.ciudad           = ciudad
        proveedor.descripcion      = descripcion
        # proveedor.contacto_principal   = request.data.get('contacto_principal', proveedor.contacto_principal)
        # proveedor.ruc                  = ruc
        # proveedor.email                = email
        # proveedor.telefono             = request.data.get('telefono', proveedor.telefono)
        # proveedor.direccion            = request.data.get('direccion', proveedor.direccion)

        proveedor.save()

        data = {
            "id"               : proveedor.id,
            "nombre_empresa" : proveedor.nombre_empresa,
            "ciudad"           : proveedor.ciudad,
            "descripcion"      : proveedor.descripcion,
            "updated_at"       : proveedor.updated_at,
        }
        return Response(data, status=status.HTTP_200_OK)

    except DatabaseError as e:
        return Response(
            {"error": f"Error de base de datos al actualizar el proveedor: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    except Exception as e:
        return Response(
            {"error": f"Error inesperado al actualizar el proveedor: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

## Eliminar Proveedor (DELETE) - Eliminación Lógica
@api_view(['DELETE'])
@permission_classes([IsAuthenticated, RolePermission(['admin'])]) # Solo admin puede eliminar
def delete_supplier(request, pk):
    try:
        # Solo busca proveedores NO eliminados para marcar como eliminado
        proveedor = get_object_or_404(Proveedor, pk=pk)
        
        # Ejecuta el soft delete (establece deleted_at)
        proveedor.delete()
        
        return Response(
            {"message": "Proveedor eliminado lógicamente exitosamente", "deleted_at": proveedor.deleted_at}, 
            status=status.HTTP_200_OK
        )
    except Exception as e:
        return Response(
            {"error": f"Error al ejecutar la eliminación lógica del proveedor: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    

# ========================================
# CRUD ORDEN PROVEEDOR (CABECERA)
# ========================================
@api_view(['GET'])
@permission_classes([IsAuthenticated, RolePermission(SUPPLIER_MANAGER_ROLES)])
def get_siguiente_numero_orden(request):
    """
    Genera el siguiente número de orden consecutivo.
    Formato: OP-00001, OP-00002, etc.
    """
    try:
        # Obtener la última orden creada
        ultima_orden = OrdenProveedor.objects.all().order_by('-id').first()
        
        if ultima_orden and ultima_orden.numero_orden:
            # Extraer el número de la última orden (ej: "OP-00005" -> 5)
            try:
                ultimo_numero = int(ultima_orden.numero_orden.split('-')[-1])
                siguiente_numero = ultimo_numero + 1
            except (ValueError, IndexError):
                # Si no se puede parsear, empezar desde 1
                siguiente_numero = 1
        else:
            # Primera orden
            siguiente_numero = 1
        
        # Formatear con ceros a la izquierda (5 dígitos)
        numero_orden_formateado = f"OP-{str(siguiente_numero).zfill(5)}"
        
        return Response({
            "siguiente_numero": numero_orden_formateado
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response(
            {"error": f"Error al generar número de orden: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


## Crear Orden de Proveedor (POST)
@api_view(['POST'])
@permission_classes([IsAuthenticated, RolePermission(SUPPLIER_MANAGER_ROLES)])
def create_orden_proveedor(request):
    """
    Crea una orden de proveedor con sus detalles.
    """
    try:
        proveedor_id  = request.data.get('proveedor_id')
        numero_orden  = request.data.get('numero_orden')
        estado        = request.data.get('estado', 'pendiente')
        notas         = request.data.get('notas', '')
        detalles_data = request.data.get('detalles', [])

        # Validaciones
        if not proveedor_id:
            return Response(
                {"error": "El ID del proveedor es obligatorio."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not numero_orden:
            return Response(
                {"error": "El número de orden es obligatorio."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not detalles_data or len(detalles_data) == 0:
            return Response(
                {"error": "Debe incluir al menos un producto en la orden."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Verificar que el proveedor existe
        proveedor = get_object_or_404(Proveedor, pk=proveedor_id)

        # Verificar unicidad del número de orden
        if OrdenProveedor.objects.filter(numero_orden=numero_orden).exists():
            return Response(
                {"error": "Ya existe una orden con ese número."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Transacción para crear orden y detalles
        with transaction.atomic():
            # Crear la orden
            orden = OrdenProveedor.objects.create(
                proveedor=proveedor,
                numero_orden=numero_orden,
                estado=estado,
                notas=notas,
                creado_por=request.user
            )

            # Crear los detalles y calcular total
            detalles_creados = []
            total_orden = Decimal('0.00')
            
            for detalle_data in detalles_data:
                producto_id = detalle_data.get('producto_id')
                nombre = detalle_data.get('nombre')
                precio_compra = detalle_data.get('precio_compra')
                cantidad = detalle_data.get('cantidad')
                notas_detalle = detalle_data.get('notas', '')

                # Validaciones de detalle
                if not producto_id or not nombre or not precio_compra or not cantidad:
                    return Response(
                        {"error": "Cada detalle debe incluir producto_id, nombre, precio_compra y cantidad."},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                detalle = OrdenProveedorDetalle.objects.create(
                    orden_proveedor=orden,
                    proveedor=proveedor,
                    producto_id=producto_id,
                    nombre=nombre,
                    precio_compra=Decimal(str(precio_compra)),
                    cantidad=int(cantidad),
                    notas=notas_detalle
                )
                
                # 🔥 Sumar al total
                total_orden += detalle.subtotal
                
                detalles_creados.append({
                    "id": detalle.id,
                    "producto_id": detalle.producto_id,
                    "nombre": detalle.nombre,
                    "precio_compra": str(detalle.precio_compra),
                    "cantidad": detalle.cantidad,
                    "subtotal": str(detalle.subtotal),
                    "notas": detalle.notas
                })

            # 🔥 Actualizar el total de la orden
            orden.total = total_orden
            orden.save(update_fields=['total'])

        data = {
            "id": orden.id,
            "proveedor": {
                "id": orden.proveedor.id,
                "nombre_empresa": orden.proveedor.nombre_empresa
            },
            "numero_orden": orden.numero_orden,
            "fecha_orden": orden.fecha_orden,
            "estado": orden.estado,
            "total": str(orden.total),
            "notas": orden.notas,
            "detalles": detalles_creados,
            "creado_por": orden.creado_por.username
        }
        return Response(data, status=status.HTTP_201_CREATED)

    except DatabaseError as e:
        return Response(
            {"error": f"Error de base de datos al crear la orden: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    except Exception as e:
        return Response(
            {"error": f"Error inesperado al crear la orden: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

## Listar Órdenes de Proveedor (GET)
@api_view(['GET'])
@permission_classes([IsAuthenticated, RolePermission(SUPPLIER_MANAGER_ROLES)])
def list_ordenes_proveedor(request):
    try:
        # Consulta inicial
        ordenes = OrdenProveedor.objects.select_related('proveedor', 'creado_por').all()
        
        # Filtro de búsqueda
        search_query = request.query_params.get('search', None)
        if search_query:
            ordenes = ordenes.filter(
                Q(numero_orden__icontains=search_query) |
                Q(proveedor__nombre_empresa__icontains=search_query) |
                Q(notas__icontains=search_query)
            )

        # Filtro por estado
        estado_filter = request.query_params.get('estado', None)
        if estado_filter:
            ordenes = ordenes.filter(estado=estado_filter)

        # Filtro por proveedor
        proveedor_id = request.query_params.get('proveedor_id', None)
        if proveedor_id:
            ordenes = ordenes.filter(proveedor_id=proveedor_id)

        # Filtros de fecha
        start_date_str = request.query_params.get('start_date', None)
        end_date_str = request.query_params.get('end_date', None)

        if start_date_str:
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                start_datetime = datetime.combine(start_date, time.min)
                ordenes = ordenes.filter(fecha_orden__gte=start_datetime)
            except ValueError:
                return Response(
                    {"error": "El formato de la fecha de inicio debe ser YYYY-MM-DD."},
                    status=status.HTTP_400_BAD_REQUEST
                )

        if end_date_str:
            try:
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
                end_datetime = datetime.combine(end_date, time.max)
                ordenes = ordenes.filter(fecha_orden__lte=end_datetime)
            except ValueError:
                return Response(
                    {"error": "El formato de la fecha de fin debe ser YYYY-MM-DD."},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Ordenación
        ordenes = ordenes.order_by('-fecha_orden')
        
        # Paginación
        paginator = PageNumberPagination()
        paginator.page_size = 10
        paginated_ordenes = paginator.paginate_queryset(ordenes, request)

        # Serialización
        data = [{
            'id': o.id,
            'proveedor': {
                'id': o.proveedor.id,
                'nombre_empresa': o.proveedor.nombre_empresa
            },
            'numero_orden': o.numero_orden,
            'fecha_orden': o.fecha_orden,
            'estado': o.estado,
            'total': str(o.total),
            'notas': o.notas,
            'creado_por_username': o.creado_por.username if o.creado_por else None,
            'created_at': o.created_at,
            'updated_at': o.updated_at,
        } for o in paginated_ordenes]

        return paginator.get_paginated_response(data)

    except Exception as e:
        return Response(
            {"error": f"Error al obtener la lista de órdenes: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
@permission_classes([IsAuthenticated, RolePermission(SUPPLIER_MANAGER_ROLES)])
def list_proveedores_con_ordenes(request):
    """
    Lista proveedores con sus órdenes agrupadas.
    Retorna estructura: proveedor -> ordenes[] -> detalles[]
    """
    try:
        # Obtener todos los proveedores con órdenes
        proveedores = Proveedor.objects.prefetch_related(
            'ordenes__detalles'
        ).annotate(
            total_ordenes=Sum('ordenes__total'),
            cantidad_ordenes=Count('ordenes')
        ).filter(ordenes__isnull=False).distinct()
        
        # Filtro de búsqueda
        search_query = request.query_params.get('search', None)
        if search_query:
            proveedores = proveedores.filter(
                Q(nombre_empresa__icontains=search_query) |
                Q(ciudad__icontains=search_query) |
                Q(descripcion__icontains=search_query)
            )

        # Filtro por ciudad
        ciudad_filter = request.query_params.get('ciudad', None)
        if ciudad_filter:
            proveedores = proveedores.filter(ciudad__icontains=ciudad_filter)

        # Filtros de fecha para las órdenes
        start_date_str = request.query_params.get('start_date', None)
        end_date_str = request.query_params.get('end_date', None)

        # Ordenación
        proveedores = proveedores.order_by('nombre_empresa')
        
        # Paginación
        paginator = PageNumberPagination()
        paginator.page_size = 10
        paginated_proveedores = paginator.paginate_queryset(proveedores, request)

        # Serialización
        data = []
        for proveedor in paginated_proveedores:
            # Obtener órdenes del proveedor
            ordenes_query = proveedor.ordenes.all()
            
            # Aplicar filtros de fecha a las órdenes si existen
            if start_date_str:
                try:
                    start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                    start_datetime = datetime.combine(start_date, time.min)
                    ordenes_query = ordenes_query.filter(fecha_orden__gte=start_datetime)
                except ValueError:
                    pass
            
            if end_date_str:
                try:
                    end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
                    end_datetime = datetime.combine(end_date, time.max)
                    ordenes_query = ordenes_query.filter(fecha_orden__lte=end_datetime)
                except ValueError:
                    pass
            
            # Serializar órdenes
            ordenes_pedido = []
            total_proveedor = 0
            
            for orden in ordenes_query.order_by('-fecha_orden'):
                # Obtener detalles de la orden
                detalles = orden.detalles.all()
                
                # 🔥 Serializar cada producto de la orden
                productos_detalle = []
                cantidad_total = 0
                
                for detalle in detalles:
                    productos_detalle.append({
                        "id": detalle.id,
                        "producto_id": detalle.producto_id,
                        "nombre": detalle.nombre,
                        "precio_compra": float(detalle.precio_compra),
                        "cantidad": detalle.cantidad,
                        "subtotal": float(detalle.subtotal),
                        "notas": detalle.notas or ""
                    })
                    cantidad_total += detalle.cantidad
                
                # Construir resumen de productos para vista rápida
                productos_resumen = ", ".join([d.nombre for d in detalles[:2]])  # Primeros 2 productos
                if detalles.count() > 2:
                    productos_resumen += f" (+{detalles.count() - 2} más)"
                
                # Mapear estado al formato del frontend
                estado_map = {
                    'pendiente': 'Pendiente',
                    'confirmada': 'Confirmada',
                    'en_transito': 'En tránsito',
                    'recibida': 'Entregado',
                    'cancelada': 'Cancelada',
                }
                
                ordenes_pedido.append({
                    "id": orden.id,
                    "numero_orden": orden.numero_orden,
                    "fecha": orden.fecha_orden.isoformat(),
                    "estado": estado_map.get(orden.estado, orden.estado),
                    "total": float(orden.total),
                    "notas": orden.notas or "",
                    "cantidad_productos": detalles.count(),
                    "cantidad_total": cantidad_total,
                    "productos_resumen": productos_resumen,
                    "productos": productos_detalle  # 🔥 Lista completa de productos
                })
                
                total_proveedor += float(orden.total)
            
            data.append({
                "id": proveedor.id,
                "nombre_proveedor": proveedor.nombre_empresa,
                "ciudad": proveedor.ciudad,
                "descripcion": proveedor.descripcion or "",
                "total": total_proveedor,
                "cantidad_ordenes": len(ordenes_pedido),
                "ordenesPedido": ordenes_pedido
            })

        return paginator.get_paginated_response(data)

    except Exception as e:
        return Response(
            {"error": f"Error al obtener la lista de proveedores con órdenes: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

## Obtener Orden de Proveedor por ID (GET)
@api_view(['GET'])
@permission_classes([IsAuthenticated, RolePermission(SUPPLIER_MANAGER_ROLES)])
def get_orden_proveedor(request, pk):
    try:
        orden = get_object_or_404(
            OrdenProveedor.objects.select_related('proveedor', 'creado_por')
                                  .prefetch_related('detalles'),
            pk=pk
        )
        
        # Serializar detalles
        detalles_data = [{
            "id": d.id,
            "producto_id": d.producto_id,
            "nombre": d.nombre,
            "precio_compra": str(d.precio_compra),
            "cantidad": d.cantidad,
            "subtotal": str(d.subtotal),
            "notas": d.notas
        } for d in orden.detalles.all()]

        data = {
            "id": orden.id,
            "proveedor": {
                "id": orden.proveedor.id,
                "nombre_empresa": orden.proveedor.nombre_empresa
            },
            "numero_orden": orden.numero_orden,
            "fecha_orden": orden.fecha_orden,
            "estado": orden.estado,
            "total": str(orden.total),
            "notas": orden.notas,
            "detalles": detalles_data,
            "creado_por": orden.creado_por.username if orden.creado_por else None,
            "created_at": orden.created_at,
            "updated_at": orden.updated_at,
        }
        return Response(data, status=status.HTTP_200_OK)

    except Exception as e:
        return Response(
            {"error": f"Error al obtener la orden: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


## Actualizar Orden de Proveedor (PUT)
@api_view(['PUT'])
@permission_classes([IsAuthenticated, RolePermission(SUPPLIER_MANAGER_ROLES)])
def update_orden_proveedor(request, pk):
    """
    Actualiza la orden y sus detalles.
    Los detalles se reemplazan completamente con los nuevos enviados.
    """
    try:
        orden = get_object_or_404(OrdenProveedor, pk=pk)
        
        numero_orden = request.data.get('numero_orden', orden.numero_orden)
        estado = request.data.get('estado', orden.estado)
        notas = request.data.get('notas', orden.notas)
        detalles_data = request.data.get('detalles', None)

        # Validación de número de orden único
        if numero_orden != orden.numero_orden and OrdenProveedor.objects.filter(numero_orden=numero_orden).exists():
            return Response(
                {"error": "Ya existe otra orden con ese número."},
                status=status.HTTP_400_BAD_REQUEST
            )

        with transaction.atomic():
            # Actualizar la orden
            orden.numero_orden = numero_orden
            orden.estado = estado
            orden.notas = notas
            orden.save()

            # Si se enviaron detalles, reemplazarlos
            if detalles_data is not None:
                # Eliminar detalles anteriores
                orden.detalles.all().delete()

                # Crear nuevos detalles
                for detalle_data in detalles_data:
                    producto_id = detalle_data.get('producto_id')
                    nombre = detalle_data.get('nombre')
                    precio_compra = detalle_data.get('precio_compra')
                    cantidad = detalle_data.get('cantidad')
                    notas_detalle = detalle_data.get('notas', '')

                    if not producto_id or not nombre or not precio_compra or not cantidad:
                        return Response(
                            {"error": "Cada detalle debe incluir producto_id, nombre, precio_compra y cantidad."},
                            status=status.HTTP_400_BAD_REQUEST
                        )

                    OrdenProveedorDetalle.objects.create(
                        orden_proveedor=orden,
                        proveedor=orden.proveedor,
                        producto_id=producto_id,
                        nombre=nombre,
                        precio_compra=Decimal(str(precio_compra)),
                        cantidad=int(cantidad),
                        notas=notas_detalle
                    )

                # Recalcular el total
                orden.calcular_total()

        # Recargar la orden con detalles
        orden.refresh_from_db()
        detalles_actualizados = [{
            "id": d.id,
            "producto_id": d.producto_id,
            "nombre": d.nombre,
            "precio_compra": str(d.precio_compra),
            "cantidad": d.cantidad,
            "subtotal": str(d.subtotal),
            "notas": d.notas
        } for d in orden.detalles.all()]

        data = {
            "id": orden.id,
            "numero_orden": orden.numero_orden,
            "estado": orden.estado,
            "total": str(orden.total),
            "notas": orden.notas,
            "detalles": detalles_actualizados,
            "updated_at": orden.updated_at,
        }
        return Response(data, status=status.HTTP_200_OK)

    except DatabaseError as e:
        return Response(
            {"error": f"Error de base de datos al actualizar la orden: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    except Exception as e:
        return Response(
            {"error": f"Error inesperado al actualizar la orden: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


## Eliminar Orden de Proveedor (DELETE)
@api_view(['DELETE'])
@permission_classes([IsAuthenticated, RolePermission(['admin'])])
def delete_orden_proveedor(request, pk):
    try:
        orden = get_object_or_404(OrdenProveedor, pk=pk)
        
        # Soft delete
        orden.delete()
        
        return Response(
            {"message": "Orden eliminada lógicamente exitosamente", "deleted_at": orden.deleted_at}, 
            status=status.HTTP_200_OK
        )
    except Exception as e:
        return Response(
            {"error": f"Error al ejecutar la eliminación lógica de la orden: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# ========================================
# CRUD ORDEN PROVEEDOR DETALLE
# ========================================

## Crear Detalle Individual (POST)
@api_view(['POST'])
@permission_classes([IsAuthenticated, RolePermission(SUPPLIER_MANAGER_ROLES)])
def create_orden_detalle(request):
    """
    Agrega un nuevo detalle a una orden existente.
    Espera:
    {
        "orden_proveedor_id": 1,
        "producto_id": 123,
        "nombre": "Laptop Dell",
        "precio_compra": 850.00,
        "cantidad": 5,
        "notas": "Urgente"
    }
    """
    try:
        orden_proveedor_id = request.data.get('orden_proveedor_id')
        producto_id = request.data.get('producto_id')
        nombre = request.data.get('nombre')
        precio_compra = request.data.get('precio_compra')
        cantidad = request.data.get('cantidad')
        notas = request.data.get('notas', '')

        # Validaciones
        if not orden_proveedor_id or not producto_id or not nombre or not precio_compra or not cantidad:
            return Response(
                {"error": "Todos los campos son obligatorios: orden_proveedor_id, producto_id, nombre, precio_compra, cantidad."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Verificar que la orden existe
        orden = get_object_or_404(OrdenProveedor, pk=orden_proveedor_id)

        # Verificar que no exista el mismo producto en la orden
        if OrdenProveedorDetalle.objects.filter(orden_proveedor=orden, producto_id=producto_id).exists():
            return Response(
                {"error": "Este producto ya existe en la orden."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Crear el detalle
        detalle = OrdenProveedorDetalle.objects.create(
            orden_proveedor=orden,
            proveedor=orden.proveedor,
            producto_id=producto_id,
            nombre=nombre,
            precio_compra=Decimal(str(precio_compra)),
            cantidad=int(cantidad),
            notas=notas
        )

        data = {
            "id": detalle.id,
            "orden_proveedor_id": detalle.orden_proveedor.id,
            "producto_id": detalle.producto_id,
            "nombre": detalle.nombre,
            "precio_compra": str(detalle.precio_compra),
            "cantidad": detalle.cantidad,
            "subtotal": str(detalle.subtotal),
            "notas": detalle.notas
        }
        return Response(data, status=status.HTTP_201_CREATED)

    except Exception as e:
        return Response(
            {"error": f"Error al crear el detalle: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


## Listar Detalles de una Orden (GET)
@api_view(['GET'])
@permission_classes([IsAuthenticated, RolePermission(SUPPLIER_MANAGER_ROLES)])
def list_orden_detalles(request, orden_id):
    try:
        orden = get_object_or_404(OrdenProveedor, pk=orden_id)
        detalles = orden.detalles.all()

        data = [{
            "id": d.id,
            "producto_id": d.producto_id,
            "nombre": d.nombre,
            "precio_compra": str(d.precio_compra),
            "cantidad": d.cantidad,
            "subtotal": str(d.subtotal),
            "notas": d.notas
        } for d in detalles]

        return Response(data, status=status.HTTP_200_OK)

    except Exception as e:
        return Response(
            {"error": f"Error al obtener los detalles: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


## Obtener Detalle por ID (GET)
@api_view(['GET'])
@permission_classes([IsAuthenticated, RolePermission(SUPPLIER_MANAGER_ROLES)])
def get_orden_detalle(request, pk):
    try:
        detalle = get_object_or_404(OrdenProveedorDetalle, pk=pk)
        
        data = {
            "id": detalle.id,
            "orden_proveedor_id": detalle.orden_proveedor.id,
            "proveedor_id": detalle.proveedor.id,
            "producto_id": detalle.producto_id,
            "nombre": detalle.nombre,
            "precio_compra": str(detalle.precio_compra),
            "cantidad": detalle.cantidad,
            "subtotal": str(detalle.subtotal),
            "notas": detalle.notas,
            "created_at": detalle.created_at,
            "updated_at": detalle.updated_at,
        }
        return Response(data, status=status.HTTP_200_OK)

    except Exception as e:
        return Response(
            {"error": f"Error al obtener el detalle: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


## Actualizar Detalle (PUT)
@api_view(['PUT'])
@permission_classes([IsAuthenticated, RolePermission(SUPPLIER_MANAGER_ROLES)])
def update_orden_detalle(request, pk):
    try:
        detalle = get_object_or_404(OrdenProveedorDetalle, pk=pk)
        
        nombre = request.data.get('nombre', detalle.nombre)
        precio_compra = request.data.get('precio_compra', detalle.precio_compra)
        cantidad = request.data.get('cantidad', detalle.cantidad)
        notas = request.data.get('notas', detalle.notas)

        # Actualizar campos
        detalle.nombre = nombre
        detalle.precio_compra = Decimal(str(precio_compra))
        detalle.cantidad = int(cantidad)
        detalle.notas = notas
        detalle.save()  # El save() ya recalcula el subtotal y el total de la orden

        data = {
            "id": detalle.id,
            "nombre": detalle.nombre,
            "precio_compra": str(detalle.precio_compra),
            "cantidad": detalle.cantidad,
            "subtotal": str(detalle.subtotal),
            "notas": detalle.notas,
            "updated_at": detalle.updated_at,
        }
        return Response(data, status=status.HTTP_200_OK)

    except Exception as e:
        return Response(
            {"error": f"Error al actualizar el detalle: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


## Eliminar Detalle (DELETE)
@api_view(['DELETE'])
@permission_classes([IsAuthenticated, RolePermission(['admin'])])
def delete_orden_detalle(request, pk):
    try:
        detalle = get_object_or_404(OrdenProveedorDetalle, pk=pk)
        
        # Soft delete (el método delete() ya actualiza el total de la orden)
        detalle.delete()
        
        return Response(
            {"message": "Detalle eliminado lógicamente exitosamente", "deleted_at": detalle.deleted_at}, 
            status=status.HTTP_200_OK
        )
    except Exception as e:
        return Response(
            {"error": f"Error al ejecutar la eliminación lógica del detalle: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    
@api_view(['GET'])
@permission_classes([IsAuthenticated, RolePermission(SUPPLIER_MANAGER_ROLES)])
def descargar_orden_pdf(request, orden_id):
    """
    Genera y descarga un PDF detallado de la orden de proveedor.
    """
    try:
        # Obtener la orden
        orden = get_object_or_404(
            OrdenProveedor.objects.select_related('proveedor', 'creado_por')
                                  .prefetch_related('detalles'),
            pk=orden_id
        )
        
        # Crear el buffer para el PDF
        buffer = io.BytesIO()
        
        # Crear el documento PDF
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=40,
            leftMargin=40,
            topMargin=60,
            bottomMargin=40,
        )
        
        # Contenedor para los elementos del PDF
        elementos = []
        
        # Estilos
        styles = getSampleStyleSheet()
        
        # Estilo para el título
        titulo_style = ParagraphStyle(
            'TituloPersonalizado',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#F7C548'),
            spaceAfter=30,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        )
        
        # Estilo para subtítulos
        subtitulo_style = ParagraphStyle(
            'SubtituloPersonalizado',
            parent=styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#333333'),
            spaceAfter=12,
            fontName='Helvetica-Bold'
        )
        
        # Estilo normal
        normal_style = ParagraphStyle(
            'NormalPersonalizado',
            parent=styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#333333'),
        )
        
        # ===== ENCABEZADO =====
        titulo = Paragraph("ORDEN DE COMPRA", titulo_style)
        elementos.append(titulo)
        elementos.append(Spacer(1, 20))
        
        # ===== INFORMACIÓN DE LA ORDEN =====
        estado_map = {
            'pendiente': 'PENDIENTE',
            'confirmada': 'CONFIRMADA',
            'en_transito': 'EN TRÁNSITO',
            'recibida': 'ENTREGADO',
            'cancelada': 'CANCELADA',
        }
        
        info_orden = [
            ['Número de Orden:', orden.numero_orden, 'Estado:', estado_map.get(orden.estado, orden.estado)],
            ['Fecha:', orden.fecha_orden.strftime('%d/%m/%Y %H:%M'), 'Creado por:', orden.creado_por.username if orden.creado_por else 'N/A'],
        ]
        
        tabla_info = Table(info_orden, colWidths=[2*inch, 2*inch, 1.5*inch, 1.5*inch])
        tabla_info.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#F7C548')),
            ('BACKGROUND', (2, 0), (2, -1), colors.HexColor('#F7C548')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        elementos.append(tabla_info)
        elementos.append(Spacer(1, 20))
        
        # ===== INFORMACIÓN DEL PROVEEDOR =====
        subtitulo_proveedor = Paragraph("INFORMACIÓN DEL PROVEEDOR", subtitulo_style)
        elementos.append(subtitulo_proveedor)
        
        info_proveedor = [
            ['Proveedor:', orden.proveedor.nombre_empresa],
            ['Ciudad:', orden.proveedor.ciudad or 'N/A'],
            ['Descripción:', orden.proveedor.descripcion or 'N/A'],
        ]
        
        if orden.proveedor.email:
            info_proveedor.append(['Email:', orden.proveedor.email])
        if orden.proveedor.telefono:
            info_proveedor.append(['Teléfono:', orden.proveedor.telefono])
        
        tabla_proveedor = Table(info_proveedor, colWidths=[2*inch, 5*inch])
        tabla_proveedor.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#FFF7E6')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        elementos.append(tabla_proveedor)
        elementos.append(Spacer(1, 20))
        
        # ===== DETALLE DE PRODUCTOS =====
        subtitulo_productos = Paragraph("DETALLE DE PRODUCTOS", subtitulo_style)
        elementos.append(subtitulo_productos)
        
        # Encabezados de la tabla de productos
        datos_productos = [
            ['#', 'Producto', 'Precio Unit.', 'Cantidad', 'Subtotal']
        ]
        
        # Agregar cada producto
        detalles = orden.detalles.all()
        for idx, detalle in enumerate(detalles, 1):
            datos_productos.append([
                str(idx),
                detalle.nombre,
                f"${detalle.precio_compra:,.2f}",
                str(detalle.cantidad),
                f"${detalle.subtotal:,.2f}"
            ])
        
        # Fila de total
        datos_productos.append([
            '',
            '',
            '',
            'TOTAL:',
            f"${orden.total:,.2f}"
        ])
        
        tabla_productos = Table(datos_productos, colWidths=[0.5*inch, 3*inch, 1.3*inch, 1*inch, 1.5*inch])
        tabla_productos.setStyle(TableStyle([
            # Encabezado
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F7C548')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            ('TOPPADDING', (0, 0), (-1, 0), 10),
            
            # Cuerpo
            ('TEXTCOLOR', (0, 1), (-1, -2), colors.black),
            ('ALIGN', (0, 1), (0, -1), 'CENTER'),  # Columna #
            ('ALIGN', (2, 1), (2, -1), 'RIGHT'),   # Precio
            ('ALIGN', (3, 1), (3, -1), 'CENTER'),  # Cantidad
            ('ALIGN', (4, 1), (4, -1), 'RIGHT'),   # Subtotal
            ('FONTNAME', (0, 1), (-1, -2), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -2), 9),
            ('BOTTOMPADDING', (0, 1), (-1, -2), 6),
            ('TOPPADDING', (0, 1), (-1, -2), 6),
            
            # Fila de total
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#FFF7E6')),
            ('TEXTCOLOR', (0, -1), (-1, -1), colors.HexColor('#155724')),
            ('ALIGN', (3, -1), (3, -1), 'RIGHT'),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, -1), (-1, -1), 12),
            ('BOTTOMPADDING', (0, -1), (-1, -1), 10),
            ('TOPPADDING', (0, -1), (-1, -1), 10),
            
            # Bordes
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
            ('LINEBELOW', (0, 0), (-1, 0), 2, colors.HexColor('#F7C548')),
        ]))
        elementos.append(tabla_productos)
        elementos.append(Spacer(1, 20))
        
        # ===== NOTAS =====
        if orden.notas:
            subtitulo_notas = Paragraph("NOTAS / OBSERVACIONES", subtitulo_style)
            elementos.append(subtitulo_notas)
            
            notas_texto = Paragraph(orden.notas, normal_style)
            elementos.append(notas_texto)
            elementos.append(Spacer(1, 20))
        
        # ===== PIE DE PÁGINA =====
        elementos.append(Spacer(1, 30))
        
        pie_texto = f"""
        <para align=center>
        <font size=8 color=#666666>
        Documento generado el {datetime.now().strftime('%d/%m/%Y a las %H:%M')}<br/>
        Sistema de Gestión de Órdenes de Compra
        </font>
        </para>
        """
        pie = Paragraph(pie_texto, styles['Normal'])
        elementos.append(pie)
        
        # Construir el PDF
        doc.build(elementos)
        
        # Preparar la respuesta
        buffer.seek(0)
        response = HttpResponse(buffer.read(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="Orden_{orden.numero_orden}.pdf"'
        
        return response
        
    except Exception as e:
        return Response(
            {"error": f"Error al generar el PDF: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )