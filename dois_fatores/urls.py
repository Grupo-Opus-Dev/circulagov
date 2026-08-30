from django.urls import path

from . import views

app_name = 'dois_fatores'

urlpatterns = [
    path('cadastrar/', views.cadastrar, name='cadastrar'),
    path('verificar/', views.verificar, name='verificar'),
]
