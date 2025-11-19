# gasto/models.py
from django.db import models
from user.models import User
from user.base.models import BaseModel

class Gasto(BaseModel):
    """
        Modelo maestro para definir un tipo de gasto (ej. 'Viáticos', 'Alquiler', 'Marketing').
        Hereda de BaseModel para trazabilidad y eliminación lógica.
    """
    nombre      = models.CharField(max_length=150, unique=True, verbose_name="Nombre del Gasto")
    descripcion = models.TextField(blank=True, null=True, verbose_name="Descripción del Tipo de Gasto")
    
    # Campo de relación: Quién creó este tipo de gasto
    creado_por = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='tipos_gastos_creados'
    )
    
    class Meta:
        verbose_name        = "Gasto Maestro"
        verbose_name_plural = "Gastos Maestros"
        db_table            = "gastos_maestros"

    def __str__(self):
        return self.nombre


class RelacionarGasto(BaseModel):
    """
    Modelo para registrar una ocurrencia específica y detallada de un gasto.
    Es el registro transaccional del gasto.
    """
    # Relación: Apunta al Gasto maestro (ej. apunta a 'Viáticos')
    gasto = models.ForeignKey(
        Gasto,
        on_delete=models.SET_NULL, # Si el tipo de gasto maestro se elimina, este campo se pone a NULL
        null=True, 
        related_name='registros_relacionados',
        verbose_name="Tipo de Gasto (Maestro)"
    )

    # Detalle del Gasto
    total_gasto = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        verbose_name="Monto Total del Gasto"
    )
    
    descripcion = models.TextField(
        verbose_name="Descripción Específica del Gasto"
    )
    
    # Campo de relación: Quién creó este registro de gasto específico
    creado_por = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='registros_gastos_creados'
    )
    
    class Meta:
        verbose_name        = "Registro de Gasto"
        verbose_name_plural = "Registros de Gastos"
        db_table            = "registros_gastos"
        ordering            = ['-created_at']

    def __str__(self):
        return f"Registro: {self.gasto.nombre if self.gasto else 'N/A'} - Total: {self.total_gasto}"