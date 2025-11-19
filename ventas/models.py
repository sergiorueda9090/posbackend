from django.db import models
from decimal import Decimal
from user.models import User
from user.base.models import BaseModel
from productos.models import Producto
from clientes.models import Cliente  # si manejas clientes registrados


class Venta(BaseModel):
    """
    Modelo que representa una venta o factura generada.
    Contiene la información general de la transacción.
    """

    METODOS_PAGO = [
        ('Efectivo', 'Efectivo'),
        ('Tarjeta', 'Tarjeta'),
        ('Transferencia', 'Transferencia'),
        ('Otro', 'Otro'),
    ]

    codigo = models.CharField(
        max_length=50,
        unique=True,
        verbose_name="Código de Venta"
    )
    
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ventas",
        verbose_name="Cliente"
    )

    metodo_pago = models.CharField(
        max_length=20,
        choices=METODOS_PAGO,
        default='Efectivo',
        verbose_name="Método de Pago"
    )

    subtotal = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Subtotal"
    )

    descuento = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Descuento Total"
    )

    impuesto = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Impuesto Total"
    )

    total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Total a Pagar"
    )

    recibido = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Monto Recibido"
    )

    cambio = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Cambio"
    )

    creado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="ventas_creadas",
        verbose_name="Creado por"
    )

    class Meta:
        verbose_name = "Venta"
        verbose_name_plural = "Ventas"
        db_table = "ventas"
        ordering = ['-created_at']

    def __str__(self):
        return f"Venta #{self.codigo}"


class DetalleVenta(BaseModel):
    """
        Modelo para registrar los productos incluidos en una venta.
        Relación N a 1 con Venta y Producto.
    """

    venta = models.ForeignKey(
        Venta,
        on_delete=models.CASCADE,
        related_name="detalles",
        verbose_name="Venta"
    )

    producto = models.ForeignKey(
        Producto,
        on_delete=models.PROTECT,
        related_name="ventas_detalle",
        verbose_name="Producto"
    )

    cantidad = models.PositiveIntegerField(
        default=1,
        verbose_name="Cantidad"
    )

    precio_unitario = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="Precio Unitario"
    )


    class Meta:
        verbose_name = "Detalle de Venta"
        verbose_name_plural = "Detalles de Ventas"
        db_table = "detalle_ventas"
        ordering = ['venta']

    def __str__(self):
        return f"{self.producto.nombre} x {self.cantidad}"
    
