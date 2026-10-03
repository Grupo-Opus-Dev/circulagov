import threading
import time
from unittest import mock

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.db import connection
from django.test import (
    Client, RequestFactory, TestCase, TransactionTestCase,
)
from django.urls import reverse
from django.utils import timezone

from .models import TokenRecuperacaoSenha
from .views import enviar_email_recuperacao

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


class TesteLogDeSolicitacao(TestCase):
    """Requisito 2.6: toda solicitacao de recuperacao de senha precisa gerar um registro no log."""

    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            username='usuario_teste', password='SenhaAntiga@123'
        )

    def test_solicitar_com_usuario_existente_gera_log(self):
        with self.assertLogs('seguranca.recuperacao_senha', level='INFO') as logs:
            self.client.post(reverse('recuperacao_senha:solicitar'),
                              {'username': 'usuario_teste'})

        self.assertIn('usuario_teste', logs.output[0])

    def test_solicitar_com_usuario_inexistente_tambem_gera_log(self):
        with self.assertLogs('seguranca.recuperacao_senha', level='INFO') as logs:
            self.client.post(reverse('recuperacao_senha:solicitar'),
                              {'username': 'nao_existe'})

        self.assertIn('nao_existe', logs.output[0])


class TesteLogDeResultado(TestCase):
    """Requisito 2.7: o log tem que dizer se a recuperacao deu certo ou nao, e o motivo, sem vazar senha ou token."""

    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            username='usuario_teste', password='SenhaAntiga@123'
        )

    def test_redefinir_com_sucesso_gera_log_de_sucesso(self):
        registro, valor_bruto = TokenRecuperacaoSenha.gerar(self.usuario)
        url = reverse('recuperacao_senha:redefinir', args=[valor_bruto])

        with self.assertLogs('seguranca.recuperacao_senha', level='INFO') as logs:
            self.client.post(
                url, {'senha_nova': 'SenhaNova@456', 'confirmacao': 'SenhaNova@456'})

        self.assertIn('sucesso', logs.output[-1])

    def test_redefinir_com_token_invalido_gera_log_de_falha_com_motivo(self):
        with self.assertLogs('seguranca.recuperacao_senha', level='WARNING') as logs:
            self.client.get(
                reverse('recuperacao_senha:redefinir', args=['token-que-nao-existe']))

        self.assertIn('token_nao_encontrado', logs.output[0])

    def test_log_de_falha_nao_vaza_senha_ou_token(self):
        registro, valor_bruto = TokenRecuperacaoSenha.gerar(self.usuario)
        url = reverse('recuperacao_senha:redefinir', args=[valor_bruto])

        with self.assertLogs('seguranca.recuperacao_senha', level='INFO') as logs:
            self.client.post(
                url, {'senha_nova': 'SenhaNova@456', 'confirmacao': 'OutraSenha@789'})

        mensagens = ' '.join(logs.output)
        self.assertNotIn('SenhaNova@456', mensagens)
        self.assertNotIn(valor_bruto, mensagens)


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


class TesteValidadoresNaRedefinicao(TestCase):
    """A redefinição aceitava qualquer senha, até "1", porque só conferia
    se as duas digitadas batiam. Os validadores do projeto valiam no
    cadastro e na troca de senha, mas não por este caminho."""

    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            username='usuario_teste', password='SenhaAntiga@123')
        self.registro, valor_bruto = TokenRecuperacaoSenha.gerar(self.usuario)
        self.url = reverse('recuperacao_senha:redefinir', args=[valor_bruto])

    def test_senha_curta_e_recusada(self):
        self.client.post(self.url, {'senha_nova': '1', 'confirmacao': '1'})
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password('SenhaAntiga@123'))

    def test_senha_comum_e_recusada(self):
        self.client.post(
            self.url, {'senha_nova': 'password', 'confirmacao': 'password'})
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password('SenhaAntiga@123'))

    def test_senha_so_numerica_e_recusada(self):
        self.client.post(
            self.url, {'senha_nova': '83920175', 'confirmacao': '83920175'})
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password('SenhaAntiga@123'))

    def test_senha_recusada_nao_queima_o_token(self):
        """Errar a senha não pode obrigar a pessoa a pedir outro link."""
        self.client.post(self.url, {'senha_nova': '1', 'confirmacao': '1'})
        self.registro.refresh_from_db()
        self.assertIsNone(self.registro.usado_em)

    def test_motivo_da_recusa_aparece_na_tela(self):
        resposta = self.client.post(
            self.url, {'senha_nova': '1', 'confirmacao': '1'})
        mensagens = [m.message for m in resposta.context['messages']]
        self.assertTrue(any('8 caracteres' in m for m in mensagens))

    def test_recusa_vai_pro_log_sem_a_senha(self):
        with self.assertLogs('seguranca.recuperacao_senha', level='INFO') as registro:
            self.client.post(
                self.url, {'senha_nova': 'Fraca1', 'confirmacao': 'Fraca1'})
        texto = chr(10).join(registro.output)
        self.assertIn('senha_recusada_pelos_validadores', texto)
        self.assertNotIn('Fraca1', texto)


