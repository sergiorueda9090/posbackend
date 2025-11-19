from django.urls import path
from . import views

urlpatterns = [
    # Crear y Listar
    path('create/',           views.create_devolucion,      name='create_devolucion'),
    path('list/',             views.list_devoluciones,      name='list_devoluciones'),

    # Obtener, Actualizar y Eliminar
    path('<int:pk>/',         views.get_devolucion,         name='get_devolucion'),
    path('<int:pk>/update/',  views.update_devolucion,      name='update_devolucion'),
]
