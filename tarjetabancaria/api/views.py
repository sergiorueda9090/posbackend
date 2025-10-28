# tarjeta/views.py
from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from django.shortcuts import get_object_or_404
from django.db import DatabaseError
from tarjetabancaria.models import TarjetaBancaria
from user.api.permissions import RolePermission 

from django.db.models import Q # Necesario para el buscador
from datetime import datetime, time # Necesario para el manejo de fechas

# Roles permitidos para gestionar tarjetas
CARD_MANAGER_ROLES = ['admin', 'contador'] 

## Crear Tarjeta Bancaria (POST)
@api_view(['POST'])
@permission_classes([IsAuthenticated, RolePermission(CARD_MANAGER_ROLES)])
def create_card(request):
    try:
        nombre      = request.data.get('nombre')
        pan         = request.data.get('pan')
        descripcion = request.data.get('descripcion', '')

        # 1. Validar campos obligatorios
        if not all([nombre, pan]):
            return Response(
                {"error": "Los campos 'nombre' y 'pan' (número de tarjeta) son obligatorios."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 2. Validación de unicidad de PAN
        if TarjetaBancaria.objects.filter(pan=pan).exists():
            return Response(
                {"error": "Ya existe una tarjeta activa con ese número (PAN)."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 3. Crear la tarjeta
        tarjeta = TarjetaBancaria.objects.create(
            nombre      = nombre,
            descripcion = descripcion,
            pan         = pan,
            creado_por  = request.user
        )

        data = {
            "id"            : tarjeta.id,
            "nombre"        : tarjeta.nombre,
            "pan_ultimos_4" : tarjeta.pan[-4:],
            "creado_por"    : tarjeta.creado_por.username
        }
        return Response(data, status=status.HTTP_201_CREATED)

    except DatabaseError as e:
        return Response(
            {"error": f"Error de base de datos al crear la tarjeta: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    except Exception as e:
        return Response(
            {"error": f"Error inesperado al crear la tarjeta: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

## Listar Tarjetas Bancarias (GET)
@api_view(['GET'])
@permission_classes([IsAuthenticated, RolePermission(CARD_MANAGER_ROLES)])
def list_cards(request):
    try:
        # Consulta inicial (SoftDeleteManager ya filtra por no eliminadas)
        tarjetas = TarjetaBancaria.objects.select_related('creado_por').all()
        
        # 1. Aplicar FILTROS
        
        # --- Filtro de Buscador (Search) ---
        search_query = request.query_params.get('search', None)
        if search_query:
            # Filtra por nombre o descripcion de la tarjeta
            tarjetas = tarjetas.filter(
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
                # Incluye todo el día de inicio (desde 00:00:00)
                start_datetime = datetime.combine(start_date, time.min)
                tarjetas = tarjetas.filter(created_at__gte=start_datetime)
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
                tarjetas = tarjetas.filter(created_at__lte=end_datetime)
            except ValueError:
                return Response(
                    {"error": "El formato de la fecha de fin debe ser YYYY-MM-DD."},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # 2. Aplicar la ordenación (después de los filtros)
        # Se mantiene la ordenación descendente por fecha de creación para mostrar las más recientes primero
        tarjetas = tarjetas.order_by('-created_at')
        
        # 3. Aplicar paginación
        paginator = PageNumberPagination()
        paginator.page_size = 10 
        paginated_cards = paginator.paginate_queryset(tarjetas, request)

        # 4. Serialización manual de los datos
        data = [{
            'id'                  : t.id,
            'nombre'              : t.nombre,
            'descripcion'         : t.descripcion,
            # NOTA: pan_ultimos_4 no se puede usar para filtrar por seguridad/diseño
            'pan_ultimos_4'       : t.pan[-4:],
            'creado_por_username' : t.creado_por.username if t.creado_por else None,
            'created_at'          : t.created_at,
            'updated_at'          : t.updated_at,
        } for t in paginated_cards]

        return paginator.get_paginated_response(data)

    except Exception as e:
        return Response(
            {"error": f"Error al obtener la lista de tarjetas: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

## Obtener Tarjeta por ID (GET)
@api_view(['GET'])
@permission_classes([IsAuthenticated, RolePermission(CARD_MANAGER_ROLES)])
def get_card(request, pk):
    try:
        # Solo busca tarjetas NO eliminadas
        tarjeta = get_object_or_404(TarjetaBancaria.objects.select_related('creado_por'), pk=pk)
        
        data = {
            "id"            : tarjeta.id,
            "nombre"        : tarjeta.nombre,
            "descripcion"   : tarjeta.descripcion,
            "pan_ultimos_4" : tarjeta.pan[-4:],
            "creado_por"    : tarjeta.creado_por.username if tarjeta.creado_por else None,
            "created_at"    : tarjeta.created_at,
            "updated_at"    : tarjeta.updated_at,
            "deleted_at"    : tarjeta.deleted_at,
        }
        return Response(data, status=status.HTTP_200_OK)

    except Exception as e:
        return Response(
            {"error": f"Error al obtener la tarjeta: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

## Actualizar Tarjeta (PUT/PATCH)
@api_view(['PUT', 'PATCH'])
@permission_classes([IsAuthenticated, RolePermission(CARD_MANAGER_ROLES)])
def update_card(request, pk):
    try:
        # Solo permite actualizar tarjetas NO eliminadas
        tarjeta = get_object_or_404(TarjetaBancaria, pk=pk)
        
        # Solo permitimos actualizar campos no sensibles o que cambien con el tiempo
        tarjeta.nombre      = request.data.get('nombre', tarjeta.nombre)
        tarjeta.descripcion = request.data.get('descripcion', tarjeta.descripcion)
        
        # Manejo del PAN (el PAN no debería ser actualizado normalmente)
        new_pan = request.data.get('pan')
        if new_pan and new_pan != tarjeta.pan:
            if TarjetaBancaria.objects.filter(pan=new_pan).exists():
                return Response(
                    {"error": "Ya existe otra tarjeta (activa) con ese número (PAN)."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            tarjeta.pan = new_pan
            
        tarjeta.save()

        data = {
            "id"            : tarjeta.id,
            "nombre"        : tarjeta.nombre,
            "pan_ultimos_4" : tarjeta.pan[-4:],
            "updated_at"    : tarjeta.updated_at,
        }
        return Response(data, status=status.HTTP_200_OK)

    except DatabaseError as e:
        return Response(
            {"error": f"Error de base de datos al actualizar la tarjeta: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    except Exception as e:
        return Response(
            {"error": f"Error inesperado al actualizar la tarjeta: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

## Eliminar Tarjeta (DELETE) - Eliminación Lógica
@api_view(['DELETE'])
@permission_classes([IsAuthenticated, RolePermission(['admin'])])
def delete_card(request, pk):
    try:
        # Solo busca tarjetas NO eliminadas
        tarjeta = get_object_or_404(TarjetaBancaria, pk=pk)
        
        # Ejecuta el soft delete (establece deleted_at)
        tarjeta.delete()
        
        return Response(
            {"message": "Tarjeta eliminada lógicamente exitosamente", "deleted_at": tarjeta.deleted_at}, 
            status=status.HTTP_200_OK
        )
    except Exception as e:
        return Response(
            {"error": f"Error al ejecutar la eliminación lógica de la tarjeta: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )