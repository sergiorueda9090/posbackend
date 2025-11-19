from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from django.shortcuts import get_object_or_404
from django.db import DatabaseError, IntegrityError
from django.db.models import Q
from datetime import datetime, time

from user.api.permissions import RolePermission
from categoria.models import Categoria
from subcategoria.models import SubCategoria

# Roles permitidos
SUBCATEGORY_MANAGER_ROLES = ['admin']


## Crear Subcategoría (POST)
@api_view(['POST'])
@permission_classes([IsAuthenticated, RolePermission(SUBCATEGORY_MANAGER_ROLES)])
def create_subcategory(request):
    try:
        categoria_id = request.data.get('categoria_id')
        nombre = request.data.get('nombre')
        descripcion = request.data.get('descripcion', '')

        if not categoria_id or not nombre:
            return Response(
                {"error": "El ID de la categoría y el nombre son obligatorios."},
                status=status.HTTP_400_BAD_REQUEST
            )

        categoria = get_object_or_404(Categoria, id=categoria_id)

        # Validar duplicado
        if SubCategoria.all_objects.filter(nombre__iexact=nombre, categoria=categoria).exists():
            return Response(
                {"error": "Ya existe una subcategoría con ese nombre en esta categoría."},
                status=status.HTTP_400_BAD_REQUEST
            )

        subcategoria = SubCategoria.objects.create(
            categoria=categoria,
            nombre=nombre,
            descripcion=descripcion,
            creado_por=request.user
        )

        data = {
            "id": subcategoria.id,
            "nombre": subcategoria.nombre,
            "categoria": subcategoria.categoria.nombre,
            "creado_por": subcategoria.creado_por.username if subcategoria.creado_por else None
        }

        return Response(data, status=status.HTTP_201_CREATED)

    except IntegrityError:
        return Response(
            {"error": "Error de integridad, puede que el nombre ya exista."},
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        return Response(
            {"error": f"Error inesperado al crear la subcategoría: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


## Listar Subcategorías (GET)
@api_view(['GET'])
@permission_classes([IsAuthenticated, RolePermission(SUBCATEGORY_MANAGER_ROLES)])
def list_subcategories(request):
    try:
        subcategorias = SubCategoria.objects.select_related('categoria', 'creado_por').all()

        # Filtros
        search = request.query_params.get('search', None)
        categoria_id = request.query_params.get('categoria_id', None)
        print(" === search === ", search)
        if search:
            subcategorias = subcategorias.filter(
                Q(nombre__icontains=search) | Q(descripcion__icontains=search)
            )

        if categoria_id:
            subcategorias = subcategorias.filter(categoria_id=categoria_id)

        # Fechas
        start_date_str = request.query_params.get('start_date')
        end_date_str = request.query_params.get('end_date')

        if start_date_str:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            start_datetime = datetime.combine(start_date, time.min)
            subcategorias = subcategorias.filter(created_at__gte=start_datetime)

        if end_date_str:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            end_datetime = datetime.combine(end_date, time.max)
            subcategorias = subcategorias.filter(created_at__lte=end_datetime)

        subcategorias = subcategorias.order_by('nombre')

        # Paginación
        paginator = PageNumberPagination()
        paginator.page_size = 10
        page = paginator.paginate_queryset(subcategorias, request)

        data = [{
            'id': s.id,
            'nombre': s.nombre,
            'descripcion': s.descripcion,
            'categoria': s.categoria.nombre if s.categoria else None,
            'creado_por': s.creado_por.username if s.creado_por else None,
            'created_at': s.created_at,
            'updated_at': s.updated_at,
        } for s in page]

        return paginator.get_paginated_response(data)

    except Exception as e:
        return Response(
            {"error": f"Error al listar las subcategorías: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


## Obtener Subcategoría por ID
@api_view(['GET'])
@permission_classes([IsAuthenticated, RolePermission(SUBCATEGORY_MANAGER_ROLES)])
def get_subcategory(request, pk):
    try:
        subcategoria = get_object_or_404(SubCategoria.objects.select_related('categoria', 'creado_por'), pk=pk)
        data = {
            "id": subcategoria.id,
            "nombre": subcategoria.nombre,
            "descripcion": subcategoria.descripcion,
            "categoria": subcategoria.categoria.nombre if subcategoria.categoria else None,
            "categoria_id": subcategoria.categoria.id if subcategoria.categoria else None,
            "creado_por": subcategoria.creado_por.username if subcategoria.creado_por else None,
            "created_at": subcategoria.created_at,
            "updated_at": subcategoria.updated_at,
        }
        return Response(data, status=status.HTTP_200_OK)

    except Exception as e:
        return Response(
            {"error": f"Error al obtener la subcategoría: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


## Actualizar Subcategoría (PUT)
@api_view(['PUT'])
@permission_classes([IsAuthenticated, RolePermission(SUBCATEGORY_MANAGER_ROLES)])
def update_subcategory(request, pk):
    try:
        subcategoria = get_object_or_404(SubCategoria, pk=pk)

        nombre = request.data.get('nombre', subcategoria.nombre)
        descripcion = request.data.get('descripcion', subcategoria.descripcion)
        categoria_id = request.data.get('categoria_id', None)

        # 🔹 Validar nombre duplicado (si cambió)
        if (
            nombre.lower() != subcategoria.nombre.lower()
            and SubCategoria.objects.filter(nombre__iexact=nombre).exclude(pk=pk).exists()
        ):
            return Response(
                {"error": "Ya existe otra subcategoría con ese nombre."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 🔹 Actualizar campos
        subcategoria.nombre = nombre
        subcategoria.descripcion = descripcion

        if categoria_id:
            categoria = get_object_or_404(Categoria, id=categoria_id)
            subcategoria.categoria = categoria

        # 🔹 Guardar cambios
        subcategoria.save()

        # 🔹 Respuesta con todos los datos relevantes
        data = {
            "id": subcategoria.id,
            "nombre": subcategoria.nombre,
            "descripcion": subcategoria.descripcion,
            "categoria_id": subcategoria.categoria.id if subcategoria.categoria else None,
            "updated_at": subcategoria.updated_at,
        }

        return Response(data, status=status.HTTP_200_OK)

    except DatabaseError as e:
        return Response(
            {"error": f"Error de base de datos: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    except Exception as e:
        return Response(
            {"error": f"Error inesperado: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


## Eliminar Subcategoría (DELETE)
@api_view(['DELETE'])
@permission_classes([IsAuthenticated, RolePermission(SUBCATEGORY_MANAGER_ROLES)])
def delete_subcategory(request, pk):
    try:
        subcategoria = get_object_or_404(SubCategoria, pk=pk)
        subcategoria.delete()

        return Response(
            {"message": "Subcategoría eliminada correctamente", "deleted_at": subcategoria.deleted_at},
            status=status.HTTP_200_OK
        )

    except Exception as e:
        return Response(
            {"error": f"Error al eliminar la subcategoría: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated, RolePermission(SUBCATEGORY_MANAGER_ROLES)])
def list_subcategories_by_categoria(request):
    """
    Endpoint que lista todas las subcategorías asociadas a una categoría específica.
    Parámetro requerido:
        - categoria_id: ID de la categoría (en query params)
    """
    try:
        categoria_id = request.query_params.get('categoria_id', None)

        if not categoria_id:
            return Response(
                {"error": "El parámetro 'categoria_id' es obligatorio."},
                status=status.HTTP_400_BAD_REQUEST
            )

        #Filtrar por categoría
        subcategorias = SubCategoria.objects.select_related('categoria').filter(
            categoria_id=categoria_id
        ).order_by('nombre')

        data = [
            {
                "id": s.id,
                "nombre": s.nombre,
                "descripcion": s.descripcion,
                "categoria": s.categoria.nombre if s.categoria else None,
                "created_at": s.created_at,
                "updated_at": s.updated_at,
            }
            for s in subcategorias
        ]

        return Response(data, status=status.HTTP_200_OK)

    except Exception as e:
        return Response(
            {"error": f"Error al listar subcategorías por categoría: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )