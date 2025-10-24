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
        # TarjetaBancaria.objects solo trae tarjetas NO eliminadas
        tarjetas = TarjetaBancaria.objects.select_related('creado_por').order_by('-created_at')
        
        # Aplicar paginación
        paginator           = PageNumberPagination()
        paginator.page_size = 10 
        paginated_cards     = paginator.paginate_queryset(tarjetas, request)

        # Serialización manual de los datos
        data = [{
            'id'                    : t.id,
            'nombre'                : t.nombre,
            'descripcion'           : t.descripcion,
            'pan_ultimos_4'         : t.pan[-4:],
            'creado_por_username'   : t.creado_por.username if t.creado_por else None,
            'created_at'            : t.created_at,
            'updated_at'            : t.updated_at,
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