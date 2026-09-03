from django.urls import path

from . import views

app_name = 'recuperacao_senha'

urlpatterns = [
    path('', views.solicitar, name='solicitar'),
    path('redefinir/<str:token>/', views.redefinir, name='redefinir'),
]
