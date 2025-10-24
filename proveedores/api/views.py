# proveedor/views.py
from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from django.shortcuts import get_object_or_404
from django.db import DatabaseError
from proveedores.models import Proveedor
from user.api.permissions import RolePermission 

# Roles permitidos para gestionar proveedores (admin y contador/manager)
SUPPLIER_MANAGER_ROLES = ['admin', 'contador'] 

## Crear Proveedor (POST)
@api_view(['POST'])
@permission_classes([IsAuthenticated, RolePermission(SUPPLIER_MANAGER_ROLES)])
def create_supplier(request):
    try:
        nombre_empresa  = request.data.get('nombre_empresa')
        ruc             = request.data.get('ruc')
        email           = request.data.get('email')

        if not nombre_empresa:
            return Response(
                {"error": "El nombre de la empresa es obligatorio."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validación de unicidad contra registros NO eliminados
        if Proveedor.objects.filter(nombre_empresa__iexact=nombre_empresa).exists():
            return Response(
                {"error": "Ya existe un proveedor con ese nombre de empresa."},
                status=status.HTTP_400_BAD_REQUEST
            )
        if ruc and Proveedor.objects.filter(ruc=ruc).exists():
            return Response(
                {"error": "Ya existe un proveedor con ese RUC/Tax ID."},
                status=status.HTTP_400_BAD_REQUEST
            )
        if email and Proveedor.objects.filter(email=email).exists():
            return Response(
                {"error": "Ya existe un proveedor con ese email."},
                status=status.HTTP_400_BAD_REQUEST
            )

        proveedor = Proveedor.objects.create(
            nombre_empresa      = nombre_empresa,
            contacto_principal  = request.data.get('contacto_principal'),
            ruc                  = ruc,
            email                = email,
            telefono             = request.data.get('telefono'),
            direccion            = request.data.get('direccion'),
            ciudad               = request.data.get('ciudad'),
            creado_por           = request.user
        )

        data = {
            "id"            : proveedor.id,
            "nombre_empresa": proveedor.nombre_empresa,
            "ruc"           : proveedor.ruc,
            "creado_por"    : proveedor.creado_por.username
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
        # Proveedor.objects solo trae proveedores NO eliminados (SoftDeleteManager)
        proveedores = Proveedor.objects.select_related('creado_por').order_by('nombre_empresa')
        
        # Aplicar paginación
        paginator           = PageNumberPagination()
        paginator.page_size = 10 
        paginated_suppliers = paginator.paginate_queryset(proveedores, request)

        # Serialización manual de los datos
        data = [{
            'id': p.id,
            'nombre_empresa'      : p.nombre_empresa,
            'contacto_principal'  : p.contacto_principal,
            'ruc'                 : p.ruc,
            'email'               : p.email,
            'telefono'            : p.telefono,
            'ciudad'              : p.ciudad,
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
            "contacto_principal": proveedor.contacto_principal,
            "ruc"               : proveedor.ruc,
            "email"             : proveedor.email,
            "telefono"          : proveedor.telefono,
            "direccion"         : proveedor.direccion,
            "ciudad"            : proveedor.ciudad,
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
        nombre_empresa  = request.data.get('nombre_empresa', proveedor.nombre_empresa)
        ruc             = request.data.get('ruc', proveedor.ruc)
        email           = request.data.get('email', proveedor.email)

        # Validación de unicidad para nombre_empresa
        if nombre_empresa != proveedor.nombre_empresa and Proveedor.objects.filter(nombre_empresa__iexact=nombre_empresa).exists():
             return Response(
                {"error": "Ya existe otro proveedor (activo) con ese nombre de empresa."},
                status=status.HTTP_400_BAD_REQUEST
            )
        # Validación de unicidad para RUC
        if ruc and ruc != proveedor.ruc and Proveedor.objects.filter(ruc=ruc).exists():
             return Response(
                {"error": "Ya existe otro proveedor (activo) con ese RUC/Tax ID."},
                status=status.HTTP_400_BAD_REQUEST
            )
        # Validación de unicidad para Email
        if email and email != proveedor.email and Proveedor.objects.filter(email=email).exists():
             return Response(
                {"error": "Ya existe otro proveedor (activo) con ese email."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Asignar campos
        proveedor.nombre_empresa       = nombre_empresa
        proveedor.contacto_principal   = request.data.get('contacto_principal', proveedor.contacto_principal)
        proveedor.ruc                  = ruc
        proveedor.email                = email
        proveedor.telefono             = request.data.get('telefono', proveedor.telefono)
        proveedor.direccion            = request.data.get('direccion', proveedor.direccion)
        proveedor.ciudad               = request.data.get('ciudad', proveedor.ciudad)

        proveedor.save()

        data = {
            "id"            : proveedor.id,
            "nombre_empresa": proveedor.nombre_empresa,
            "updated_at"    : proveedor.updated_at,
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