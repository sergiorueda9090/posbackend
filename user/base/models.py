# base/models.py
from django.db import models

# 1. Custom Manager para Excluir Registros Eliminados
class SoftDeleteManager(models.Manager):
    """Manager que devuelve solo los registros NO eliminados (deleted_at=NULL)."""
    def get_queryset(self):
        # Filtra para excluir cualquier registro que tenga un valor en deleted_at
        return super().get_queryset().filter(deleted_at__isnull=True)

# 2. Modelo Base Abstracto
class BaseModel(models.Model):
    """
    Clase abstracta base para implementar trazabilidad (created_at, updated_at)
    y eliminación lógica (deleted_at).
    """
    # Campos de Trazabilidad
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Creación")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Última Actualización")
    deleted_at = models.DateTimeField(null=True, blank=True, verbose_name="Fecha de Eliminación Lógica")

    # Managers
    objects = SoftDeleteManager() # Manager por defecto (solo registros activos)
    all_objects = models.Manager() # Manager para acceder a TODOS los registros (incluyendo eliminados)

    class Meta:
        abstract = True
        ordering = ['-created_at']

    # Método de eliminación lógica
    def delete(self, using=None, keep_parents=False):
        """Sobrescribe el método delete para establecer deleted_at en lugar de eliminar."""
        from django.utils import timezone
        self.deleted_at = timezone.now()
        self.save(update_fields=['deleted_at'])

    # Método para restaurar el registro
    def restore(self):
        """Restaura un registro eliminado lógicamente."""
        self.deleted_at = None
        self.save(update_fields=['deleted_at'])