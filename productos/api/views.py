from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import MultiPartParser, FormParser
from django.shortcuts import get_object_or_404
from django.db import IntegrityError
from django.db.models import Q
from django.db import DatabaseError
from decimal import Decimal

from user.api.permissions import RolePermission
from productos.models import Producto
from inventarioproducto.models import InventarioProducto
from inventarioproducto.api.views import get_total_unidades_producto_call
from categoria.models import Categoria
from subcategoria.models import SubCategoria
from proveedores.models import Proveedor

from core.utils import remove_thousand_separators

PRODUCT_MANAGER_ROLES = ['admin']


# ======================================================
# Crear Producto (POST)
# ======================================================
@api_view(['POST'])
@permission_classes([IsAuthenticated, RolePermission(PRODUCT_MANAGER_ROLES)])
@parser_classes([MultiPartParser, FormParser])  # Para recibir imágenes
def create_product(request):
    try:
        categoria_id        = request.data.get('categoria_id')
        subcategoria_id     = request.data.get('subcategoria_id')
        proveedor_id        = request.data.get('proveedor_id')
        nombre              = request.data.get('nombre')
        descripcion         = request.data.get('descripcion', '')
        precio_compra       = request.data.get('precio_compra', '0')
        porcentaje_ganancia = Decimal(request.data.get('porcentaje_ganancia', '0'))
        codigo_busqueda     = request.data.get('codigo_busqueda')
        imagen              = request.FILES.get('imagen')
        unidad_medida       = request.data.get('unidad_medida')
        genero              = request.data.get('genero')
        #cantidad_inicial    = int(request.data.get('cantidad', 0))

        if not all([categoria_id, nombre, precio_compra, porcentaje_ganancia, codigo_busqueda, unidad_medida, genero, proveedor_id]):
            return Response({"error": "Campos obligatorios faltantes."}, status=status.HTTP_400_BAD_REQUEST)

        precio_compra       = Decimal(remove_thousand_separators(precio_compra))
        print("===== precio_compra ======", precio_compra)

        categoria    = get_object_or_404(Categoria, id=categoria_id)
        subcategoria = get_object_or_404(SubCategoria, id=subcategoria_id) if subcategoria_id else None
        proveedor    = get_object_or_404(Proveedor, id=proveedor_id)

        if Producto.objects.filter(Q(nombre__iexact=nombre) | Q(codigo_busqueda__iexact=codigo_busqueda)).exists():
            return Response({"error": "Ya existe un producto con ese nombre o código."}, status=status.HTTP_400_BAD_REQUEST)

        producto = Producto(
            categoria=categoria,
            subcategoria=subcategoria,
            proveedor=proveedor,
            nombre=nombre,
            descripcion=descripcion,
            precio_compra=precio_compra,
            porcentaje_ganancia=porcentaje_ganancia,
            codigo_busqueda=codigo_busqueda,
            unidad_medida=unidad_medida,
            genero=genero,
            imagen=imagen,
            creado_por=request.user
        )

        producto.calcular_precio_final()
        producto.save()

        # Crear inventario inicial
        InventarioProducto.objects.create(
            producto=producto, 
            cantidad_unidades=0 
        )

        data = {
            "id": producto.id,
            "nombre": producto.nombre,
            "descripcion": producto.descripcion,
            "precio_compra": producto.precio_compra,
            "porcentaje_ganancia": producto.porcentaje_ganancia,
            "precio_final": producto.precio_final,
            "categoria": producto.categoria.nombre if producto.categoria else None,
            "subcategoria": producto.subcategoria.nombre if producto.subcategoria else None,
            "unidad_medida": producto.unidad_medida,
        }
        return Response(data, status=status.HTTP_201_CREATED)

    except IntegrityError:
        return Response({"error": "Error de integridad al crear el producto."}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({"error": f"Error inesperado al crear el producto: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ======================================================
# Listar Productos (GET)
# ======================================================
@api_view(['GET'])
@permission_classes([IsAuthenticated, RolePermission(PRODUCT_MANAGER_ROLES)])
def list_products(request):
    try:
        productos = Producto.objects.select_related('categoria', 'subcategoria', 'creado_por').all()

        search          = request.query_params.get('search')
        categoria_id    = request.query_params.get('categoria_id')
        subcategoria_id = request.query_params.get('subcategoria_id')
        proveedor_id    = request.query_params.get('proveedor_id')

        if search:
            productos = productos.filter(Q(nombre__icontains=search) | Q(codigo_busqueda__icontains=search) | Q(descripcion__icontains=search) | Q(categoria__nombre__icontains=search) | Q(subcategoria__nombre__icontains=search))
        if categoria_id:
            productos = productos.filter(categoria_id=categoria_id)
        if subcategoria_id:
            productos = productos.filter(subcategoria_id=subcategoria_id)
        if proveedor_id:
            productos = productos.filter(proveedor_id=proveedor_id)
            
        #Ordenar del más reciente al más antiguo
        productos = productos.order_by('-created_at')

        paginator = PageNumberPagination()
        paginator.page_size = 10
        page = paginator.paginate_queryset(productos, request)
        
        data = [{
            'id'                : p.id,
            'categoria'         : p.categoria.nombre if p.categoria else None,
            'subcategoria'      : p.subcategoria.nombre if p.subcategoria else None,
            'proveedor'         : p.proveedor.nombre_empresa if p.proveedor else None,
            'nombre'            : p.nombre,
            'descripcion'       : p.descripcion,
            'precio_compra'     : p.precio_compra,
            'porcentaje_ganancia': p.porcentaje_ganancia,
            'precio_final'      : p.precio_final,
            'codigo_busqueda'   : p.codigo_busqueda,
            'imagen_url'        : p.imagen.url if p.imagen else None,
            'unidad_medida'     : p.unidad_medida,
            'genero'            : p.genero,
            'creado_por'        : p.creado_por.username if p.creado_por else None,
            'created_at'        : p.created_at,
            'cantidad'          : get_total_unidades_producto_call(p.id)
        } for p in page]

        return paginator.get_paginated_response(data)

    except Exception as e:
        return Response({"error": f"Error al listar los productos: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ======================================================
# Obtener Producto por ID (GET /<id>/)
# ======================================================
@api_view(['GET'])
@permission_classes([IsAuthenticated, RolePermission(PRODUCT_MANAGER_ROLES)])
def get_product(request, pk):
    producto = get_object_or_404(Producto, pk=pk)
    data = {
        "id"                    : producto.id,
        "nombre"                : producto.nombre,
        "descripcion"           : producto.descripcion,
        "proveedor_id"          : producto.proveedor.id if producto.proveedor else None,
        "precio_compra"         : producto.precio_compra,
        "porcentaje_ganancia"   : producto.porcentaje_ganancia,
        "precio_final"          : producto.precio_final,
        "codigo_busqueda"       : producto.codigo_busqueda,
        "imagen_url"            : producto.imagen.url if producto.imagen else None,
        "categoria_id"          : producto.categoria.id if producto.categoria else None,
        "subcategoria_id"       : producto.subcategoria.id if producto.subcategoria else None,
        "unidad_medida"         : producto.unidad_medida,
        "genero"                : producto.genero,
        "inventario"            : producto.inventario.cantidad_unidades if hasattr(producto, 'inventario') else 0,
        "creado_por"            : producto.creado_por.username if producto.creado_por else None,
    }
    return Response(data, status=status.HTTP_200_OK)


# ======================================================
# Actualizar Producto (PUT /<id>/update/)
# ======================================================
@api_view(['PUT', 'PATCH'])
@permission_classes([IsAuthenticated, RolePermission(PRODUCT_MANAGER_ROLES)])
@parser_classes([MultiPartParser, FormParser])
def update_product(request, id):
    producto = get_object_or_404(Producto, id=id)
    try:
        categoria_id        = request.data.get('categoria_id')
        subcategoria_id     = request.data.get('subcategoria_id')
        proveedor_id        = request.data.get('proveedor_id')
        nombre              = request.data.get('nombre', producto.nombre)
        descripcion         = request.data.get('descripcion', producto.descripcion)
        precio_compra       = request.data.get('precio_compra', producto.precio_compra)
        porcentaje_ganancia = request.data.get('porcentaje_ganancia', producto.porcentaje_ganancia)
        codigo_busqueda     = request.data.get('codigo_busqueda', producto.codigo_busqueda)
        imagen              = request.FILES.get('imagen')
        unidad_medida       = request.data.get('unidad_medida', producto.unidad_medida)
        genero              = request.data.get('genero', producto.genero)

        if categoria_id:
            producto.categoria = get_object_or_404(Categoria, id=categoria_id)
        if subcategoria_id:
            producto.subcategoria = get_object_or_404(SubCategoria, id=subcategoria_id)
        if proveedor_id:
            producto.proveedor = get_object_or_404(Proveedor, id=proveedor_id)

        producto.nombre = nombre
        producto.descripcion = descripcion
        producto.precio_compra = precio_compra
        producto.porcentaje_ganancia = porcentaje_ganancia
        producto.codigo_busqueda = codigo_busqueda
        producto.unidad_medida = unidad_medida
        producto.genero = genero

        if imagen:
            producto.imagen = imagen

        producto.calcular_precio_final()
        producto.save()

        return Response({"message": "Producto actualizado correctamente."}, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({"error": f"Error al actualizar el producto: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ======================================================
# Eliminar Producto (DELETE /<id>/delete/)
# ======================================================
@api_view(['DELETE'])
@permission_classes([IsAuthenticated, RolePermission(PRODUCT_MANAGER_ROLES)])
def delete_product(request, pk):
    producto = get_object_or_404(Producto, pk=pk)
    try:
        producto.delete()
        return Response({"message": "Producto eliminado correctamente."}, status=status.HTTP_200_OK)
    except DatabaseError:
        return Response({"error": "Error de base de datos al eliminar el producto."}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({"error": f"Error al eliminar el producto: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
