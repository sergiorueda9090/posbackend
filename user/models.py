from django.db import models
from django.contrib.auth.models import AbstractUser

# Create your models here.

class Role(models.TextChoices):
    ADMIN = 'admin', 'Administrador'
    VENDEDOR = 'vendedor', 'Vendedor'
    CONTADOR = 'contador', 'Contador'
    CLIENTE = 'cliente', 'Cliente'

class User(AbstractUser):
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.CLIENTE
    )

    def __str__(self):
        return f"{self.username} ({self.role})"