from django.urls import path

from . import views

app_name = 'direitos_titular'

urlpatterns = [
    path('', views.consultar, name='consultar'),
    path('exportar/', views.exportar, name='exportar'),
    path('excluir/', views.confirmar_exclusao, name='confirmar_exclusao'),
    path('excluir/confirmar/', views.excluir, name='excluir'),
]
