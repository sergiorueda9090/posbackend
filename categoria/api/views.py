# categoria/views.py
from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from django.shortcuts import get_object_or_404
from django.db import DatabaseError, IntegrityError
from categoria.models import Categoria
from user.api.permissions import RolePermission 

from django.db.models import Q # Importar Q para búsquedas complejas
from datetime import datetime, time # Importar datetime y time para manejar fechas

# Roles permitidos para gestionar categorías (ej. solo administradores)
CATEGORY_MANAGER_ROLES = ['admin']

## Crear Categoría (POST)
@api_view(['POST'])
@permission_classes([IsAuthenticated, RolePermission(CATEGORY_MANAGER_ROLES)])
def create_category(request):
    try:
        nombre      = request.data.get('nombre')
        descripcion = request.data.get('descripcion', '')

        if not nombre:
            return Response(
                {"error": "El nombre de la categoría es obligatorio."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validación: Prevenir duplicados (incluso si están eliminados lógicamente)
        # Usamos all_objects y filtramos por nombre, asegurando unicidad del nombre.
        if Categoria.all_objects.filter(nombre__iexact=nombre).exists():
             return Response(
                {"error": "Ya existe una categoría con ese nombre."},
                status=status.HTTP_400_BAD_REQUEST
            )

        categoria = Categoria.objects.create(
            nombre      = nombre,
            descripcion = descripcion,
            creado_por  = request.user
        )

        data = {
            "id"        : categoria.id,
            "nombre"    : categoria.nombre,
            "creado_por": categoria.creado_por.username
        }
        return Response(data, status=status.HTTP_201_CREATED)

    except IntegrityError:
        return Response(
            {"error": "Error de integridad. Puede que el nombre ya exista."},
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        return Response(
            {"error": f"Error inesperado al crear la categoría: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

## Listar Categorías (GET)
@api_view(['GET'])
@permission_classes([IsAuthenticated, RolePermission(CATEGORY_MANAGER_ROLES)])
def list_categories(request):
    try:
        # Categoria.objects.all() usa SoftDeleteManager, solo trae categorías NO eliminadas
        categorias = Categoria.objects.select_related('creado_por').all()
        
        # 1. Aplicar FILTROS
        
        # --- Filtro de Buscador (Search) ---
        search_query = request.query_params.get('search', None)
        if search_query:
            # Filtra por nombre o descripcion
            categorias = categorias.filter(
                Q(nombre__icontains=search_query) |
                Q(descripcion__icontains=search_query)
            )

        # --- Filtros de Fecha de Inicio y Fecha de Fin (Date Range) ---
        start_date_str = request.query_params.get('start_date', None)
        end_date_str = request.query_params.get('end_date', None)

        if start_date_str:
            try:
                # Convertir la cadena a objeto datetime.date
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                # Filtrar categorías cuya fecha de creación sea mayor o igual a la fecha de inicio
                # Incluye todo el día, desde 00:00:00
                start_datetime = datetime.combine(start_date, time.min)
                categorias = categorias.filter(created_at__gte=start_datetime)
            except ValueError:
                return Response(
                    {"error": "El formato de la fecha de inicio debe ser YYYY-MM-DD."},
                    status=status.HTTP_400_BAD_REQUEST
                )

        if end_date_str:
            try:
                # Convertir la cadena a objeto datetime.date
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
                # Filtrar categorías cuya fecha de creación sea menor o igual a la fecha de fin
                # Incluye todo el día hasta 23:59:59.999999
                end_datetime = datetime.combine(end_date, time.max)
                categorias = categorias.filter(created_at__lte=end_datetime)
            except ValueError:
                return Response(
                    {"error": "El formato de la fecha de fin debe ser YYYY-MM-DD."},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # 2. Ordenación
        # Se ordena después de los filtros
        categorias = categorias.order_by('nombre')
        
        # 3. IMPLEMENTACIÓN DE PAGINACIÓN
        paginator = PageNumberPagination()
        paginator.page_size = 10 # Define el número de elementos por página
        paginated_categories = paginator.paginate_queryset(categorias, request)

        # 4. Serializar los datos de la página actual
        data = [{
            'id'                  : c.id,
            'nombre'              : c.nombre,
            'descripcion'         : c.descripcion,
            # Asegúrate de que .creado_por exista antes de acceder a .username
            'creado_por_username' : c.creado_por.username if c.creado_por else None,
            'created_at'          : c.created_at,
            'updated_at'          : c.updated_at,
        } for c in paginated_categories]

        return paginator.get_paginated_response(data)

    except Exception as e:
        # Se puede añadir logging aquí para depuración
        print(f"Error en list_categories: {e}")
        return Response(
            {"error": f"Error al obtener la lista de categorías: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

## Obtener Categoría por ID (GET)
@api_view(['GET'])
@permission_classes([IsAuthenticated, RolePermission(CATEGORY_MANAGER_ROLES)])
def get_category(request, pk):
    try:
        # Solo busca categorías NO eliminadas
        categoria = get_object_or_404(Categoria.objects.select_related('creado_por'), pk=pk)
        
        data = {
            "id": categoria.id,
            "nombre": categoria.nombre,
            "descripcion": categoria.descripcion,
            "creado_por": categoria.creado_por.username if categoria.creado_por else None,
            "created_at": categoria.created_at,
            "updated_at": categoria.updated_at,
            "deleted_at": categoria.deleted_at,
        }
        return Response(data, status=status.HTTP_200_OK)

    except Exception as e:
        return Response(
            {"error": f"Error al obtener la categoría: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

## Actualizar Categoría (PUT)
@api_view(['PUT'])
@permission_classes([IsAuthenticated, RolePermission(CATEGORY_MANAGER_ROLES)])
def update_category(request, pk):
    try:
        # Solo permite actualizar categorías NO eliminadas
        categoria = get_object_or_404(Categoria, pk=pk)
        
        nombre = request.data.get('nombre', categoria.nombre)
        descripcion = request.data.get('descripcion', categoria.descripcion)

        # Validación: Evitar colisión de nombre con otras categorías ACTIVAS
        if nombre != categoria.nombre and Categoria.objects.filter(nombre__iexact=nombre).exists():
             return Response(
                {"error": "Ya existe otra categoría (activa) con ese nombre."},
                status=status.HTTP_400_BAD_REQUEST
            )

        categoria.nombre = nombre
        categoria.descripcion = descripcion
        categoria.save()

        data = {
            "id": categoria.id,
            "nombre": categoria.nombre,
            "updated_at": categoria.updated_at,
        }
        return Response(data, status=status.HTTP_200_OK)

    except DatabaseError as e:
        return Response(
            {"error": f"Error de base de datos al actualizar la categoría: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    except Exception as e:
        return Response(
            {"error": f"Error inesperado al actualizar la categoría: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

## Eliminar Categoría (DELETE) - Eliminación Lógica
@api_view(['DELETE'])
@permission_classes([IsAuthenticated, RolePermission(CATEGORY_MANAGER_ROLES)])
def delete_category(request, pk):
    try:
        # Solo busca categorías NO eliminadas
        categoria = get_object_or_404(Categoria, pk=pk)
        
        # Ejecuta el soft delete (establece deleted_at)
        categoria.delete()
        
        return Response(
            {"message": "Categoría eliminada lógicamente exitosamente", "deleted_at": categoria.deleted_at}, 
            status=status.HTTP_200_OK
        )
    except Exception as e:
        return Response(
            {"error": f"Error al ejecutar la eliminación lógica de la categoría: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )