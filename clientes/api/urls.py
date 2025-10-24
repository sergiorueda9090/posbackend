# client/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('create/',             views.create_client,    name='create_client'), 
    path('list/',               views.list_clients,     name='list_clients'), 
    path('<int:pk>/',           views.get_client,       name='get_client'), 
    path('<int:pk>/update/',    views.update_client,    name='update_client'),
    path('<int:pk>/delete/',    views.delete_client,    name='delete_client'),
]