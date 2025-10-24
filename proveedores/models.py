# proveedor/models.py
from django.db import models
from user.models import User 
from user.base.models import BaseModel # Importa tu modelo base

class Proveedor(BaseModel):
    """
    Modelo para almacenar información de los proveedores.
    Hereda de BaseModel para trazabilidad y eliminación lógica.
    """
    # Información básica del proveedor
    nombre_empresa     = models.CharField(max_length=150, unique=True, verbose_name="Nombre de la Empresa")
    contacto_principal = models.CharField(max_length=100, blank=True, null=True)
    ruc                 = models.CharField(max_length=20, unique=True, blank=True, null=True, verbose_name="RUC / Tax ID")
    
    # Contacto
    email    = models.EmailField(max_length=100, unique=True, blank=True, null=True)
    telefono = models.CharField(max_length=20, blank=True, null=True)
    
    # Dirección
    direccion = models.CharField(max_length=255, blank=True, null=True)
    ciudad    = models.CharField(max_length=100, blank=True, null=True)

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