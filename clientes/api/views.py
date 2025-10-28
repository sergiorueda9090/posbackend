# client/views.py
from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from django.shortcuts import get_object_or_404
from django.db import DatabaseError
from clientes.models import Cliente
from user.api.permissions import RolePermission 

from django.db.models import Q # Necesario para el buscador
from datetime import datetime, time # Necesario para el manejo de fechas
# Roles permitidos para gestionar clientes
CLIENT_MANAGER_ROLES = ['admin', 'contador']

## Crear Cliente (POST) - NO REQUIERE CAMBIOS DE LÓGICA DE ELIMINACIÓN
@api_view(['POST'])
@permission_classes([IsAuthenticated, RolePermission(CLIENT_MANAGER_ROLES)])
def create_client(request):
    try:
        # Campos requeridos
        nombre = request.data.get('nombre')
        email = request.data.get('email')

        if not nombre:
            return Response(
                {"error": "El nombre del cliente es obligatorio."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # CAMBIO DE VALIDACIÓN: Usar all_objects para validar unicidad incluso contra eliminados
        # Si el email es único, pero existía en un registro eliminado, es tu decisión si lo permites.
        # Aquí, vamos a asumir que no se puede usar un email aunque el cliente esté eliminado lógicamente.
        if email and Cliente.all_objects.filter(email=email, deleted_at__isnull=True).exists():
            return Response(
                {"error": "Ya existe un cliente con este email."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Crea la instancia del cliente
        cliente = Cliente.objects.create(
            nombre      = nombre,
            apellido    = request.data.get('apellido'),
            email       = email,
            telefono    = request.data.get('telefono'),
            direccion   = request.data.get('direccion'),
            creado_por  = request.user # Asigna el usuario autenticado como creador
        )

        data = {
            "id"        : cliente.id,
            "nombre"    : cliente.nombre,
            "email"     : cliente.email,
            "creado_por": cliente.creado_por.username
        }

        return Response(data, status=status.HTTP_201_CREATED)
    
    except DatabaseError as e:
        return Response(
            {"error": f"Error de base de datos al crear el cliente: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    except Exception as e:
        return Response(
            {"error": f"Error inesperado al crear el cliente: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

# ----------------------------------------------------------------------
## Listar Clientes (GET) - CAMBIO: Cliente.objects.all() es correcto
@api_view(['GET'])
@permission_classes([IsAuthenticated, RolePermission(CLIENT_MANAGER_ROLES)])
def list_clients(request):
    try:
        # Consulta inicial
        # SoftDeleteManager asegura que deleted_at sea NULL
        clientes = Cliente.objects.select_related('creado_por').all()
        
        # 1. Aplicar FILTROS
        
        # --- Filtro de Buscador (Search) ---
        search_query = request.query_params.get('search', None)
        if search_query:
            # Filtra por nombre, apellido, email o teléfono
            clientes = clientes.filter(
                Q(nombre__icontains=search_query) |
                Q(apellido__icontains=search_query) |
                Q(email__icontains=search_query) |
                Q(telefono__icontains=search_query) 
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
                clientes = clientes.filter(created_at__gte=start_datetime)
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
                clientes = clientes.filter(created_at__lte=end_datetime)
            except ValueError:
                return Response(
                    {"error": "El formato de la fecha de fin debe ser YYYY-MM-DD."},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # 2. Aplicar la ordenación (después de los filtros)
        clientes = clientes.order_by('nombre')
        
        # 3. Aplicar paginación
        paginator = PageNumberPagination()
        paginator.page_size = 30 
        paginated_clients = paginator.paginate_queryset(clientes, request)

        # 4. Serialización manual de los datos
        data = [{
            'id'           : c.id,
            'nombre'       : c.nombre,
            'apellido'     : c.apellido,
            'email'        : c.email,
            'telefono'     : c.telefono,
            'creado_por_username': c.creado_por.username if c.creado_por else None,
            'created_at'   : c.created_at,
            'updated_at'   : c.updated_at,
        } for c in paginated_clients]

        return paginator.get_paginated_response(data)

    except Exception as e:
        # Recomendable agregar logging aquí
        return Response(
            {"error": f"Error al obtener la lista de clientes: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

# ----------------------------------------------------------------------
## Obtener Cliente por ID (GET) - NO REQUIERE CAMBIOS DE MANAGER
@api_view(['GET'])
@permission_classes([IsAuthenticated, RolePermission(CLIENT_MANAGER_ROLES)])
def get_client(request, pk):
    try:
        # CORRECCIÓN: get_object_or_404 usa Cliente.objects por defecto, 
        # que solo busca entre los NO eliminados. Si no lo encuentra (porque está eliminado),
        # lanzará 404, que es el comportamiento deseado.
        cliente = get_object_or_404(Cliente.objects.select_related('creado_por'), pk=pk)
        
        data = {
            "id"         : cliente.id,
            "nombre"     : cliente.nombre,
            "apellido"   : cliente.apellido,
            "email"      : cliente.email,
            "telefono"   : cliente.telefono,
            "direccion"  : cliente.direccion,
            "creado_por" : cliente.creado_por.username if cliente.creado_por else None,
            "created_at" : cliente.created_at,
            "updated_at" : cliente.updated_at,
            "deleted_at" : cliente.deleted_at, # Incluir el estado de eliminación lógica
        }
        return Response(data, status=status.HTTP_200_OK)

    except Exception as e:
        return Response(
            {"error": f"Error al obtener el cliente: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

# ----------------------------------------------------------------------
## Actualizar Cliente (PUT) - NO REQUIERE CAMBIOS DE MANAGER
@api_view(['PUT'])
@permission_classes([IsAuthenticated, RolePermission(CLIENT_MANAGER_ROLES)])
def update_client(request, pk):
    try:
        # 💡 CORRECCIÓN: Solo permite actualizar clientes NO eliminados (usa Cliente.objects por defecto)
        cliente = get_object_or_404(Cliente, pk=pk) 
        
        # ... (Lógica de actualización de campos) ...
        cliente.nombre      = request.data.get('nombre', cliente.nombre)
        cliente.apellido    = request.data.get('apellido', cliente.apellido)
        cliente.email       = request.data.get('email', cliente.email)
        cliente.telefono    = request.data.get('telefono', cliente.telefono)
        cliente.direccion   = request.data.get('direccion', cliente.direccion)


        # Validación de email único si se intenta cambiar (incluye no eliminados)
        new_email = request.data.get('email')
        # 💡 CAMBIO: Usar Cliente.objects para evitar colisión con otros clientes NO eliminados
        # Si quieres evitar colisión incluso con eliminados, usa Cliente.all_objects
        if new_email and new_email != cliente.email and Cliente.objects.filter(email=new_email).exists(): 
             return Response(
                {"error": "Ya existe otro cliente (activo) con este email."},
                status=status.HTTP_400_BAD_REQUEST
            )

        cliente.save()

        data = {
            "id"         : cliente.id,
            "nombre"     : cliente.nombre,
            "email"      : cliente.email,
            "updated_at" : cliente.updated_at, #CAMBIO: Usar el nuevo nombre del campo
        }
        return Response(data, status=status.HTTP_200_OK)

    except DatabaseError as e:
        return Response(
            {"error": f"Error de base de datos al actualizar el cliente: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    except Exception as e:
        return Response(
            {"error": f"Error inesperado al actualizar el cliente: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

# ----------------------------------------------------------------------
## Eliminar Cliente (DELETE) - CAMBIO CLAVE
@api_view(['DELETE'])
@permission_classes([IsAuthenticated, RolePermission(['admin'])]) # Solo admin puede eliminar
def delete_client(request, pk):
    try:
        # CAMBIO CLAVE: Usamos get_object_or_404 con el manager por defecto (objects), 
        # que solo encuentra clientes NO eliminados (deleted_at=NULL).
        cliente = get_object_or_404(Cliente, pk=pk) 

        # Llama al método .delete() del modelo, que ahora hace la eliminación LÓGICA (soft delete)
        cliente.delete()
        
        return Response(
            # CAMBIO DE MENSAJE: Reflejar la eliminación lógica
            {"message": "Cliente eliminado lógicamente exitosamente", "deleted_at": cliente.deleted_at}, 
            status=status.HTTP_200_OK # Se cambia a 200/204, aunque 204 No Content es el estándar,
                                      # al no ser una eliminación real, 200 es aceptable si devuelves data.
        )
    except Exception as e:
        return Response(
            {"error": f"Error al ejecutar la eliminación lógica del cliente: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )