from django.urls import path

from . import views

app_name = 'direitos_titular'

urlpatterns = [
    path('', views.consultar, name='consultar'),
]
