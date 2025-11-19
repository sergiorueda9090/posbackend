# recepcion_pago/views.py
from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from django.shortcuts import get_object_or_404
from django.db import DatabaseError, IntegrityError

from user.api.permissions import RolePermission 
from recepcionpago.models import RecepcionPago
from clientes.models import Cliente
from tarjetabancaria.models import TarjetaBancaria

from django.db.models import Q 
from decimal import Decimal, InvalidOperation # Importar para manejo de valor

from django.db.models import Sum
from datetime import datetime, time

# Roles permitidos para gestionar recepciones de pago
PAYMENT_MANAGER_ROLES = ['admin', 'manager'] # Se añaden managers por ejemplo

# --- Ayudante de Serialización ---
def serialize_pago(pago: RecepcionPago):
    """Serializa un objeto RecepcionPago con formato de moneda COP."""
    
    # --- Formatear el valor como moneda colombiana ---
    try:
        # Ejemplo: $1.250.000,00
        valor_cop = "${:,.2f}".format(pago.valor).replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        valor_cop = f"${pago.valor}"  # fallback simple si falla el formato

    return {
        'id'                 : pago.id,
        'valor'              : pago.valor,  # <-- valor formateado en COP
        'descripcion'        : pago.descripcion,
        'fecha_transaccion'  : pago.fecha_transaccion,
        'cliente_id'         : pago.cliente_id,
        'cliente_nombre'     : pago.cliente.nombre,
        'tarjeta_id'         : pago.tarjeta_id,
        'tarjeta_pan'        : f"**** {pago.tarjeta.pan[-4:]}" if pago.tarjeta.pan else None,
        'creado_por_username': pago.creado_por.username if pago.creado_por else None,
        'created_at'         : pago.created_at,
        'updated_at'         : pago.updated_at,
    }


