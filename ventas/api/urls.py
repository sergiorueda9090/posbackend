from django.urls import path
from . import views

urlpatterns = [
    path('create/',          views.create_venta,        name='create_venta'),
    path('list/',            views.list_ventas,         name='list_ventas'),
    path('<int:pk>/',        views.get_venta,           name='get_venta'),
    path('<int:pk>/delete/', views.delete_venta,        name='delete_venta'),
    path('resumen/',         views.resumen_ventas_view, name='resumen_ventas'),
    path('reporte/',         views.reporte_ventas,      name='reporte_ventas'),
    path('get-siguiente-codigo-venta-v2/', views.get_siguiente_codigo_venta_v2, name='get_siguiente_codigo_venta_v2'),
]