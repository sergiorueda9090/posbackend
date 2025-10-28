"""
URL configuration for backend project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include

from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)


urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/user/',                   include('user.api.urls'),                name='user_api'),
    path('api/clients/',                include('clientes.api.urls'),            name='clients_api'),
    path('api/categories/',             include('categoria.api.urls'),           name='categories_api'),
    path('api/suppliers/',              include('proveedores.api.urls'),         name='suppliers_api'),
    path('api/cards/',                  include('tarjetabancaria.api.urls'),     name='cards_api'),
    path('api/gastos/',                 include('gastos.api.urls'),              name='expenses_api'),
    path('api/recepcionpago/',          include('recepcionpago.api.urls'),       name='payments_api'),
    path('api/cargosnoregistrados/',    include('cargosnoregistrados.api.urls'), name='unregistered_charges_api'),
    path('api/ajustessaldo/',           include('ajustessaldo.api.urls'),        name='adjustments_api'),
    path('api/utilidadocacional/',      include('utilidadocacional.api.urls'),   name='occasional_income_api'),

    path('api/token/',          TokenObtainPairView.as_view(),  name='token_obtain_pair'),
    path('api/token/refresh/',  TokenRefreshView.as_view(),     name='token_refresh'),
]