## 1. Crear Recepción de Pago (POST)
@api_view(['POST'])
@permission_classes([IsAuthenticated, RolePermission(PAYMENT_MANAGER_ROLES)])
def create_recepcion_pago(request):
    try:
        cliente_id   = request.data.get('cliente_id')
        tarjeta_id   = request.data.get('tarjeta_id')
        valor_str    = request.data.get('valor')
        descripcion  = request.data.get('descripcion', '')

        # 1. Validaciones de entrada
        if not all([cliente_id, tarjeta_id, valor_str]):
            return Response(
                {"error": "Los campos 'cliente_id', 'tarjeta_id' y 'valor' son obligatorios."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            valor = Decimal(valor_str)
            if valor <= 0:
                raise InvalidOperation
        except InvalidOperation:
            return Response(
                {"error": "El valor de la transacción debe ser un número positivo válido."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 2. Verificar existencia de Cliente y Tarjeta (solo activos)
        cliente = get_object_or_404(Cliente, pk=cliente_id)
        tarjeta = get_object_or_404(TarjetaBancaria, pk=tarjeta_id)

        # 3. Creación del objeto
        pago = RecepcionPago.objects.create(
            cliente     = cliente,
            tarjeta     = tarjeta,
            valor       = valor,
            descripcion = descripcion,
            creado_por  = request.user
        )

        return Response(serialize_pago(pago), status=status.HTTP_201_CREATED)

    except Exception as e:
        return Response(
            {"error": f"Error inesperado al registrar el pago: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


## 2. Listar Recepciones de Pago (GET)
@api_view(['GET'])
@permission_classes([IsAuthenticated, RolePermission(PAYMENT_MANAGER_ROLES)])
def list_recepciones_pago(request):
    try:
        # Optimización: Cargar relaciones en una sola consulta
        pagos = RecepcionPago.objects.select_related('cliente', 'tarjeta', 'creado_por').all()
        
        # --- 1. Obtener parámetros de filtros de fecha y otros ---
        search_query    = request.query_params.get('search',     None)
        cliente_id      = request.query_params.get('cliente_id', None)
        start_date_str  = request.query_params.get('start_date', None) # Nuevo
        end_date_str    = request.query_params.get('end_date',   None)   # Nuevo
        
        # Variables para almacenar las fechas de filtro procesadas
        fecha_inicio = None
        fecha_fin    = None

        # --- 2. Aplicar Filtros de Búsqueda (Texto y Cliente) ---
        if search_query:
            # Búsqueda por descripción, nombre de cliente o nombre de tarjeta
            pagos = pagos.filter(
                Q(descripcion__icontains=search_query) |
                Q(cliente__nombre__icontains=search_query) |
                Q(tarjeta__nombre__icontains=search_query)
            )
        
        if cliente_id:
            pagos = pagos.filter(cliente_id=cliente_id)

        # --- 3. Aplicar Filtros de Fecha (Rango) ---
        if start_date_str:
            try:
                # Convertir la cadena a objeto datetime.date
                fecha_inicio = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                # Incluye todo el día, desde 00:00:00
                start_datetime = datetime.combine(fecha_inicio, time.min)
                pagos = pagos.filter(fecha_transaccion__gte=start_datetime)
            except ValueError:
                return Response(
                    {"error": "El formato de la fecha de inicio debe ser YYYY-MM-DD."},
                    status=status.HTTP_400_BAD_REQUEST
                )

        if end_date_str:
            try:
                # Convertir la cadena a objeto datetime.date
                fecha_fin = datetime.strptime(end_date_str, '%Y-%m-%d').date()
                # Incluye todo el día hasta 23:59:59.999999
                end_datetime = datetime.combine(fecha_fin, time.max)
                pagos = pagos.filter(fecha_transaccion__lte=end_datetime)
            except ValueError:
                return Response(
                    {"error": "El formato de la fecha de fin debe ser YYYY-MM-DD."},
                    status=status.HTTP_400_BAD_REQUEST
                )

        # --- 4. Paginación ---
        paginator = PageNumberPagination()
        paginator.page_size = 15 # Más ítems por ser transacciones
        # La paginación se aplica al queryset *filtrado*
        paginated_pagos = paginator.paginate_queryset(pagos, request)

        # --- 5. Serialización ---
        data = [serialize_pago(p) for p in paginated_pagos]

        # --- 6. Calcular total general (usando el mismo queryset *filtrado*) ---
        # Calculamos el total con los mismos filtros aplicados al queryset 'pagos'
        total = pagos.aggregate(total_valor=Sum('valor'))['total_valor'] or 0
        total_cop = "${:,.2f}".format(total).replace(",", "X").replace(".", ",").replace("X", ".")
        return paginator.get_paginated_response(data)
        
        return paginator.get_paginated_response({
            "results"   : data,
            "total"     : total_cop,
            "filtros_aplicados": { # Cambiado a 'filtros_aplicados' para evitar confusión
                "search"    : search_query,
                "cliente_id": cliente_id,
                "start_date": start_date_str, 
                "end_date"  : end_date_str,
            }
        })

    except Exception as e:
        # Se puede añadir logging aquí para depuración
        print(f"Error en list_recepciones_pago: {e}") 
        return Response(
            {"error": f"Error al obtener la lista de pagos: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    
## 3. Obtener Recepción de Pago por ID (GET)
@api_view(['GET'])
@permission_classes([IsAuthenticated, RolePermission(PAYMENT_MANAGER_ROLES)])
def get_recepcion_pago(request, pk):
    # Solo busca pagos NO eliminados (Soft Delete)
    pago = get_object_or_404(
        RecepcionPago.objects.select_related('cliente', 'tarjeta', 'creado_por'), 
        pk=pk
    )
    
    return Response(serialize_pago(pago), status=status.HTTP_200_OK)


## 4. Actualizar Recepción de Pago (PUT/PATCH)
@api_view(['PUT', 'PATCH'])
@permission_classes([IsAuthenticated, RolePermission(PAYMENT_MANAGER_ROLES)])
def update_recepcion_pago(request, pk):
    try:
        # Solo permite actualizar pagos NO eliminados
        pago = get_object_or_404(RecepcionPago, pk=pk)
        
        valor_str   = request.data.get('valor')
        descripcion = request.data.get('descripcion', pago.descripcion)
        cliente_id  = request.data.get('cliente_id', pago.cliente_id)
        tarjeta_id  = request.data.get('tarjeta_id', pago.tarjeta_id)
        
        # Validación y asignación de valor
        if valor_str:
            try:
                pago.valor = Decimal(valor_str)
                if pago.valor <= 0:
                    raise InvalidOperation
            except InvalidOperation:
                return Response(
                    {"error": "El valor de la transacción debe ser un número positivo válido."},
                    status=status.HTTP_400_BAD_REQUEST
                )

        # Asignación de Cliente
        if cliente_id != pago.cliente_id:
            pago.cliente = get_object_or_404(Cliente, pk=cliente_id)

        # Asignación de Tarjeta
        if tarjeta_id != pago.tarjeta_id:
            pago.tarjeta = get_object_or_404(TarjetaBancaria, pk=tarjeta_id)

        pago.descripcion = descripcion
        pago.save()

        # Recargar para serializar las relaciones actualizadas
        pago_updated = RecepcionPago.objects.select_related('cliente', 'tarjeta', 'creado_por').get(pk=pk)

        return Response(serialize_pago(pago_updated), status=status.HTTP_200_OK)

    except Exception as e:
        return Response(
            {"error": f"Error inesperado al actualizar el pago: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


## 5. Eliminar Recepción de Pago (DELETE) - Eliminación Lógica
@api_view(['DELETE'])
@permission_classes([IsAuthenticated, RolePermission(PAYMENT_MANAGER_ROLES)])
def delete_recepcion_pago(request, pk):
    try:
        # Solo busca pagos NO eliminados
        pago = get_object_or_404(RecepcionPago, pk=pk)
        
        # Ejecuta el soft delete (establece deleted_at)
        pago.delete()
        
        return Response(
            {"message": "Recepción de Pago eliminada lógicamente exitosamente", "deleted_at": pago.deleted_at}, 
            status=status.HTTP_200_OK
        )
    except Exception as e:
        return Response(
            {"error": f"Error al ejecutar la eliminación lógica del pago: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    

def get_total_recepciones_pago(fechaInicio=None, fechaFin=None):
    """
        Devuelve el total general de todos los pagos registrados.
        Se puede filtrar opcionalmente por un rango de fechas (fechaInicio, fechaFin).
    """
    try:
        # --- Obtener parámetros opcionales ---
        fecha_inicio = fechaInicio
        fecha_fin    = fechaFin

        # --- Base Query ---
        pagos = RecepcionPago.objects.all()

        # --- Aplicar filtro por rango de fechas (si se pasan) ---
        if fecha_inicio:
            fecha_inicio = datetime.strptime(fecha_inicio, "%Y-%m-%d")
            pagos = pagos.filter(fecha_transaccion__date__gte=fecha_inicio)

        if fecha_fin:
            fecha_fin = datetime.strptime(fecha_fin, "%Y-%m-%d")
            pagos = pagos.filter(fecha_transaccion__date__lte=fecha_fin)

        # --- Calcular suma total ---
        total = pagos.aggregate(total_valor=Sum('valor'))['total_valor'] or 0

        # --- Formatear como moneda colombiana ---
        total_cop = "${:,.2f}".format(total).replace(",", "X").replace(".", ",").replace("X", ".")

        # --- Respuesta ---
        return {
            "total": total_cop,
            "filtros": {
                "fechaInicio": fecha_inicio.strftime("%Y-%m-%d") if fecha_inicio else None,
                "fechaFin": fecha_fin.strftime("%Y-%m-%d") if fecha_fin else None
            }
        }

    except Exception as e:
        return {
            "total": 0,
            "filtros": {
                "fechaInicio": fecha_inicio.strftime("%Y-%m-%d") if fecha_inicio else None,
                "fechaFin": fecha_fin.strftime("%Y-%m-%d") if fecha_fin else None
            }
        }