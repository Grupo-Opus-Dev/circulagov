from django.urls import path

from . import views, views_gestao

app_name = 'usuarios'

urlpatterns = [
    path('', views.inicio, name='inicio'),

    path('gestao/usuarios/', views_gestao.lista_usuarios, name='gestao_lista'),
    path('gestao/usuarios/novo/', views_gestao.novo_usuario, name='gestao_novo'),
    path('gestao/usuarios/<int:usuario_id>/',
         views_gestao.detalhe_usuario, name='gestao_detalhe'),
]
