# ajustessaldo/api/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('list/',               views.list_ajustes,     name='list-ajustes'),
    path('create/',             views.create_ajuste,    name='create-ajuste'),
    path('<int:pk>/',           views.get_ajuste,       name='get-ajuste'),
    path('<int:pk>/update/',    views.update_ajuste,    name='update-ajuste'),
    path('<int:pk>/delete/',    views.delete_ajuste,    name='delete-ajuste'),
]