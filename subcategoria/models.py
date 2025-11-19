from django.db import models
from user.models import User
from user.base.models import BaseModel
from categoria.models import Categoria


class SubCategoria(BaseModel):
    """
        Modelo para almacenar subcategorías asociadas a una categoría principal.
        Incluye trazabilidad (BaseModel) y eliminación lógica.
    """
    categoria = models.ForeignKey(
        Categoria,
        on_delete=models.CASCADE,  # Si se elimina la categoría, se eliminan sus subcategorías
        related_name='subcategorias'
    )
    nombre = models.CharField(max_length=100, unique=True, verbose_name="Nombre de la Subcategoría")
    descripcion = models.TextField(blank=True, null=True, verbose_name="Descripción")
    creado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='subcategorias_creadas'
    )

    class Meta:
        verbose_name = "Subcategoría"
        verbose_name_plural = "Subcategorías"
        db_table = "subcategorias"
        ordering = ['nombre']

    def __str__(self):
        return f"{self.nombre} ({self.categoria.nombre})"
