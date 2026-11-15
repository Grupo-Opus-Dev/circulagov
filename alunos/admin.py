from django import forms
from django.contrib import admin

from .models import TAMANHO_MAXIMO_RA, Aluno


class FormularioAlunoAdmin(forms.ModelForm):
    # O RA fica cifrado no banco, então não é campo do model: entra aqui
    # como texto e é gravado pela propriedade `ra` do Aluno.
    ra = forms.CharField(label='RA', max_length=TAMANHO_MAXIMO_RA)

    class Meta:
        model = Aluno
        fields = ('usuario', 'ra', 'nome_completo')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields['ra'].initial = self.instance.ra

    def clean(self):
        dados = super().clean()
        ra = (dados.get('ra') or '').strip()
        if ra:
            repetido = Aluno.objects.com_ra(ra)
            if self.instance.pk:
                repetido = repetido.exclude(pk=self.instance.pk)
            if repetido.exists():
                self.add_error('ra', 'Já existe um aluno com esse RA.')
            self.instance.ra = ra
        return dados


@admin.register(Aluno)
class AlunoAdmin(admin.ModelAdmin):
    form = FormularioAlunoAdmin
    list_display = ('nome_completo', 'ra', 'usuario')
    search_fields = ('nome_completo',)

    def get_search_results(self, request, queryset, termo):
        # O RA cifrado não aceita busca por parte do texto. O RA completo
        # é encontrado pelo índice.
        resultado, tem_duplicados = super().get_search_results(
            request, queryset, termo)
        if termo:
            resultado |= queryset.com_ra(termo)
        return resultado, tem_duplicados
