from django.urls import path
from . import views

urlpatterns = [
    path('create/',                                         views.create_combo,                 name='create_combo'),
    path('list/',                                           views.list_combos,                  name='list_combos'),
    path('active/',                                         views.get_active_combos,            name='get_active_combos'),
    path('<int:pk>/',                                       views.get_combo,                    name='get_combo'),
    path('<int:pk>/update/',                                views.update_combo,                 name='update_combo'),
    path('<int:pk>/delete/',                                views.delete_combo,                 name='delete_combo'),
    path('<int:pk>/add-product/',                           views.add_product_to_combo,         name='add_product_to_combo'),
    path('<int:pk>/remove-product/<int:producto_combo_id>/', views.remove_product_from_combo,    name='remove_product_from_combo'),
    path('<int:pk>/update-product/<int:producto_combo_id>/', views.update_product_in_combo,      name='update_product_in_combo'),
]
