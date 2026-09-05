"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
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

Usamos aqui para guardar as URLs utilizadas no sistema WEB.
"""
from django.contrib import admin
from django.urls import include, path

from usuarios.views import LoginComDoisFatoresView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('contas/login/', LoginComDoisFatoresView.as_view(), name='login'),
    path('contas/', include('django.contrib.auth.urls')),
    path('', include('usuarios.urls')),
    path('dois-fatores/', include('dois_fatores.urls')),
    path('recuperar-senha/', include('recuperacao_senha.urls')),
]
