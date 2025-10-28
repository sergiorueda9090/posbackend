from django.db import models
from user.models import User
from user.base.models import BaseModel 
from clientes.models import Cliente 


class AjusteSaldo(BaseModel):
    """
    Modelo para registrar ajustes manuales de saldo a clientes.
    """
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ajustes_saldo"
    )

    fecha_transaccion = models.DateTimeField(
        auto_now_add=True, # Usamos auto_now_add para registrar el momento de la creación
        verbose_name="Fecha ajuste de saldo"
    )

    valor = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        verbose_name="Valor del Ajuste de Saldo"
    )
    
    observacion = models.TextField(blank=True, null=True)
    
    creado_por = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='ajustes_creados',
        verbose_name="Registrado por"
    )

    class Meta:
        db_table            = "ajustesaldo"
        verbose_name        = "Ajuste de Saldo"
        verbose_name_plural = "Ajustes de Saldo"
        ordering = ["-fecha_transaccion"]

    def __str__(self):
        cliente_nombre = self.cliente.nombre if self.cliente else "Sin cliente"
        return f"Ajuste {self.id} - {cliente_nombre} - ${self.valor}"
