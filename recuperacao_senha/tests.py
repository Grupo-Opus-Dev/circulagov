from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from .models import TokenRecuperacaoSenha

Usuario = get_user_model()


class TokenRecuperacaoSenhaTests(TestCase):
    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            username='usuario_teste', password='SenhaAntiga@123'
        )

    def test_token_gerado_e_valido(self):
        registro, valor_bruto = TokenRecuperacaoSenha.gerar(self.usuario)
        encontrado = TokenRecuperacaoSenha.validar(valor_bruto)
        self.assertEqual(encontrado, registro)

    def test_valor_bruto_nao_fica_salvo_no_banco(self):
        registro, valor_bruto = TokenRecuperacaoSenha.gerar(self.usuario)
        self.assertNotEqual(registro.token_hash, valor_bruto)

    def test_token_expirado_nao_valida(self):
        registro, valor_bruto = TokenRecuperacaoSenha.gerar(self.usuario)
        registro.expira_em = timezone.now() - timezone.timedelta(minutes=1)
        registro.save(update_fields=['expira_em'])

        self.assertIsNone(TokenRecuperacaoSenha.validar(valor_bruto))

    def test_token_usado_nao_valida_de_novo(self):
        registro, valor_bruto = TokenRecuperacaoSenha.gerar(self.usuario)
        registro.marcar_usado()

        self.assertIsNone(TokenRecuperacaoSenha.validar(valor_bruto))

    def test_token_invalido_nao_valida(self):
        self.assertIsNone(TokenRecuperacaoSenha.validar('valor-que-nao-existe'))


class FluxoRecuperacaoSenhaTests(TestCase):
    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            username='usuario_teste', password='SenhaAntiga@123'
        )

    def test_solicitar_gera_token_para_usuario_existente(self):
        self.client.post(reverse('recuperacao_senha:solicitar'), {'username': 'usuario_teste'})
        self.assertTrue(TokenRecuperacaoSenha.objects.filter(usuario=self.usuario).exists())

    def test_solicitar_nao_revela_se_usuario_existe(self):
        resposta_existente = Client().post(
            reverse('recuperacao_senha:solicitar'), {'username': 'usuario_teste'}, follow=True
        )
        resposta_inexistente = Client().post(
            reverse('recuperacao_senha:solicitar'), {'username': 'nao_existe'}, follow=True
        )
        self.assertEqual(
            [m.message for m in resposta_existente.context['messages']],
            [m.message for m in resposta_inexistente.context['messages']],
        )

    def test_redefinir_com_token_valido_troca_a_senha(self):
        registro, valor_bruto = TokenRecuperacaoSenha.gerar(self.usuario)
        url = reverse('recuperacao_senha:redefinir', args=[valor_bruto])

        self.client.post(url, {'senha_nova': 'SenhaNova@456', 'confirmacao': 'SenhaNova@456'})

        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password('SenhaNova@456'))

    def test_redefinir_marca_token_como_usado(self):
        registro, valor_bruto = TokenRecuperacaoSenha.gerar(self.usuario)
        url = reverse('recuperacao_senha:redefinir', args=[valor_bruto])

        self.client.post(url, {'senha_nova': 'SenhaNova@456', 'confirmacao': 'SenhaNova@456'})

        registro.refresh_from_db()
        self.assertIsNotNone(registro.usado_em)

    def test_redefinir_com_token_ja_usado_falha(self):
        registro, valor_bruto = TokenRecuperacaoSenha.gerar(self.usuario)
        url = reverse('recuperacao_senha:redefinir', args=[valor_bruto])

        self.client.post(url, {'senha_nova': 'SenhaNova@456', 'confirmacao': 'SenhaNova@456'})
        resposta = self.client.get(url)

        self.assertEqual(resposta.status_code, 400)

    def test_redefinir_com_senhas_diferentes_nao_troca(self):
        registro, valor_bruto = TokenRecuperacaoSenha.gerar(self.usuario)
        url = reverse('recuperacao_senha:redefinir', args=[valor_bruto])

        self.client.post(url, {'senha_nova': 'SenhaNova@456', 'confirmacao': 'OutraSenha@789'})

        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password('SenhaAntiga@123'))
