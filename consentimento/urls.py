from django.urls import path

from . import views

app_name = 'consentimento'

urlpatterns = [
    path('', views.gerenciar, name='gerenciar'),
    path('revogar/<int:consentimento_id>/', views.revogar, name='revogar'),
]
