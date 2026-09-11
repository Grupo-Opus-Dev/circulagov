from django.contrib import admin

from .models import Consentimento


@admin.register(Consentimento)
class ConsentimentoAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'finalidade', 'versao_termos', 'aceito_em', 'revogado_em')
    list_filter = ('finalidade', 'versao_termos')
    readonly_fields = ('aceito_em',)
