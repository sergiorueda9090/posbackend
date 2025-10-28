from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.pagination import PageNumberPagination
from django.shortcuts import get_object_or_404
from django.contrib.auth.hashers import make_password
from django.db import DatabaseError
from user.models import User
from .permissions import RolePermission

from django.db.models import Q # Importar Q para búsquedas complejas
from datetime import datetime  # Importar datetime para manejar fechas

# Obtener usuario autenticado
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def me_view(request):
    try:
        user = request.user
        data = {
            "id": user.id,
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "email": user.email,
            "role": user.role,
            "is_active": user.is_active,
            "is_staff": user.is_staff,
            "is_superuser": user.is_superuser,
            "last_login": user.last_login,
            "date_joined": user.date_joined,
        }
        return Response(data, status=status.HTTP_200_OK)
    except Exception as e:
        return Response(
            {"error": f"Error retrieving user data: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

#Crear usuario
@api_view(['POST'])
@permission_classes([IsAuthenticated, RolePermission(['admin'])])
def create_user(request):
    try:
        username    = request.data.get('username')
        password    = request.data.get('password')
        email       = request.data.get('email', '')
        first_name  = request.data.get('first_name', '')
        last_name   = request.data.get('last_name', '')
        role        = request.data.get('role', 'admin')

        if not username or not password:
            return Response(
                {"error": "Username and password are required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if User.objects.filter(username=username).exists():
            return Response(
                {"error": "Username already exists."},
                status=status.HTTP_400_BAD_REQUEST
            )

        user = User.objects.create(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
            role=role,
            password=make_password(password)
        )

        data = {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role
        }
        return Response(data, status=status.HTTP_201_CREATED)

    except DatabaseError as e:
        return Response(
            {"error": f"Database error: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    except Exception as e:
        return Response(
            {"error": f"Unexpected error: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated, RolePermission(['admin'])])
def list_users(request):
    try:
        print("Rol del usuario:", request.user.role)

        # 1. Obtener todos los usuarios como un queryset
        users = User.objects.all()

        # 2. Aplicar FILTROS
        
        # --- Filtro de Buscador (Search) ---
        search_query = request.query_params.get('search', None)
        if search_query:
            # Filtra por username, email, first_name o last_name
            # usando la búsqueda 'icontains' (case-insensitive containment)
            users = users.filter(
                Q(username__icontains=search_query) |
                Q(email__icontains=search_query) |
                Q(first_name__icontains=search_query) |
                Q(last_name__icontains=search_query)
            )

        # --- Filtros de Fecha de Inicio y Fecha de Fin (Date Range) ---
        start_date_str = request.query_params.get('start_date', None)
        end_date_str = request.query_params.get('end_date', None)

        if start_date_str:
            try:
                # Convertir la cadena a objeto datetime.date
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                # Filtra usuarios cuya fecha de unión sea mayor o igual a la fecha de inicio
                users = users.filter(date_joined__gte=start_date)
            except ValueError:
                # Manejar el error si el formato de fecha es incorrecto
                return Response(
                    {"error": "El formato de la fecha de inicio debe ser YYYY-MM-DD."},
                    status=status.HTTP_400_BAD_REQUEST
                )

        if end_date_str:
            try:
                # Convertir la cadena a objeto datetime.date
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
                # Filtra usuarios cuya fecha de unión sea menor o igual a la fecha de fin
                users = users.filter(date_joined__lte=end_date)
            except ValueError:
                # Manejar el error si el formato de fecha es incorrecto
                return Response(
                    {"error": "El formato de la fecha de fin debe ser YYYY-MM-DD."},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
        # 3. Seleccionar los campos a devolver (values) y Ordenar
        # Se ordena por 'id' para asegurar un orden consistente antes de paginar
        users = users.order_by('id').values(
            'id', 'username', 'email', 'first_name', 'last_name', 'role', 'is_active', 'date_joined' # Agregué 'date_joined' para que se pueda ver la fecha
        )

        # 4. Aplicar paginación manualmente
        paginator = PageNumberPagination()
        paginator.page_size = 5  # puedes ajustar o leer desde settings
        paginated_users = paginator.paginate_queryset(users, request)

        return paginator.get_paginated_response(paginated_users)

    except Exception as e:
        return Response(
            {"error": f"Error fetching users: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    except Exception as e:
        return Response(
            {"error": f"Error fetching users: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

# Obtener un usuario por ID (admin o contador)
@api_view(['GET'])
@permission_classes([IsAuthenticated, RolePermission(['admin'])])
def get_user(request, pk):
    try:
        user = get_object_or_404(User, pk=pk)
        data = {
            "id": user.id,
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "email": user.email,
            "role": user.role,
            "is_active": user.is_active,
        }
        return Response(data, status=status.HTTP_200_OK)
    except Exception as e:
        return Response(
            {"error": f"Error retrieving user: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

# Actualizar usuario (solo admin)
@api_view(['PUT'])
@permission_classes([IsAuthenticated, RolePermission(['admin'])])
def update_user(request, pk):
    try:
        user = get_object_or_404(User, pk=pk)
        user.username = request.data.get('username', user.username)
        user.first_name = request.data.get('first_name', user.first_name)
        user.last_name = request.data.get('last_name', user.last_name)
        user.email = request.data.get('email', user.email)
        user.role = request.data.get('role', user.role)
        password = request.data.get('password')

        if password:
            user.password = make_password(password)

        user.save()

        data = {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role,
        }
        return Response(data, status=status.HTTP_200_OK)

    except DatabaseError as e:
        return Response(
            {"error": f"Database error while updating user: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    except Exception as e:
        return Response(
            {"error": f"Unexpected error: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# Eliminar usuario (solo admin)
@api_view(['DELETE'])
@permission_classes([IsAuthenticated, RolePermission(['admin'])])
def delete_user(request, pk):
    try:
        user = get_object_or_404(User, pk=pk)
        user.delete()
        return Response(
            {"message": "User deleted successfully"},
            status=status.HTTP_204_NO_CONTENT
        )
    except Exception as e:
        return Response(
            {"error": f"Error deleting user: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
