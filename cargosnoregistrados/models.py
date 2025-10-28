from django.db import models
from user.models import User
from user.base.models import BaseModel
from clientes.models import Cliente
from tarjetabancaria.models import TarjetaBancaria


class CargosNoRegistrados(BaseModel):
    """
    Modelo para registrar cargos no registrados asociados a una tarjeta,
    opcionalmente relacionados con un cliente.
    """

    # Cliente (opcional)
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cargos_noregistrados',
        verbose_name="Cliente (opcional)"
    )

    # Tarjeta (obligatorio)
    tarjeta = models.ForeignKey(
        TarjetaBancaria,
        on_delete=models.PROTECT,
        related_name='cargos_noregistrados',
        verbose_name="Tarjeta Bancaria"
    )

    # Descripción del cargo
    descripcion = models.TextField(
        blank=True,
        null=True,
        verbose_name="Descripción del Cargo"
    )

    # Fecha de la transacción
    fecha_transaccion = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de la Transacción"
    )

    # Usuario que creó el registro
    creado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='cargos_noregistrados_creados',
        verbose_name="Registrado por"
    )

    class Meta:
        verbose_name = "Cargo No Registrado"
        verbose_name_plural = "Cargos No Registrados"
        db_table = "cargosnoregistrados"
        ordering = ['-fecha_transaccion']

    def __str__(self):
        cliente_str = self.cliente.nombre if self.cliente else "Sin cliente"
        return f"Cargo no registrado ({cliente_str}) - {self.fecha_transaccion.strftime('%Y-%m-%d %H:%M')}"
