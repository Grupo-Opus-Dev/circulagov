from django.urls import path

from . import views, views_gestao

app_name = 'usuarios'

urlpatterns = [
    path('', views.inicio, name='inicio'),

    path('gestao/usuarios/', views_gestao.lista_usuarios, name='gestao_lista'),
    path('gestao/usuarios/novo/', views_gestao.novo_usuario, name='gestao_novo'),
    path('gestao/usuarios/<int:usuario_id>/',
         views_gestao.detalhe_usuario, name='gestao_detalhe'),
    path('gestao/usuarios/<int:usuario_id>/editar/',
         views_gestao.editar_usuario, name='gestao_editar'),
    path('gestao/usuarios/<int:usuario_id>/senha/',
         views_gestao.definir_senha, name='gestao_definir_senha'),
    path('gestao/usuarios/<int:usuario_id>/enviar-link-senha/',
         views_gestao.enviar_link_de_senha, name='gestao_enviar_link_senha'),
    path('gestao/usuarios/<int:usuario_id>/remover-2fa/',
         views_gestao.remover_dois_fatores, name='gestao_remover_2fa'),
]
