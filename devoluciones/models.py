# recepcion_pago/models.py

from django.db import models
from user.base.models import BaseModel

class Devoluciones(BaseModel):
    """
    Modelo simple para registrar devoluciones de productos.
    Solo guarda:
    - código de venta
    - ID del producto
    - cantidad devuelta
    """

    codigo_venta = models.CharField(
        max_length=50,
        verbose_name="Código de la Venta"
    )

    producto_id = models.IntegerField(
        verbose_name="ID del Producto"
    )

    cantidad = models.PositiveIntegerField(
        verbose_name="Cantidad Devuelta"
    )

    class Meta:
        verbose_name = "Devolución"
        verbose_name_plural = "Devoluciones"
        db_table = "devoluciones"
        ordering = ['-created_at']  # BaseModel ya trae created_at

    def __str__(self):
        return f"Devolución: Venta {self.codigo_venta} - Producto {self.producto_id} - Cantidad {self.cantidad}"
