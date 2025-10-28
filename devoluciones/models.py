# recepcion_pago/models.py
from django.db import models
from user.models import User
from user.base.models import BaseModel 
from clientes.models import Cliente          # Importar el modelo Cliente
from tarjetabancaria.models import TarjetaBancaria  # Importar el modelo TarjetaBancaria

class Devoluciones(BaseModel):
    """
        Modelo para registrar las devoluciones de pago.
        Hereda de BaseModel para trazabilidad y eliminación lógica.
    """
    
    # --- Relaciones ---
    
    # Relación con el Cliente que realiza el pago
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.PROTECT,  # No permitir eliminar al cliente si tiene pagos asociados
        related_name='pagos_recibidos',
        verbose_name="Cliente"
    )
    
    # Relación con la Tarjeta utilizada
    tarjeta = models.ForeignKey(
        TarjetaBancaria,
        on_delete=models.PROTECT,  # No permitir eliminar la tarjeta si tiene pagos asociados
        related_name='transacciones',
        verbose_name="Tarjeta Bancaria"
    )

    # --- Campos de la Transacción ---
    
    # Valor de la transacción
    valor = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        verbose_name="Valor de la Transacción"
    )
    
    # Descripción de la transacción
    descripcion = models.TextField(
        blank=True, 
        null=True,
        verbose_name="Descripción del Pago"
    )
    
    # Fecha y hora en que se registró la transacción (ya cubierta por created_at en BaseModel, pero se añade un campo explícito si se necesita una fecha/hora diferente a la de creación)
    fecha_transaccion = models.DateTimeField(
        auto_now_add=True, # Usamos auto_now_add para registrar el momento de la creación
        verbose_name="Fecha de la Transacción"
    )

    # Campo de relación: Quién registró este pago
    creado_por = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='pagos_registrados',
        verbose_name="Registrado por"
    )
    
    class Meta:
        verbose_name          = "Devolución de Pago"
        verbose_name_plural   = "Devoluciones de Pago"
        db_table              = "devoluciones"
        # Ordenación por defecto: más reciente primero
        ordering = ['-fecha_transaccion'] 

    def __str__(self):
        return f"Devolución de ${self.valor} por {self.cliente} ({self.fecha_transaccion.strftime('%Y-%m-%d %H:%M')})"