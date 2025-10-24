from django.db import models
from user.models import User # Asumiendo que tu modelo de usuario está aquí
from user.base.models import BaseModel

class Cliente(BaseModel):
    # Información básica del cliente
    nombre   = models.CharField(max_length=100)
    apellido = models.CharField(max_length=100,  blank=True, null=True)
    email    = models.EmailField(max_length=100, unique=True, blank=True, null=True)
    telefono = models.CharField(max_length=20,   blank=True, null=True)
    
    # Información de dirección
    direccion = models.CharField(max_length=255, blank=True, null=True)
    telefono  = models.CharField(max_length=100, blank=True, null=True)
 
    # Campo de relación: Quién creó este cliente
    creado_por = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, # Si el usuario que lo creó es eliminado, el campo se pone a NULL
        null=True, 
        related_name='clientes_creados'
    )

    class Meta:
        verbose_name        = "Cliente"
        verbose_name_plural = "Clientes"
        db_table            = "clientes"

    def __str__(self):
        return f"{self.nombre} {self.apellido if self.apellido else ''}"