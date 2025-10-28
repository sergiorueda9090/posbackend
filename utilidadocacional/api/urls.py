# utilidadocacional/api/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('list/',               views.list_utilidades,  name='list-utilidades'),
    path('create/',             views.create_utilidad,  name='create-utilidad'),
    path('<int:pk>/',           views.get_utilidad,     name='get-utilidad'),
    path('<int:pk>/update/',    views.update_utilidad,  name='update-utilidad'),
    path('<int:pk>/delete/',    views.delete_utilidad,  name='delete-utilidad'),
]