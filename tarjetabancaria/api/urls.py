# tarjeta/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('create/',             views.create_card,  name='create_card'), 
    path('list/',               views.list_cards,   name='list_cards'), 
    path('<int:pk>/',           views.get_card,     name='get_card'), 
    path('<int:pk>/update/',    views.update_card,  name='update_card'),
    path('<int:pk>/delete/',    views.delete_card,  name='delete_card'),
]