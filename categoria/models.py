# categoria/models.py
from django.db import models
from user.models import User # Asume que tu modelo de usuario está aquí
from user.base.models import BaseModel # Importa tu modelo base

class Categoria(BaseModel):
    """
        Modelo para almacenar categorías de productos o servicios.
        Hereda de BaseModel para trazabilidad y eliminación lógica.
    """
    # Información de la Categoría
    nombre      = models.CharField(max_length=100, unique=True, verbose_name="Nombre de la Categoría")
    descripcion = models.TextField(blank=True, null=True, verbose_name="Descripción")
    
    # Campo de relación: Quién creó esta categoría
    creado_por = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, # Si el usuario que lo creó es eliminado, el campo se pone a NULL
        null=True, 
        related_name='categorias_creadas'
    )
    
    class Meta:
        verbose_name        = "Categoria"
        verbose_name_plural = "Categorias"
        db_table            = "categorias" # Nombre de la tabla en la BD

    def __str__(self):
        return self.nombre