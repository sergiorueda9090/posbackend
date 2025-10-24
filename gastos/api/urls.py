# gasto/urls.py
from django.urls import path
from . import views

urlpatterns = [
    # Rutas para el Gasto Maestro (Tipo de Gasto)
    path('create/master/',          views.create_master_expense,    name='create_master_expense'), 
    path('list/master/',            views.list_master_expenses,     name='list_master_expenses'),
    path('<int:pk>/master/',        views.get_master_expense,       name='get_master_expense'),
    path('<int:pk>/master/update/', views.update_master_expense,    name='update_master_expense'),
    path('<int:pk>/master/delete/', views.delete_master_expense,    name='delete_master_expense'),

    # Rutas para el Registro de Gasto (Transaccional)
    path('create/record/',              views.create_expense_record, name='create_expense_record'), 
    path('list/record/',                views.list_expense_records,  name='list_expense_records'),
    path('<int:pk>/record/',            views.get_expense_record,    name='get_expense_record'),
    path('<int:pk>/record/update/',     views.update_expense_record, name='update_expense_record'),
    path('<int:pk>/record/delete/',     views.delete_expense_record, name='delete_expense_record'),
]