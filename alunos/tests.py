from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from .models import Aluno

Usuario = get_user_model()


class TesteCadastroDoAluno(TestCase):
    """Evidência funcional de que o Aluno tem só os dados definidos em
    docs/DADOS_PESSOAIS.md: RA, nome completo e e-mail institucional."""

    def test_aluno_com_email_institucional_e_criado_normalmente(self):
        usuario = Usuario.objects.create_user(
            username='12345678',
            password='SenhaDeTeste123',
            email='12345678@aluno.educacao.sp.gov.br',
        )
        aluno = Aluno.objects.create(
            usuario=usuario, ra='12345678', nome_completo='Maria da Silva'
        )

        self.assertEqual(aluno.ra, '12345678')
        self.assertEqual(str(aluno), 'Maria da Silva (RA 12345678)')

    def test_aluno_sem_email_institucional_nao_e_criado(self):
        usuario = Usuario.objects.create_user(
            username='87654321', password='SenhaDeTeste123'
        )

        with self.assertRaises(ValidationError):
            Aluno.objects.create(
                usuario=usuario, ra='87654321', nome_completo='João Souza'
            )

    def test_ra_repetido_nao_e_permitido(self):
        usuario_1 = Usuario.objects.create_user(
            username='11111111',
            password='SenhaDeTeste123',
            email='11111111@aluno.educacao.sp.gov.br',
        )
        Aluno.objects.create(usuario=usuario_1, ra='11111111', nome_completo='Aluno Um')

        usuario_2 = Usuario.objects.create_user(
            username='outro_usuario',
            password='SenhaDeTeste123',
            email='11111111-outro@aluno.educacao.sp.gov.br',
        )
        with self.assertRaises(ValidationError):
            Aluno.objects.create(usuario=usuario_2, ra='11111111', nome_completo='Aluno Dois')


class TesteLoginDoAlunoComRA(TestCase):
    """Evidência de que o aluno entra pela tela de login normal, digitando
    o RA no campo de usuário, sem nenhuma tela nova."""

    def setUp(self):
        self.senha = 'SenhaDeTeste123'
        self.usuario = Usuario.objects.create_user(
            username='99998888',
            password=self.senha,
            email='99998888@aluno.educacao.sp.gov.br',
        )
        Aluno.objects.create(
            usuario=self.usuario, ra='99998888', nome_completo='Aluno Teste'
        )

    def test_login_com_ra_e_senha_funciona(self):
        self.client.post(
            reverse('login'), {'username': '99998888', 'password': self.senha}
        )

        resposta = self.client.get(reverse('usuarios:inicio'))
        self.assertEqual(resposta.status_code, 200)
