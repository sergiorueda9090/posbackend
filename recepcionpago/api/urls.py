# recepcion_pago/urls.py
from django.urls import path
from . import views

urlpatterns = [
    # Crear y Listar
    path('create/',          views.create_recepcion_pago, name='create_recepcion_pago'), 
    path('list/',            views.list_recepciones_pago, name='list_recepciones_pago'), 
    path('<int:pk>/',        views.get_recepcion_pago,    name='get_recepcion_pago'), 
    path('<int:pk>/update/', views.update_recepcion_pago, name='update_recepcion_pago'),
    path('<int:pk>/delete/', views.delete_recepcion_pago, name='delete_recepcion_pago'),
]