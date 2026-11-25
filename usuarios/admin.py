from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .exclusao import pode_excluir
from .models import Usuario


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):

    def has_delete_permission(self, request, obj=None):
        # O Django consulta por objeto também na exclusão em lote, então a
        # regra vale para o botão e para a ação "excluir selecionados".
        if obj is not None and not pode_excluir(obj, request.user):
            return False
        return super().has_delete_permission(request, obj)
