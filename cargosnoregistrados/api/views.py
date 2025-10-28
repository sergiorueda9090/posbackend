from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from django.shortcuts import get_object_or_404
from django.db.models import Q, Sum
from decimal import Decimal
from datetime import datetime, time

# Modelos
from user.api.permissions import RolePermission
from clientes.models import Cliente
from tarjetabancaria.models import TarjetaBancaria
from cargosnoregistrados.models import CargosNoRegistrados

# Roles permitidos
CARGOS_MANAGER_ROLES = ['admin', 'manager', 'contador']


# --- Serializador manual ---
def serialize_cargo(cargo: CargosNoRegistrados):
    """Serializa un objeto de CargosNoRegistrados."""
    return {
        'id': cargo.id,
        'descripcion': cargo.descripcion,
        'fecha_transaccion': cargo.fecha_transaccion,
        'cliente_id': cargo.cliente_id,
        'cliente_nombre': cargo.cliente.nombre if cargo.cliente else None,
        'tarjeta_id': cargo.tarjeta_id,
        'tarjeta_nombre': cargo.tarjeta.nombre if cargo.tarjeta else None,
        'creado_por_username': cargo.creado_por.username if cargo.creado_por else None,
        'created_at': cargo.created_at,
        'updated_at': cargo.updated_at,
        'deleted_at': cargo.deleted_at,
    }


