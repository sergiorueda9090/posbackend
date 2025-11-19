from django.urls import path
from . import views

urlpatterns = [
    path('create/',                     views.create_inventario,    name='create_inventario'), 
    path('list/',                       views.list_inventarios,     name='list_inventarios'), 
    path('<int:pk>/',                   views.get_inventario,       name='get_inventario'), 
    path('<int:pk>/update/',            views.update_inventario,    name='update_inventario'),
    path('<int:pk>/delete/',            views.delete_inventario,    name='delete_inventario'),
    path('<int:producto_id>/total/',    views.get_total_unidades_producto, name='get_total_unidades_producto'),
    path('<int:producto_id>/cantidad/', views.get_inventario_by_producto, name='get_inventario_by_producto'),
]