class TesteUsoSimultaneoDoToken(TransactionTestCase):
    """Dois pedidos com o mesmo link, ao mesmo tempo. Antes, os dois
    conferiam o token antes de qualquer um marcá-lo, e os dois trocavam
    a senha: o link de uso único servia duas vezes."""

    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            username='corrida', password='SenhaAntiga@123')
        self.registro, self.valor_bruto = TokenRecuperacaoSenha.gerar(
            self.usuario)
        self.url = reverse('recuperacao_senha:redefinir', args=[self.valor_bruto])

    def _rodar_em_paralelo(self, tarefas):
        resultados = [None] * len(tarefas)
        erros = []

        def executar(indice):
            try:
                resultados[indice] = tarefas[indice]()
            except Exception as erro:  # noqa: BLE001
                erros.append(erro)
            finally:
                connection.close()

        threads = [threading.Thread(target=executar, args=(i,))
                   for i in range(len(tarefas))]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)
        self.assertEqual(erros, [])
        return resultados

    def test_consumir_so_deixa_um_dos_pedidos_simultaneos_passar(self):
        barreira = threading.Barrier(2)

        def tentar():
            registro = TokenRecuperacaoSenha.objects.get(pk=self.registro.pk)
            barreira.wait(timeout=10)
            return registro.consumir()

        resultados = self._rodar_em_paralelo([tentar, tentar])
        self.assertEqual(sorted(resultados), [False, True])

    def test_dois_pedidos_pelo_mesmo_link_so_um_troca_a_senha(self):
        # Os dois leem o token antes de qualquer um gravar, que e a
        # situacao que quebrava o uso unico.
        barreira = threading.Barrier(2)
        original = TokenRecuperacaoSenha.buscar_com_motivo

        def buscar_e_esperar(valor_bruto):
            resposta = original(valor_bruto)
            barreira.wait(timeout=10)
            return resposta

        def pedir(senha):
            def executar():
                cliente = Client()
                resposta = cliente.post(self.url, {
                    'senha_nova': senha, 'confirmacao': senha})
                return resposta.status_code
            return executar

        with mock.patch.object(
                TokenRecuperacaoSenha, 'buscar_com_motivo',
                side_effect=buscar_e_esperar):
            resultados = self._rodar_em_paralelo([
                pedir('PrimeiraSenha@456'), pedir('SegundaSenha@789')])

        self.assertEqual(sorted(resultados), [302, 400])
        self.usuario.refresh_from_db()
        senhas_certas = [
            senha for senha in ('PrimeiraSenha@456', 'SegundaSenha@789')
            if self.usuario.check_password(senha)]
        self.assertEqual(len(senhas_certas), 1)

    def test_token_expirado_nao_e_consumido(self):
        self.registro.expira_em = timezone.now() - timezone.timedelta(minutes=1)
        self.registro.save()
        self.assertFalse(self.registro.consumir())
        self.registro.refresh_from_db()
        self.assertIsNone(self.registro.usado_em)

    def test_se_a_troca_de_senha_falha_o_token_continua_valendo(self):
        with mock.patch.object(
                Usuario, 'save', side_effect=RuntimeError('falha no banco')):
            with self.assertRaises(RuntimeError):
                Client().post(self.url, {
                    'senha_nova': 'SenhaNova@456',
                    'confirmacao': 'SenhaNova@456'})
        self.registro.refresh_from_db()
        self.assertIsNone(self.registro.usado_em)


class TesteLimiteDeEmailsPorConta(TestCase):
    """O nginx limita por endereço. Por conta, quem usa vários endereços
    ainda poderia encher a caixa de alguém e gastar a cota de envios."""

    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.usuario = Usuario.objects.create_user(
            username='alvo', password='SenhaAntiga@123',
            email='alvo@exemplo.com')

    def _pedir(self, ip='10.0.0.1', username='alvo'):
        return self.client.post(
            reverse('recuperacao_senha:solicitar'),
            {'username': username}, REMOTE_ADDR=ip)

    def test_so_os_3_primeiros_pedidos_da_hora_mandam_e_mail(self):
        for numero in range(6):
            self._pedir(ip=f'10.0.0.{numero}')
        self.assertEqual(len(mail.outbox), 3)

    def test_resposta_e_a_mesma_com_ou_sem_limite(self):
        respostas = []
        for _ in range(5):
            resposta = self._pedir()
            respostas.append(
                (resposta.status_code, resposta.headers['Location']))
        self.assertEqual(len(set(respostas)), 1)

    def test_resposta_para_usuario_inexistente_e_igual_a_de_conta_limitada(self):
        for _ in range(4):
            limitada = self._pedir()
        inexistente = self._pedir(username='ninguem')
        self.assertEqual(limitada.status_code, inexistente.status_code)
        self.assertEqual(
            limitada.headers['Location'], inexistente.headers['Location'])

    def test_limite_de_uma_conta_nao_afeta_outra(self):
        Usuario.objects.create_user(
            username='outra', password='SenhaAntiga@123', email='o@exemplo.com')
        for _ in range(5):
            self._pedir()
        antes = len(mail.outbox)
        self._pedir(username='outra')
        self.assertEqual(len(mail.outbox), antes + 1)

    def test_pedidos_recusados_nao_renovam_a_janela(self):
        for _ in range(5):
            self._pedir()
        with mock.patch('time.time', return_value=time.time() + 61 * 60):
            self._pedir()
        self.assertEqual(len(mail.outbox), 4)

    def test_limite_vai_pro_log(self):
        for _ in range(3):
            self._pedir()
        with self.assertLogs('seguranca.recuperacao_senha', level='WARNING') as logs:
            self._pedir()
        self.assertIn('limite de e-mails', ' '.join(logs.output))

    def test_convite_da_gestao_nao_conta_no_limite(self):
        pedido = RequestFactory().get('/')
        for _ in range(5):
            enviar_email_recuperacao(pedido, self.usuario, nova_conta=True)
        self.assertEqual(len(mail.outbox), 5)
