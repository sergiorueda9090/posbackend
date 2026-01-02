from django.db import models
from user.models import User
from user.base.models import BaseModel
from productos.models import Producto
from decimal import Decimal


class Combo(BaseModel):
    """
    Modelo para gestionar combos de productos.
    Un combo agrupa varios productos con precios especiales.
    """
    nombre = models.CharField(
        max_length=200,
        unique=True,
        verbose_name="Nombre del Combo"
    )

    activo = models.BooleanField(
        default=True,
        verbose_name="Combo Activo"
    )

    creado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='combos_creados',
        verbose_name="Creado por"
    )

    class Meta:
        verbose_name = "Combo"
        verbose_name_plural = "Combos"
        db_table = "combos"
        ordering = ['-created_at']

    def __str__(self):
        return self.nombre

    @property
    def precio_total(self):
        """
        Calcula el precio total del combo sumando los precios especiales
        de todos los productos asociados multiplicados por su cantidad.
        """
        total = self.productos_combo.aggregate(
            total=models.Sum(
                models.F('precio_combo') * models.F('cantidad'),
                output_field=models.DecimalField()
            )
        )['total']
        return total or Decimal('0.00')


class ProductoCombo(BaseModel):
    """
    Modelo intermedio que relaciona Productos con Combos.
    Permite definir precio especial y cantidad para cada producto en el combo.
    """
    combo = models.ForeignKey(
        Combo,
        on_delete=models.CASCADE,
        related_name='productos_combo',
        verbose_name="Combo"
    )

    producto = models.ForeignKey(
        Producto,
        on_delete=models.PROTECT,
        related_name='combos',
        verbose_name="Producto"
    )

    precio_combo = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="Precio Especial en Combo"
    )

    cantidad = models.PositiveIntegerField(
        default=1,
        verbose_name="Cantidad del Producto en Combo"
    )

    class Meta:
        verbose_name = "Producto en Combo"
        verbose_name_plural = "Productos en Combos"
        db_table = "producto_combo"
        ordering = ['combo', 'producto']
        unique_together = ['combo', 'producto']

    def __str__(self):
        return f"{self.producto.nombre} en {self.combo.nombre}"
