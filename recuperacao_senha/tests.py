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
        self.assertIsNone(
            TokenRecuperacaoSenha.validar('valor-que-nao-existe'))


class FluxoRecuperacaoSenhaTests(TestCase):
    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            username='usuario_teste', password='SenhaAntiga@123'
        )

    def test_solicitar_gera_token_para_usuario_existente(self):
        self.client.post(reverse('recuperacao_senha:solicitar'), {
                         'username': 'usuario_teste'})
        self.assertTrue(TokenRecuperacaoSenha.objects.filter(
            usuario=self.usuario).exists())

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

        self.client.post(
            url, {'senha_nova': 'SenhaNova@456', 'confirmacao': 'SenhaNova@456'})

        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password('SenhaNova@456'))

    def test_redefinir_marca_token_como_usado(self):
        registro, valor_bruto = TokenRecuperacaoSenha.gerar(self.usuario)
        url = reverse('recuperacao_senha:redefinir', args=[valor_bruto])

        self.client.post(
            url, {'senha_nova': 'SenhaNova@456', 'confirmacao': 'SenhaNova@456'})

        registro.refresh_from_db()
        self.assertIsNotNone(registro.usado_em)

    def test_redefinir_com_token_ja_usado_falha(self):
        registro, valor_bruto = TokenRecuperacaoSenha.gerar(self.usuario)
        url = reverse('recuperacao_senha:redefinir', args=[valor_bruto])

        self.client.post(
            url, {'senha_nova': 'SenhaNova@456', 'confirmacao': 'SenhaNova@456'})
        resposta = self.client.get(url)

        self.assertEqual(resposta.status_code, 400)

    def test_redefinir_com_senhas_diferentes_nao_troca(self):
        registro, valor_bruto = TokenRecuperacaoSenha.gerar(self.usuario)
        url = reverse('recuperacao_senha:redefinir', args=[valor_bruto])

        self.client.post(
            url, {'senha_nova': 'SenhaNova@456', 'confirmacao': 'OutraSenha@789'})

        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password('SenhaAntiga@123'))


class TesteExpiracaoDoToken(TestCase):
    """Requisito 2.3: o token deixa de ser válido depois de um tempo definido."""

    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            username='usuario_teste', password='SenhaAntiga@123'
        )

    def test_prazo_de_validade_esta_dentro_do_esperado(self):
        from recuperacao_senha.models import MINUTOS_VALIDADE_TOKEN
        self.assertGreaterEqual(MINUTOS_VALIDADE_TOKEN, 30)
        self.assertLessEqual(MINUTOS_VALIDADE_TOKEN, 60)

    def test_token_ainda_nao_expirado_continua_valido(self):
        registro, valor_bruto = TokenRecuperacaoSenha.gerar(self.usuario)
        registro.expira_em = timezone.now() + timezone.timedelta(seconds=5)
        registro.save(update_fields=['expira_em'])

        self.assertIsNotNone(TokenRecuperacaoSenha.validar(valor_bruto))

    def test_token_expirado_por_um_segundo_ja_nao_vale(self):
        registro, valor_bruto = TokenRecuperacaoSenha.gerar(self.usuario)
        registro.expira_em = timezone.now() - timezone.timedelta(seconds=1)
        registro.save(update_fields=['expira_em'])

        self.assertIsNone(TokenRecuperacaoSenha.validar(valor_bruto))


class TesteInvalidacaoAposUso(TestCase):
    """Requisito 2.4: token usado uma vez não pode ser reutilizado."""

    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            username='usuario_teste', password='SenhaAntiga@123'
        )

    def test_segunda_tentativa_de_redefinir_com_mesmo_token_nao_troca_senha_de_novo(self):
        registro, valor_bruto = TokenRecuperacaoSenha.gerar(self.usuario)
        url = reverse('recuperacao_senha:redefinir', args=[valor_bruto])

        self.client.post(
            url, {'senha_nova': 'PrimeiraSenha@111', 'confirmacao': 'PrimeiraSenha@111'})
        resposta_segunda_tentativa = self.client.post(
            url, {'senha_nova': 'SegundaSenha@222',
                  'confirmacao': 'SegundaSenha@222'}
        )

        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password('PrimeiraSenha@111'))
        self.assertFalse(self.usuario.check_password('SegundaSenha@222'))
        self.assertEqual(resposta_segunda_tentativa.status_code, 400)


class TesteMensagemGenericaDeFalha(TestCase):
    """Requisito 2.5: falha clara e genérica, sem vazar qual foi o motivo."""

    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            username='usuario_teste', password='SenhaAntiga@123'
        )

    def _conteudo_da_pagina_de_erro(self, token):
        resposta = self.client.get(
            reverse('recuperacao_senha:redefinir', args=[token]))
        return resposta.status_code, resposta.content

    def test_token_expirado_usado_e_inexistente_mostram_a_mesma_pagina(self):
        registro_expirado, token_expirado = TokenRecuperacaoSenha.gerar(
            self.usuario)
        registro_expirado.expira_em = timezone.now() - timezone.timedelta(minutes=1)
        registro_expirado.save(update_fields=['expira_em'])

        registro_usado, token_usado = TokenRecuperacaoSenha.gerar(self.usuario)
        registro_usado.marcar_usado()

        status_expirado, corpo_expirado = self._conteudo_da_pagina_de_erro(
            token_expirado)
        status_usado, corpo_usado = self._conteudo_da_pagina_de_erro(
            token_usado)
        status_inexistente, corpo_inexistente = self._conteudo_da_pagina_de_erro(
            'token-que-nunca-existiu')

        self.assertEqual(status_expirado, 400)
        self.assertEqual(status_usado, 400)
        self.assertEqual(status_inexistente, 400)
        self.assertEqual(corpo_expirado, corpo_usado)
        self.assertEqual(corpo_usado, corpo_inexistente)
