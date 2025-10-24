# tarjeta/models.py
from django.db import models
from user.models import User
from user.base.models import BaseModel 
from django.core.validators import MinLengthValidator, MaxLengthValidator

class TarjetaBancaria(BaseModel):
    """
    Modelo simplificado para tarjetas bancarias.
    Hereda de BaseModel para trazabilidad y eliminación lógica.
    """
    # Información de la Tarjeta
    nombre      = models.CharField(max_length=100, verbose_name="Nombre de la Tarjeta")
    descripcion = models.TextField(blank=True, null=True, verbose_name="Descripción")
    
    pan = models.CharField( # Primary Account Number (Número de Tarjeta)
        max_length=20, 
        unique=True, 
        validators=[MinLengthValidator(8), MaxLengthValidator(20)],
        verbose_name="Numero de Tarjeta"
    )
    
    # Campo de relación: Quién creó esta tarjeta (usuario administrativo)
    creado_por = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='tarjetas_creadas'
    )
    
    class Meta:
        verbose_name        = "Tarjeta Bancaria"
        verbose_name_plural = "Tarjetas Bancarias"
        db_table            = "tarjetas_bancarias"

    def __str__(self):
        # Muestra el nombre y los últimos 4 dígitos del PAN
        return f"{self.nombre} (**** {self.pan[-4:]})"