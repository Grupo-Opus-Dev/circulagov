from django.urls import path

from . import views

app_name = 'consentimento'

urlpatterns = [
    path('', views.gerenciar, name='gerenciar'),
]
