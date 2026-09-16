import base64
import logging
import tempfile
from io import StringIO
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from .integridade import HandlerLogIntegro, verificar_arquivo

Usuario = get_user_model()

CHAVE_TESTE = base64.b64encode(b'k' * 32).decode()
OUTRA_CHAVE = base64.b64encode(b'x' * 32).decode()


def gravar_eventos(caminho, mensagens, chave=CHAVE_TESTE):
    """Grava mensagens usando o handler real, como a aplicação faz."""
    handler = HandlerLogIntegro(caminho, chave)
    handler.setFormatter(logging.Formatter('%(levelname)s %(name)s %(message)s'))
    logger = logging.getLogger(f'teste.integridade.{id(handler)}')
    logger.propagate = False
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    for mensagem in mensagens:
        logger.info(mensagem)
    logger.removeHandler(handler)
    handler.close()


class CadeiaDeIntegridadeTests(SimpleTestCase):
    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.caminho = Path(self.pasta.name) / 'seguranca.log'

    def tearDown(self):
        self.pasta.cleanup()

    def linhas(self):
        return self.caminho.read_text(encoding='utf-8').splitlines()

    def reescrever(self, linhas):
        self.caminho.write_text('\n'.join(linhas) + '\n', encoding='utf-8')

    def test_log_sem_alteracao_e_integro(self):
        gravar_eventos(self.caminho, ['login ok', 'logout', 'login falhou'])
        resultado = verificar_arquivo(self.caminho, CHAVE_TESTE)
        self.assertTrue(resultado.integro)
        self.assertEqual(resultado.total_linhas, 3)

    def test_alterar_texto_de_uma_linha_e_detectado(self):
        gravar_eventos(self.caminho, ['login falhou username=ana', 'logout'])
        linhas = self.linhas()
        linhas[0] = linhas[0].replace('falhou', 'ok')
        self.reescrever(linhas)

        resultado = verificar_arquivo(self.caminho, CHAVE_TESTE)
        self.assertFalse(resultado.integro)
        self.assertEqual(resultado.linha_com_problema, 1)

    def test_apagar_linha_do_meio_e_detectado(self):
        gravar_eventos(self.caminho, ['evento 1', 'evento 2', 'evento 3'])
        linhas = self.linhas()
        del linhas[1]
        self.reescrever(linhas)

        resultado = verificar_arquivo(self.caminho, CHAVE_TESTE)
        self.assertFalse(resultado.integro)
        self.assertEqual(resultado.linha_com_problema, 2)

    def test_inserir_linha_forjada_sem_a_chave_e_detectado(self):
        gravar_eventos(self.caminho, ['evento 1', 'evento 2'])
        linhas = self.linhas()
        linhas.insert(1, 'INFO seguranca login ok username=invasor | mac=' + 'a' * 64)
        self.reescrever(linhas)

        resultado = verificar_arquivo(self.caminho, CHAVE_TESTE)
        self.assertFalse(resultado.integro)
        self.assertEqual(resultado.linha_com_problema, 2)

    def test_linha_sem_assinatura_e_detectada(self):
        gravar_eventos(self.caminho, ['evento 1'])
        linhas = self.linhas() + ['INFO seguranca linha adicionada na mao']
        self.reescrever(linhas)

        resultado = verificar_arquivo(self.caminho, CHAVE_TESTE)
        self.assertFalse(resultado.integro)
        self.assertEqual(resultado.motivo, 'linha sem assinatura')

    def test_verificar_com_chave_errada_falha(self):
        gravar_eventos(self.caminho, ['evento 1'])
        resultado = verificar_arquivo(self.caminho, OUTRA_CHAVE)
        self.assertFalse(resultado.integro)

    def test_quebra_de_linha_na_mensagem_nao_forja_linha_nova(self):
        # Simula um username malicioso tentando criar uma linha falsa.
        gravar_eventos(self.caminho, ['login falhou username=x\nINFO seguranca login ok'])
        self.assertEqual(len(self.linhas()), 1)
        self.assertTrue(verificar_arquivo(self.caminho, CHAVE_TESTE).integro)

    def test_cadeia_continua_depois_de_reiniciar_o_servidor(self):
        gravar_eventos(self.caminho, ['antes de reiniciar'])
        # Handler novo no mesmo arquivo simula o servidor subindo de novo.
        gravar_eventos(self.caminho, ['depois de reiniciar'])
        resultado = verificar_arquivo(self.caminho, CHAVE_TESTE)
        self.assertTrue(resultado.integro)
        self.assertEqual(resultado.total_linhas, 2)

    def test_chave_curta_e_recusada(self):
        chave_curta = base64.b64encode(b'curta').decode()
        with self.assertRaises(ValueError):
            HandlerLogIntegro(self.caminho, chave_curta)


class TelaEComandoDeIntegridadeTests(TestCase):
    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.caminho = Path(self.pasta.name) / 'seguranca.log'
        self.override = override_settings(
            LOG_DIR=Path(self.pasta.name), CHAVE_INTEGRIDADE_LOGS=CHAVE_TESTE
        )
        self.override.enable()

    def tearDown(self):
        self.override.disable()
        self.pasta.cleanup()

    def adulterar(self):
        linhas = self.caminho.read_text(encoding='utf-8').splitlines()
        linhas[0] = linhas[0].replace('evento', 'EVENTO')
        self.caminho.write_text('\n'.join(linhas) + '\n', encoding='utf-8')

    def test_tela_exige_administrador(self):
        comum = Usuario.objects.create_user(username='comum', password='Senha@12345')
        self.client.force_login(comum)
        resposta = self.client.get(reverse('auditoria:integridade'))
        self.assertEqual(resposta.status_code, 302)

    def test_tela_mostra_log_integro(self):
        gravar_eventos(self.caminho, ['evento 1', 'evento 2'])
        admin = Usuario.objects.create_user(
            username='admin', password='Senha@12345', is_staff=True
        )
        self.client.force_login(admin)
        resposta = self.client.get(reverse('auditoria:integridade'))
        self.assertContains(resposta, 'Log íntegro')

    def test_tela_mostra_linha_adulterada(self):
        gravar_eventos(self.caminho, ['evento 1', 'evento 2'])
        self.adulterar()
        admin = Usuario.objects.create_user(
            username='admin', password='Senha@12345', is_staff=True
        )
        self.client.force_login(admin)
        resposta = self.client.get(reverse('auditoria:integridade'))
        self.assertContains(resposta, 'Log alterado na linha 1')

    def test_comando_aprova_log_integro(self):
        gravar_eventos(self.caminho, ['evento 1'])
        saida = StringIO()
        call_command('verificar_logs', stdout=saida)
        self.assertIn('Log íntegro', saida.getvalue())

    def test_comando_falha_com_log_adulterado(self):
        gravar_eventos(self.caminho, ['evento 1'])
        self.adulterar()
        with self.assertRaises(CommandError):
            call_command('verificar_logs', stdout=StringIO())
