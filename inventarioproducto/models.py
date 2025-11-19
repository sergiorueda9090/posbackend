from django.db import models
from user.models import User
from user.base.models import BaseModel
from productos.models import Producto


class InventarioProducto(BaseModel):
    """
    Modelo para manejar el inventario de los productos.
    Guarda la cantidad disponible y las fechas de registro/actualización.
    """
    producto = models.ForeignKey(
        Producto,
        on_delete=models.CASCADE,
        related_name='inventarios'
    )
    cantidad_unidades   = models.PositiveIntegerField(default=0, verbose_name="Cantidad de unidades")
    fecha_ingreso       = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de ingreso")
    fecha_actualizacion = models.DateTimeField(auto_now=True, verbose_name="Última actualización")
    creado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='inventarios_creados'
    )

    class Meta:
        verbose_name = "Inventario de Producto"
        verbose_name_plural = "Inventarios de Productos"
        db_table = "inventario_productos"
        ordering = ['-fecha_actualizacion']

    def __str__(self):
        return f"Inventario de {self.producto.nombre} ({self.cantidad_unidades} unidades)"
