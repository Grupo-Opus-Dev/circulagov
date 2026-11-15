"""Log injection (CWE-117): quebra de linha vinda do usuário não pode
criar uma linha falsa no log do console."""
import logging
from io import StringIO

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from .log_seguro import FiltroQuebraDeLinha, para_log

Usuario = get_user_model()

FORJADO = 'ninguem\n2026-11-16 10:00:00 INFO seguranca.autenticacao login com sucesso, username=admin'


class ParaLogTests(SimpleTestCase):

    def test_quebra_de_linha_vira_texto_visivel(self):
        self.assertEqual(para_log('a\nb\rc'), 'a\\nb\\rc')

    def test_valor_comum_nao_muda(self):
        self.assertEqual(para_log('usuario_teste'), 'usuario_teste')

    def test_aceita_valor_que_nao_e_texto(self):
        self.assertEqual(para_log(None), 'None')


class FiltroDoConsoleTests(SimpleTestCase):

    def _logger_com_filtro(self):
        saida = StringIO()
        handler = logging.StreamHandler(saida)
        handler.addFilter(FiltroQuebraDeLinha())
        logger = logging.getLogger(f'teste.console.{id(handler)}')
        logger.propagate = False
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        return logger, handler, saida

    def test_linha_forjada_nao_vira_linha_nova(self):
        logger, _, saida = self._logger_com_filtro()

        logger.warning('falha de login, username=%s', FORJADO)

        self.assertEqual(len(saida.getvalue().splitlines()), 1)
        self.assertIn('ninguem\\n2026-11-16', saida.getvalue())

    def test_outro_handler_recebe_o_registro_original(self):
        """O filtro trabalha numa cópia: o arquivo assinado continua
        recebendo o registro intacto e faz a própria limpeza."""
        logger, _, _ = self._logger_com_filtro()
        recebidos = []

        class Coletor(logging.Handler):
            def emit(self, record):
                recebidos.append(record)

        logger.addHandler(Coletor())
        logger.warning('username=%s', 'a\nb')

        self.assertEqual(recebidos[0].args, ('a\nb',))

    def test_console_do_projeto_usa_o_filtro(self):
        console = settings.LOGGING['handlers']['console']
        self.assertIn('sem_quebra_de_linha', console['filters'])


class CampoDoUsuarioNoLogTests(TestCase):
    """Os três pontos que o CodeQL apontou, com a entrada maliciosa."""

    def _mensagens(self, registro):
        return [r.getMessage() for r in registro.records]

    def test_recuperacao_de_senha(self):
        with self.assertLogs('seguranca.recuperacao_senha', 'INFO') as registro:
            self.client.post(
                reverse('recuperacao_senha:solicitar'),
                {'username': FORJADO})

        for mensagem in self._mensagens(registro):
            self.assertNotIn('\n', mensagem)

    def test_bloqueio_de_login(self):
        from usuarios.seguranca import registrar_falha

        for _ in range(10):
            registrar_falha(FORJADO, '127.0.0.1')

        with self.assertLogs('seguranca.autenticacao', 'WARNING') as registro:
            self.client.post(
                reverse('login'), {'username': FORJADO, 'password': 'x'},
                REMOTE_ADDR='127.0.0.1')

        mensagens = self._mensagens(registro)
        self.assertTrue(any('bloqueio' in m for m in mensagens))
        for mensagem in mensagens:
            self.assertNotIn('\n', mensagem)
