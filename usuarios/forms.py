from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import BaseUserCreationForm

from alunos.models import Aluno

Usuario = get_user_model()

CLASSE_CAMPO = (
    'w-full rounded-md border border-slate-300 px-3 py-2 text-sm '
    'focus:outline-none focus:ring-2 focus:ring-blue-600 focus:border-blue-600'
)


class FormularioNovoUsuario(BaseUserCreationForm):
    """Cadastro de usuário pela área de gestão.

    Herda de BaseUserCreationForm para aproveitar a confirmação de senha
    e os validadores do projeto, em vez de reimplementar essa parte.

    O e-mail é obrigatório aqui, diferente do Usuario em geral, porque
    sem ele a pessoa não consegue recuperar a própria senha, e quem
    cadastra não deveria ser o único caminho de volta.
    """

    email = forms.EmailField(label='E-mail', required=True)

    is_staff = forms.BooleanField(
        label='Acesso à gestão e à auditoria',
        required=False,
        help_text='Permite abrir esta área e a tela de integridade do log.',
    )

    ra = forms.CharField(
        label='RA', required=False,
        help_text='Preencha para vincular um cadastro de aluno.',
    )
    nome_completo = forms.CharField(label='Nome completo', required=False)

    class Meta(BaseUserCreationForm.Meta):
        model = Usuario
        fields = ('username', 'email')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for nome, campo in self.fields.items():
            if nome == 'is_staff':
                continue
            campo.widget.attrs['class'] = CLASSE_CAMPO

    def clean(self):
        dados = super().clean()
        ra = (dados.get('ra') or '').strip()
        nome = (dados.get('nome_completo') or '').strip()

        # Aluno exige os dois. Deixar passar só um criaria cadastro pela
        # metade, ou falharia lá na frente com erro pouco claro.
        if ra and not nome:
            self.add_error('nome_completo', 'Informe o nome completo do aluno.')
        if nome and not ra:
            self.add_error('ra', 'Informe o RA do aluno.')

        if ra and Aluno.objects.filter(ra=ra).exists():
            self.add_error('ra', 'Já existe um aluno com esse RA.')

        return dados

    def save(self, commit=True):
        usuario = super().save(commit=False)
        usuario.email = self.cleaned_data['email']
        usuario.is_staff = self.cleaned_data.get('is_staff', False)
        usuario.save()

        ra = (self.cleaned_data.get('ra') or '').strip()
        if ra:
            Aluno.objects.create(
                usuario=usuario,
                ra=ra,
                nome_completo=self.cleaned_data['nome_completo'].strip(),
            )

        return usuario
