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

    # === ÓRDENES DE PROVEEDOR ===
    path('ordenes/siguiente-numero/',   views.get_siguiente_numero_orden,   name='get_siguiente_numero_orden'),
    path('ordenes/',                    views.list_ordenes_proveedor,       name='list_ordenes_proveedor'),
    path('ordenes/by-proveedor/',       views.list_proveedores_con_ordenes, name='list_ordenes_by_proveedor'),
    path('ordenes/<int:orden_id>/pdf/', views.descargar_orden_pdf,          name='descargar_orden_pdf'),
    path('ordenes/create/',             views.create_orden_proveedor,       name='create_orden_proveedor'),
    path('ordenes/<int:pk>/',           views.get_orden_proveedor,          name='get_orden_proveedor'),
    path('ordenes/<int:pk>/update/',    views.update_orden_proveedor,       name='update_orden_proveedor'),
    path('ordenes/<int:pk>/delete/',    views.delete_orden_proveedor,       name='delete_orden_proveedor'),
    
    # === DETALLES DE ORDEN ===
    path('ordenes/<int:orden_id>/detalles/', views.list_orden_detalles,     name='list_orden_detalles'),
    path('detalles/create/',                 views.create_orden_detalle,    name='create_orden_detalle'),
    path('detalles/<int:pk>/',               views.get_orden_detalle,       name='get_orden_detalle'),
    path('detalles/<int:pk>/update/',        views.update_orden_detalle,    name='update_orden_detalle'),
    path('detalles/<int:pk>/delete/',        views.delete_orden_detalle,    name='delete_orden_detalle'),

]