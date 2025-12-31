# proveedor/models.py
from django.db import models
from user.models import User 
from user.base.models import BaseModel # Importa tu modelo base
from tarjetabancaria.models import TarjetaBancaria
from django.core.validators import MinValueValidator
from decimal import Decimal

class Proveedor(BaseModel):
    """
    Modelo para almacenar información de los proveedores.
    Hereda de BaseModel para trazabilidad y eliminación lógica.
    """
    # Información básica del proveedor
    nombre_empresa      = models.CharField(max_length=150, unique=True, verbose_name="Nombre de la Empresa")
    contacto_principal  = models.CharField(max_length=100, blank=True, null=True)
    ruc                 = models.CharField(max_length=20, unique=True, blank=True, null=True, verbose_name="RUC / Tax ID")
    
    # Contacto
    email    = models.EmailField(max_length=100, unique=True, blank=True, null=True)
    telefono = models.CharField(max_length=20, blank=True, null=True)
    
    # Dirección
    direccion = models.CharField(max_length=255, blank=True, null=True)
    ciudad    = models.CharField(max_length=100, blank=True, null=True)

    descripcion = models.TextField(blank=True, null=True, verbose_name="Descripción", default="")
    # Campo de relación: Quién creó este proveedor
    creado_por = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='proveedores_creados'
    )
    
    class Meta:
        verbose_name = "Proveedor"
        verbose_name_plural = "Proveedores"
        db_table = "proveedores"

    def __str__(self):
        return self.nombre_empresa
    
class OrdenProveedor(BaseModel):
    """
    Modelo para la orden de compra al proveedor (cabecera).
    """
    proveedor = models.ForeignKey(
        Proveedor,
        on_delete=models.PROTECT,
        related_name='ordenes',
        verbose_name="Proveedor"
    )

    tarjeta = models.ForeignKey(
        TarjetaBancaria,
        on_delete=models.SET_NULL,
        null=True,
        related_name='ordenes_proveedor',
        verbose_name="Tarjeta Bancaria",
        default=None
    )
    
    numero_orden = models.CharField(
        max_length=50,
        unique=True,
        verbose_name="Número de Orden",
        help_text="Número único de la orden de compra"
    )
    
    fecha_orden = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de Orden"
    )
    
    """
    value	     Label Frontend	   Label Django
    pendiente	 En Cotización	   En Cotización
    confirmada	 Pagada	           Pagada
    en_transito	 En Tránsito	   En Tránsito
    recibida	 Inventariada	   Inventariada
    """

    ESTADO_CHOICES = [
        ('pendiente', 'En Cotización'),
        ('confirmada', 'Pagada'),
        ('en_transito', 'En Tránsito'),
        ('recibida', 'Inventariada'),
    ]
    
    estado = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default='pendiente',
        verbose_name="Estado",
        db_index=True
    )
    
    total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0.00,
        verbose_name="Total de la Orden",
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    
    notas = models.TextField(
        blank=True,
        null=True,
        verbose_name="Notas / Observaciones"
    )
    
    creado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='ordenes_proveedor_creadas',
        verbose_name="Creado por"
    )
    
    class Meta:
        verbose_name = "Orden de Proveedor"
        verbose_name_plural = "Órdenes de Proveedor"
        db_table = "ordenes_proveedor"
        ordering = ['-fecha_orden']
        indexes = [
            models.Index(fields=['proveedor', 'estado']),
            models.Index(fields=['numero_orden']),
            models.Index(fields=['fecha_orden']),
        ]
    
    def __str__(self):
        return f"Orden {self.numero_orden} - {self.proveedor.nombre_empresa}"
    
    # 🔥 AGREGAR ESTE MÉTODO
    def calcular_total(self):
        """Calcula el total sumando todos los detalles de la orden"""
        total = sum(
            detalle.precio_compra * detalle.cantidad 
            for detalle in self.detalles.all()
        )
        self.total = total
        self.save(update_fields=['total'])
        return total


class OrdenProveedorDetalle(BaseModel):
    """
    Modelo para el detalle de cada producto en la orden de compra.
    """
    orden_proveedor = models.ForeignKey(
        OrdenProveedor,
        on_delete=models.CASCADE,
        related_name='detalles',
        verbose_name="Orden de Proveedor"
    )
    
    proveedor = models.ForeignKey(
        Proveedor,
        on_delete=models.PROTECT,
        related_name='detalles_ordenes',
        verbose_name="Proveedor"
    )
    
    producto_id = models.IntegerField(
        verbose_name="ID del Producto",
        help_text="ID del producto desde el sistema de inventario",
        db_index=True
    )
    
    nombre = models.CharField(
        max_length=200,
        verbose_name="Nombre del Producto",
        help_text="Nombre del producto al momento de la compra"
    )
    
    precio_compra = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Precio de Compra Unitario",
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    
    cantidad = models.PositiveIntegerField(
        verbose_name="Cantidad",
        validators=[MinValueValidator(1)]
    )
    
    subtotal = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        editable=False,
        verbose_name="Subtotal",
        default=0.00
    )
    
    notas = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name="Notas del Producto"
    )
    
    class Meta:
        verbose_name = "Detalle de Orden"
        verbose_name_plural = "Detalles de Órdenes"
        db_table = "ordenes_proveedor_detalle"
        ordering = ['id']
        indexes = [
            models.Index(fields=['orden_proveedor', 'producto_id']),
            models.Index(fields=['proveedor']),
        ]
        unique_together = [['orden_proveedor', 'producto_id']]
    
    def __str__(self):
        return f"{self.nombre} - Cantidad: {self.cantidad}"
    
    def save(self, *args, **kwargs):
        """Calcula el subtotal automáticamente antes de guardar"""
        self.subtotal = self.precio_compra * self.cantidad
        super().save(*args, **kwargs)
        
        # Actualizar el total de la orden padre
        if self.orden_proveedor:
            self.orden_proveedor.calcular_total()
    
    def delete(self, *args, **kwargs):
        """Actualiza el total de la orden al eliminar un detalle"""
        orden = self.orden_proveedor
        super().delete(*args, **kwargs)
        if orden:
            orden.calcular_total()