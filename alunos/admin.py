from django.contrib import admin

from .models import Aluno


@admin.register(Aluno)
class AlunoAdmin(admin.ModelAdmin):
    list_display = ('nome_completo', 'ra', 'usuario')
    search_fields = ('nome_completo', 'ra')
