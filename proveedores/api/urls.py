# proveedor/urls.py
from django.urls import path
from . import views

urlpatterns = [
    # Crear y Listar
    path('create/',             views.create_supplier,  name='create_supplier'), 
    path('list/',               views.list_suppliers,   name='list_suppliers'), 
    path('<int:pk>/',           views.get_supplier,     name='get_supplier'), 
    path('<int:pk>/update/',    views.update_supplier,  name='update_supplier'),
    path('<int:pk>/delete/',    views.delete_supplier,  name='delete_supplier'),
]