# categoria/urls.py
from django.urls import path
from . import views

urlpatterns = [
    # Crear y Listar
    path('create/',             views.create_category,      name='create_category'), 
    path('list/',               views.list_categories,      name='list_categories'), 
    path('<int:pk>/',           views.get_category,         name='get_category'), 
    path('<int:pk>/update/',    views.update_category,      name='update_category'),
    path('<int:pk>/delete/',    views.delete_category,      name='delete_category'),
]