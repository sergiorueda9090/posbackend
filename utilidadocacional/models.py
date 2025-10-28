# utilidadocacional/models.py
from django.db import models
from user.models import User
from user.base.models import BaseModel 
from tarjetabancaria.models import TarjetaBancaria # Importamos TarjetaBancaria

class UtilidadOcasional(BaseModel):
    """
    Modelo para registrar ingresos o utilidades ocasionales.
    Hereda de BaseModel para trazabilidad y eliminación lógica.
    """
    
    # --- Relaciones ---
    
    # Relación con la Tarjeta asociada a este ingreso
    tarjeta = models.ForeignKey(
        TarjetaBancaria,
        on_delete=models.PROTECT,  # No permitir eliminar la tarjeta si tiene utilidades asociadas
        related_name='utilidades_generadas',
        verbose_name="Tarjeta Bancaria"
    )

    # --- Campos de la Transacción ---
    
    fecha_transaccion = models.DateTimeField(
        auto_now_add=True, 
        verbose_name="Fecha de la Utilidad"
    )

    valor = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        verbose_name="Valor de la Utilidad"
    )
    
    observacion = models.TextField(
        blank=True, 
        null=True,
        verbose_name="Observación de la Utilidad"
    )
    
    # Campo de relación: Quién registró esta utilidad
    creado_por = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='utilidades_registradas',
        verbose_name="Registrado por"
    )
    
    class Meta:
        db_table            = "utilidadocasional"
        verbose_name        = "Utilidad Ocasional"
        verbose_name_plural = "Utilidades Ocasionales"
        ordering = ["-fecha_transaccion"]

    def __str__(self):
        return f"Utilidad {self.id} - {self.tarjeta.nombre} - ${self.valor}"