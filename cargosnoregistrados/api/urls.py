from django.urls import path
from . import views

urlpatterns = [
    path('create/',             views.create_cargo,   name='create_cargo'),
    path('list/',               views.list_cargos,    name='list_cargos'),
    path('<int:pk>/',           views.get_cargo,      name='get_cargo'),
    path('<int:pk>/update/',    views.update_cargo,   name='update_cargo'),
    path('<int:pk>/delete/',    views.delete_cargo,   name='delete_cargo'),
]
