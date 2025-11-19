from django.db import models
from user.models import User
from user.base.models import BaseModel
from categoria.models import Categoria
from subcategoria.models import SubCategoria
import uuid
import os
from decimal import Decimal

def upload_to_unique(instance, filename):
    ext = filename.split('.')[-1]
    filename = f"{uuid.uuid4()}.{ext}"
    return os.path.join('productos', filename)

class Producto(BaseModel):
    """
        Modelo para gestionar los productos disponibles en el sistema.
        Incluye trazabilidad, relación con categorías y manejo de imagen en S3.
    """

    categoria = models.ForeignKey(
        Categoria,
        on_delete=models.SET_NULL,
        null=True,
        related_name='productos'
    )
    subcategoria = models.ForeignKey(
        SubCategoria,
        on_delete=models.SET_NULL,
        null=True,
        related_name='productos'
    )
    nombre = models.CharField(max_length=200, unique=True, verbose_name="Nombre del Producto")
    descripcion = models.TextField(blank=True, null=True, verbose_name="Descripción")
    precio_compra = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Precio de compra")
    porcentaje_ganancia = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="Porcentaje de ganancia (%)")
    precio_final    = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Precio de venta final")
    codigo_busqueda = models.CharField(max_length=100, unique=True, verbose_name="Código de búsqueda")
    imagen          = models.ImageField(upload_to=upload_to_unique, blank=True, null=True)
    creado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='productos_creados'
    )

    class Meta:
        verbose_name = "Producto"
        verbose_name_plural = "Productos"
        db_table = "productos"
        ordering = ['nombre']

    def __str__(self):
        return self.nombre

    def calcular_precio_final(self):
        """
        Calcula automáticamente el precio final según el porcentaje de ganancia.
        """
        precio = Decimal(self.precio_compra)
        ganancia = Decimal(self.porcentaje_ganancia)
        self.precio_final = precio + (precio * ganancia / Decimal(100))
