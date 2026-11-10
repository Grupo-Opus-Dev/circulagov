"""Rotas do arquivo de teste da esteira. Nunca deve chegar na main."""
from django.urls import path

from . import exemplo_vulneravel

urlpatterns = [
    path("cmd/", exemplo_vulneravel.executar_comando),
    path("calc/", exemplo_vulneravel.calcular),
]
