# gasto/views.py
from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from django.shortcuts import get_object_or_404
from django.db import DatabaseError
from gastos.models import Gasto, RelacionarGasto
from user.api.permissions import RolePermission 

from django.db.models import Q # Necesario para el buscador
from datetime import datetime, time # Necesario para el manejo de fechas

# Roles permitidos para gestionar gastos
EXPENSE_MANAGER_ROLES = ['admin', 'contador'] 

# =========================================================================
# VISTAS DEL MODELO GASTO (MAESTRO)
# =========================================================================

## Crear Gasto (Maestro) (POST)
@api_view(['POST'])
@permission_classes([IsAuthenticated, RolePermission(EXPENSE_MANAGER_ROLES)])
def create_master_expense(request):
    # Lógica para crear un tipo de gasto (ej. 'Viajes')
    try:
        nombre = request.data.get('nombre')
        descripcion = request.data.get('descripcion', '')

        if not nombre:
            return Response({"error": "El nombre del Gasto (Maestro) es obligatorio."}, status=status.HTTP_400_BAD_REQUEST)
        
        if Gasto.objects.filter(nombre__iexact=nombre).exists():
            return Response({"error": "Ya existe un Gasto Maestro con ese nombre."}, status=status.HTTP_400_BAD_REQUEST)

        gasto = Gasto.objects.create(
            nombre=nombre,
            descripcion=descripcion,
            creado_por=request.user
        )
        return Response({
            "id": gasto.id, 
            "nombre": gasto.nombre,
            "creado_por": gasto.creado_por.username
        }, status=status.HTTP_201_CREATED)

    except Exception as e:
        return Response({"error": f"Error al crear el Gasto Maestro: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

## Listar Gastos (Maestro) (GET)
@api_view(['GET'])
@permission_classes([IsAuthenticated, RolePermission(EXPENSE_MANAGER_ROLES)])
def list_master_expenses(request):
    try:
        # Consulta inicial
        gastos = Gasto.objects.select_related('creado_por').all()
        
        # 1. Aplicar FILTROS
        
        # --- Filtro de Buscador (Search) ---
        search_query = request.query_params.get('search', None)
        if search_query:
            # Filtra por nombre o descripcion
            gastos = gastos.filter(
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
                gastos = gastos.filter(created_at__gte=start_datetime)
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
                gastos = gastos.filter(created_at__lte=end_datetime)
            except ValueError:
                return Response(
                    {"error": "El formato de la fecha de fin debe ser YYYY-MM-DD."},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # 2. Aplicar la ordenación (después de los filtros)
        gastos = gastos.order_by('nombre')
        
        # 3. Aplicar paginación
        paginator = PageNumberPagination()
        paginator.page_size = 10 
        paginated_gastos = paginator.paginate_queryset(gastos, request)

        # 4. Serialización manual de los datos
        data = [{
            'id': g.id,
            'nombre': g.nombre,
            'descripcion': g.descripcion,
            'creado_por_username': g.creado_por.username if g.creado_por else None,
            'created_at': g.created_at,
        } for g in paginated_gastos]

        return paginator.get_paginated_response(data)

    except Exception as e:
        # Recomendable agregar logging aquí
        return Response(
            {"error": f"Error al listar Gastos Maestros: {str(e)}"}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
## Obtener Gasto (Maestro) por ID (GET)
@api_view(['GET'])
@permission_classes([IsAuthenticated, RolePermission(EXPENSE_MANAGER_ROLES)])
def get_master_expense(request, pk):
    try:
        # Busca solo gastos maestros NO eliminados
        gasto = get_object_or_404(Gasto.objects.select_related('creado_por'), pk=pk)
        
        data = {
            "id": gasto.id,
            "nombre": gasto.nombre,
            "descripcion": gasto.descripcion,
            "creado_por": gasto.creado_por.username if gasto.creado_por else None,
            "created_at": gasto.created_at,
            "updated_at": gasto.updated_at,
            "deleted_at": gasto.deleted_at,
        }
        return Response(data, status=status.HTTP_200_OK)

    except Exception as e:
        return Response(
            {"error": f"Error al obtener el Gasto Maestro: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['PUT'])
@permission_classes([IsAuthenticated, RolePermission(EXPENSE_MANAGER_ROLES)])
def update_master_expense(request, pk):
    try:
        # Solo permite actualizar gastos maestros NO eliminados
        gasto = get_object_or_404(Gasto, pk=pk)
        
        nombre = request.data.get('nombre', gasto.nombre)
        descripcion = request.data.get('descripcion', gasto.descripcion)

        # Validación: Evitar colisión de nombre con otros gastos maestros ACTIVOS
        if nombre != gasto.nombre and Gasto.objects.filter(nombre__iexact=nombre).exists():
             return Response(
                {"error": "Ya existe otro Gasto Maestro (activo) con ese nombre."},
                status=status.HTTP_400_BAD_REQUEST
            )

        gasto.nombre = nombre
        gasto.descripcion = descripcion
        gasto.save()

        data = {
            "id": gasto.id,
            "nombre": gasto.nombre,
            "updated_at": gasto.updated_at,
        }
        return Response(data, status=status.HTTP_200_OK)

    except DatabaseError as e:
        return Response(
            {"error": f"Error de base de datos al actualizar el Gasto Maestro: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    except Exception as e:
        return Response(
            {"error": f"Error inesperado al actualizar el Gasto Maestro: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
       
## Eliminar Gasto (Maestro) (DELETE) - Eliminación Lógica
@api_view(['DELETE'])
@permission_classes([IsAuthenticated, RolePermission(['admin'])])
def delete_master_expense(request, pk):
    try:
        gasto = get_object_or_404(Gasto, pk=pk)
        gasto.delete() # Soft delete
        
        return Response(
            {"message": "Gasto Maestro eliminado lógicamente.", "deleted_at": gasto.deleted_at}, 
            status=status.HTTP_200_OK
        )
    except Exception as e:
        return Response({"error": f"Error al eliminar Gasto Maestro: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# =========================================================================
# VISTAS DEL MODELO RELACIONARGASTO (TRANSACCIONAL)
# =========================================================================

## Crear Registro de Gasto (POST)
@api_view(['POST'])
@permission_classes([IsAuthenticated, RolePermission(EXPENSE_MANAGER_ROLES)])
def create_expense_record(request):
    # Lógica para registrar una ocurrencia de gasto
    try:
        gasto_id = request.data.get('gasto_id')
        total_gasto = request.data.get('total_gasto')
        descripcion = request.data.get('descripcion')

        if not all([gasto_id, total_gasto, descripcion]):
            return Response(
                {"error": "Los campos 'gasto_id', 'total_gasto' y 'descripcion' son obligatorios."}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 1. Validar que el Gasto Maestro exista y esté activo
        gasto_maestro = get_object_or_404(Gasto, pk=gasto_id)

        # 2. Crear el registro transaccional
        registro = RelacionarGasto.objects.create(
            gasto=gasto_maestro,
            total_gasto=total_gasto,
            descripcion=descripcion,
            creado_por=request.user
        )
        return Response({
            "id": registro.id, 
            "tipo_gasto": registro.gasto.nombre,
            "total_gasto": registro.total_gasto,
            "creado_por": registro.creado_por.username
        }, status=status.HTTP_201_CREATED)

    except Gasto.DoesNotExist:
        return Response({"error": "El Gasto Maestro especificado no existe o está eliminado."}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({"error": f"Error al crear el registro de gasto: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

## Listar Registros de Gasto (GET)
@api_view(['GET'])
@permission_classes([IsAuthenticated, RolePermission(EXPENSE_MANAGER_ROLES)])
def list_expense_records(request):
    try:
        # Consulta inicial
        # select_related es crucial para permitir la búsqueda en r.gasto.nombre
        registros = RelacionarGasto.objects.select_related('gasto', 'creado_por').all()
        
        # 1. Aplicar FILTROS
        
        # --- Filtro de Buscador (Search) ---
        search_query = request.query_params.get('search', None)
        if search_query:
            # Filtra por la descripción del registro o por el nombre del gasto relacionado
            registros = registros.filter(
                Q(descripcion__icontains=search_query) |
                Q(gasto__nombre__icontains=search_query) # Búsqueda en el campo 'nombre' del modelo 'gasto' relacionado
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
                registros = registros.filter(created_at__gte=start_datetime)
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
                registros = registros.filter(created_at__lte=end_datetime)
            except ValueError:
                return Response(
                    {"error": "El formato de la fecha de fin debe ser YYYY-MM-DD."},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # 2. Aplicar la ordenación (por fecha de creación más reciente)
        registros = registros.order_by('-created_at')
        
        # 3. Aplicar paginación
        paginator = PageNumberPagination()
        paginator.page_size = 10 
        paginated_records = paginator.paginate_queryset(registros, request)

        # 4. Serialización manual de los datos
        data = [{
            'id': r.id,
            'tipo_gasto': r.gasto.nombre if r.gasto else 'N/A',
            'total_gasto': r.total_gasto,
            'descripcion_registro': r.descripcion,
            'creado_por_username': r.creado_por.username if r.creado_por else None,
            'created_at': r.created_at,
        } for r in paginated_records]

        return paginator.get_paginated_response(data)

    except Exception as e:
        return Response({"error": f"Error al listar registros de gastos: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
## Obtener Registro de Gasto por ID (GET)
@api_view(['GET'])
@permission_classes([IsAuthenticated, RolePermission(EXPENSE_MANAGER_ROLES)])
def get_expense_record(request, pk):
    try:
        # Busca solo registros de gasto NO eliminados
        registro = get_object_or_404(RelacionarGasto.objects.select_related('gasto', 'creado_por'), pk=pk)
        
        data = {
            "id": registro.id,
            "gasto_id": registro.gasto.id if registro.gasto else None,
            "tipo_gasto_nombre": registro.gasto.nombre if registro.gasto else 'N/A',
            "total_gasto": registro.total_gasto,
            "descripcion": registro.descripcion,
            "creado_por": registro.creado_por.username if registro.creado_por else None,
            "created_at": registro.created_at,
            "updated_at": registro.updated_at,
            "deleted_at": registro.deleted_at,
        }
        return Response(data, status=status.HTTP_200_OK)

    except Exception as e:
        return Response(
            {"error": f"Error al obtener el Registro de Gasto: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['PUT'])
@permission_classes([IsAuthenticated, RolePermission(EXPENSE_MANAGER_ROLES)])
def update_expense_record(request, pk):
    try:
        # Solo permite actualizar registros NO eliminados
        registro = get_object_or_404(RelacionarGasto, pk=pk)
        
        gasto_id = request.data.get('gasto_id')
        total_gasto = request.data.get('total_gasto', registro.total_gasto)
        descripcion = request.data.get('descripcion', registro.descripcion)

        # 1. Validar y actualizar el Gasto Maestro (si se proporciona un nuevo ID)
        if gasto_id is not None and gasto_id != (registro.gasto.id if registro.gasto else None):
            gasto_maestro = get_object_or_404(Gasto, pk=gasto_id)
            registro.gasto = gasto_maestro

        # 2. Asignar campos
        registro.total_gasto = total_gasto
        registro.descripcion = descripcion
        
        registro.save()

        data = {
            "id": registro.id,
            "tipo_gasto": registro.gasto.nombre if registro.gasto else 'N/A',
            "total_gasto": registro.total_gasto,
            "updated_at": registro.updated_at,
        }
        return Response(data, status=status.HTTP_200_OK)

    except Gasto.DoesNotExist:
        return Response(
            {"error": "El Gasto Maestro especificado no existe o está eliminado."},
            status=status.HTTP_404_NOT_FOUND
        )
    except DatabaseError as e:
        return Response(
            {"error": f"Error de base de datos al actualizar el Registro de Gasto: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    except Exception as e:
        return Response(
            {"error": f"Error inesperado al actualizar el Registro de Gasto: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    
## Eliminar Registro de Gasto (DELETE) - Eliminación Lógica
@api_view(['DELETE'])
@permission_classes([IsAuthenticated, RolePermission(['admin', 'contador'])])
def delete_expense_record(request, pk):
    try:
        registro = get_object_or_404(RelacionarGasto, pk=pk)
        registro.delete() # Soft delete
        
        return Response(
            {"message": "Registro de gasto eliminado lógicamente.", "deleted_at": registro.deleted_at}, 
            status=status.HTTP_200_OK
        )
    except Exception as e:
        return Response({"error": f"Error al eliminar registro de gasto: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)