# 1️⃣ Crear Cargo No Registrado
@api_view(['POST'])
@permission_classes([IsAuthenticated, RolePermission(CARGOS_MANAGER_ROLES)])
def create_cargo(request):
    cliente_id = request.data.get('cliente_id', None)
    tarjeta_id = request.data.get('tarjeta_id')
    descripcion = request.data.get('descripcion', '')

    if not tarjeta_id:
        return Response(
            {"error": "El campo 'tarjeta_id' es obligatorio."},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        tarjeta = get_object_or_404(TarjetaBancaria, pk=tarjeta_id)
        cliente = None
        if cliente_id:
            cliente = get_object_or_404(Cliente, pk=cliente_id)

        cargo = CargosNoRegistrados.objects.create(
            cliente=cliente,
            tarjeta=tarjeta,
            descripcion=descripcion,
            creado_por=request.user
        )

        cargo_created = CargosNoRegistrados.objects.select_related(
            'cliente', 'tarjeta', 'creado_por'
        ).get(pk=cargo.pk)

        return Response(serialize_cargo(cargo_created), status=status.HTTP_201_CREATED)

    except Exception as e:
        return Response(
            {"error": f"Error al registrar el cargo: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# 2️⃣ Listar Cargos No Registrados
@api_view(['GET'])
@permission_classes([IsAuthenticated, RolePermission(CARGOS_MANAGER_ROLES)])
def list_cargos(request):
    try:
        cargos = CargosNoRegistrados.objects.select_related('cliente', 'tarjeta', 'creado_por').filter(deleted_at__isnull=True)

        # --- Filtros ---
        search_query = request.query_params.get('search', None)
        cliente_id_filter = request.query_params.get('cliente_id', None)
        tarjeta_id_filter = request.query_params.get('tarjeta_id', None)
        start_date_str = request.query_params.get('start_date', None)
        end_date_str = request.query_params.get('end_date', None)

        # Búsqueda por texto
        if search_query:
            cargos = cargos.filter(
                Q(descripcion__icontains=search_query) |
                Q(cliente__nombre__icontains=search_query) |
                Q(tarjeta__nombre__icontains=search_query)
            )

        # Filtro por cliente
        if cliente_id_filter:
            cargos = cargos.filter(cliente_id=cliente_id_filter)

        # Filtro por tarjeta
        if tarjeta_id_filter:
            cargos = cargos.filter(tarjeta_id=tarjeta_id_filter)

        # Filtros por fecha
        if start_date_str:
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                cargos = cargos.filter(fecha_transaccion__gte=datetime.combine(start_date, time.min))
            except ValueError:
                return Response({"error": "Formato de fecha inicio inválido (YYYY-MM-DD)."}, status=status.HTTP_400_BAD_REQUEST)

        if end_date_str:
            try:
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
                cargos = cargos.filter(fecha_transaccion__lte=datetime.combine(end_date, time.max))
            except ValueError:
                return Response({"error": "Formato de fecha fin inválido (YYYY-MM-DD)."}, status=status.HTTP_400_BAD_REQUEST)

        # Orden
        cargos = cargos.order_by('-fecha_transaccion')

        # Paginación
        paginator = PageNumberPagination()
        paginator.page_size = 15
        paginated_cargos = paginator.paginate_queryset(cargos, request)

        data = [serialize_cargo(c) for c in paginated_cargos]

        return paginator.get_paginated_response({
            "results": data,
            "filtros_aplicados": {
                "search": search_query,
                "cliente_id": cliente_id_filter,
                "tarjeta_id": tarjeta_id_filter,
                "start_date": start_date_str,
                "end_date": end_date_str,
            }
        })

    except Exception as e:
        print(f"Error en list_cargos: {e}")
        return Response(
            {"error": f"Error al obtener los cargos: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# 3️⃣ Obtener Detalle
@api_view(['GET'])
@permission_classes([IsAuthenticated, RolePermission(CARGOS_MANAGER_ROLES)])
def get_cargo(request, pk):
    cargo = get_object_or_404(
        CargosNoRegistrados.objects.select_related('cliente', 'tarjeta', 'creado_por').filter(deleted_at__isnull=True),
        pk=pk
    )
    return Response(serialize_cargo(cargo), status=status.HTTP_200_OK)


# 4️⃣ Actualizar Cargo
@api_view(['PUT', 'PATCH'])
@permission_classes([IsAuthenticated, RolePermission(CARGOS_MANAGER_ROLES)])
def update_cargo(request, pk):
    try:
        cargo = get_object_or_404(CargosNoRegistrados.objects.filter(deleted_at__isnull=True), pk=pk)

        descripcion = request.data.get('descripcion', cargo.descripcion)
        cliente_id = request.data.get('cliente_id', cargo.cliente_id)
        tarjeta_id = request.data.get('tarjeta_id', cargo.tarjeta_id)

        if cliente_id != cargo.cliente_id:
            cargo.cliente = get_object_or_404(Cliente, pk=cliente_id) if cliente_id else None

        if tarjeta_id != cargo.tarjeta_id:
            cargo.tarjeta = get_object_or_404(TarjetaBancaria, pk=tarjeta_id)

        cargo.descripcion = descripcion
        cargo.save()

        cargo_updated = CargosNoRegistrados.objects.select_related('cliente', 'tarjeta', 'creado_por').get(pk=pk)
        return Response(serialize_cargo(cargo_updated), status=status.HTTP_200_OK)

    except Exception as e:
        return Response(
            {"error": f"Error al actualizar el cargo: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# 5️⃣ Eliminar Lógicamente
@api_view(['DELETE'])
@permission_classes([IsAuthenticated, RolePermission(CARGOS_MANAGER_ROLES)])
def delete_cargo(request, pk):
    try:
        cargo = get_object_or_404(CargosNoRegistrados.objects.filter(deleted_at__isnull=True), pk=pk)
        cargo.delete()
        return Response(
            {"message": "Cargo eliminado lógicamente exitosamente", "deleted_at": cargo.deleted_at},
            status=status.HTTP_200_OK
        )
    except Exception as e:
        return Response(
            {"error": f"Error al eliminar el cargo: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


def get_total_cargos_no_registrados(cliente_id=None, tarjeta_id=None):
    """
    Calcula el total de cargos no registrados filtrando por cliente o por tarjeta.
    
    Parámetros:
        cliente_id (int | None): ID del cliente opcional.
        tarjeta_id (int | None): ID de la tarjeta opcional.
    
    Retorna:
        dict: {
            "total": Decimal,
            "total_cop": str
        }
    """
    # Base Query: sólo registros activos (no eliminados)
    cargos = CargosNoRegistrados.objects.filter(deleted_at__isnull=True)

    # Filtrar por cliente o tarjeta
    if cliente_id:
        cargos = cargos.filter(cliente_id=cliente_id)
    elif tarjeta_id:
        cargos = cargos.filter(tarjeta_id=tarjeta_id)

    # Calcular total
    total = cargos.aggregate(total_valor=Sum('tarjeta__transacciones__valor'))['total_valor'] or Decimal(0)

    # Formatear a COP
    total_cop = "${:,.2f}".format(total).replace(",", "X").replace(".", ",").replace("X", ".")

    return {
        "total"     : total,
        "total_cop" : total_cop
    }