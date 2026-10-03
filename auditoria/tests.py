import base64
import logging
import subprocess
import sys
import tempfile
import time
from io import StringIO
from pathlib import Path

from django.conf import settings
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
    handler.setFormatter(logging.Formatter(
        '%(levelname)s %(name)s %(message)s'))
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
        linhas.insert(
            1, 'INFO seguranca login ok username=invasor | mac=' + 'a' * 64)
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
        gravar_eventos(
            self.caminho, ['login falhou username=x\nINFO seguranca login ok'])
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
        # Era 302 enquanto a tela usava o staff_member_required, que
        # mandava pro login do admin do Django. Agora quem ja esta
        # logado e nao tem permissao recebe 403, porque redirecionar
        # pra tela de entrar nao resolveria nada.
        comum = Usuario.objects.create_user(
            username='comum', password='Senha@12345')
        self.client.force_login(comum)
        resposta = self.client.get(reverse('auditoria:integridade'))
        self.assertEqual(resposta.status_code, 403)

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


class AnalisarLogsCommandTests(TestCase):
    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.caminho = Path(self.pasta.name) / 'seguranca.log'
        self.override = override_settings(LOG_DIR=Path(self.pasta.name))
        self.override.enable()

    def tearDown(self):
        self.override.disable()
        self.pasta.cleanup()

    def escrever_log(self, linhas):
        self.caminho.write_text('\n'.join(linhas) + '\n', encoding='utf-8')

    def test_conta_falhas_de_login_por_usuario(self):
        self.escrever_log([
            '2026-01-01 10:00:00,000 WARNING seguranca.autenticacao tentativa de login com falha, username=ana',
            '2026-01-01 10:00:01,000 WARNING seguranca.autenticacao tentativa de login com falha, username=ana',
            '2026-01-01 10:00:02,000 WARNING seguranca.autenticacao tentativa de login com falha, username=bruno',
        ])
        saida = StringIO()
        call_command('analisar_logs', stdout=saida)
        resultado = saida.getvalue()
        self.assertIn('ana: 2 tentativa(s)', resultado)
        self.assertIn('bruno: 1 tentativa(s)', resultado)

    def test_detecta_bloqueio_por_forca_bruta(self):
        self.escrever_log([
            '2026-01-01 10:00:00,000 WARNING seguranca.autenticacao bloqueio por forca bruta, username=ana',
        ])
        saida = StringIO()
        call_command('analisar_logs', stdout=saida)
        self.assertIn('ana: 1 bloqueio(s)', saida.getvalue())

    def test_conta_eventos_de_2fa(self):
        self.escrever_log([
            '2026-01-01 10:00:00,000 INFO seguranca.dois_fatores 2FA ativado, username=ana',
            '2026-01-01 10:00:01,000 INFO seguranca.dois_fatores codigo 2FA correto, username=ana',
            '2026-01-01 10:00:02,000 WARNING seguranca.dois_fatores codigo 2FA incorreto, username=ana',
        ])
        saida = StringIO()
        call_command('analisar_logs', stdout=saida)
        resultado = saida.getvalue()
        self.assertIn('1 ativação(ões)', resultado)
        self.assertIn('1 código(s) correto(s)', resultado)
        self.assertIn('1 código(s) incorreto(s)', resultado)

    def test_ignora_linhas_de_outros_loggers(self):
        self.escrever_log([
            '2026-01-01 10:00:00,000 INFO seguranca.recuperacao_senha solicitacao de recuperacao de senha para username=ana',
        ])
        saida = StringIO()
        call_command('analisar_logs', stdout=saida)
        resultado = saida.getvalue()
        self.assertIn('Nenhuma falha registrada', resultado)
        self.assertIn('Nenhum evento de 2FA registrado', resultado)

    def test_reconhece_linhas_com_assinatura_mac(self):
        self.escrever_log([
            '2026-01-01 10:00:00,000 WARNING seguranca.autenticacao tentativa de login com falha, username=ana | mac=' + 'a' * 64,
        ])
        saida = StringIO()
        call_command('analisar_logs', stdout=saida)
        self.assertIn('ana: 1 tentativa(s)', saida.getvalue())

    def test_arquivo_de_log_inexistente_gera_erro_claro(self):
        with self.assertRaises(CommandError):
            call_command('analisar_logs', stdout=StringIO())


# Executado em processos separados pelo teste abaixo. Fica em texto, e não
# como função, porque precisa rodar num interpretador novo, sem Django:
# é isso que o Gunicorn faz ao criar cada worker.
SCRIPT_TRABALHADOR = """
import logging, sys, time
from auditoria.integridade import HandlerLogIntegro

caminho, chave, numero, quantidade, inicio = sys.argv[1:6]
handler = HandlerLogIntegro(caminho, chave)
handler.setFormatter(logging.Formatter('%(message)s'))
log = logging.getLogger('trabalhador')
log.propagate = False
log.addHandler(handler)
log.setLevel(logging.INFO)

# Todos esperam o mesmo instante, pra disputar o arquivo de verdade.
while time.time() < float(inicio):
    time.sleep(0.001)

for i in range(int(quantidade)):
    log.info('worker %s evento %s', numero, i)
"""


class CadeiaComVariosProcessosTests(SimpleTestCase):
    """O Gunicorn de produção roda vários processos, cada um com o seu
    handler, todos gravando no mesmo arquivo. Na primeira versão a cadeia
    vivia na memória de cada processo e quebrava sozinha em produção,
    sem ninguém ter mexido no log."""

    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.caminho = Path(self.pasta.name) / 'seguranca.log'

    def tearDown(self):
        self.pasta.cleanup()

    def test_handlers_alternando_no_mesmo_arquivo_mantem_a_cadeia(self):
        """Determinístico: dois handlers, como dois workers, escrevendo
        em revezamento. Falhava quando o último MAC ficava na memória."""
        a = HandlerLogIntegro(self.caminho, CHAVE_TESTE)
        b = HandlerLogIntegro(self.caminho, CHAVE_TESTE)
        formato = logging.Formatter('%(message)s')
        logs = []
        for nome, handler in (('a', a), ('b', b)):
            handler.setFormatter(formato)
            log = logging.getLogger(f'teste.revezamento.{nome}.{id(handler)}')
            log.propagate = False
            log.addHandler(handler)
            log.setLevel(logging.INFO)
            logs.append(log)

        for rodada in range(5):
            logs[0].info('a %s', rodada)
            logs[1].info('b %s', rodada)

        a.close()
        b.close()
        resultado = verificar_arquivo(self.caminho, CHAVE_TESTE)
        self.assertTrue(resultado.integro, resultado.motivo)
        self.assertEqual(resultado.total_linhas, 10)

    def test_quatro_processos_gravando_ao_mesmo_tempo(self):
        inicio = time.time() + 1.5
        processos = [
            subprocess.Popen(
                [sys.executable, '-c', SCRIPT_TRABALHADOR, str(self.caminho),
                 CHAVE_TESTE, str(numero), '40', str(inicio)],
                cwd=settings.BASE_DIR, stderr=subprocess.PIPE,
            )
            for numero in range(4)
        ]
        for processo in processos:
            _, erro = processo.communicate(timeout=60)
            self.assertEqual(processo.returncode, 0, erro.decode())

        resultado = verificar_arquivo(self.caminho, CHAVE_TESTE)
        self.assertTrue(
            resultado.integro,
            f'cadeia quebrou na linha {resultado.linha_com_problema}')
        # Nenhuma linha pode se perder na disputa.
        self.assertEqual(resultado.total_linhas, 160)

    def test_ultima_linha_maior_que_o_bloco_de_leitura(self):
        """A leitura do final do arquivo amplia o bloco quando a última
        linha é maior que ele, em vez de assinar em cima de uma linha
        cortada pela metade."""
        gravar_eventos(self.caminho, ['x' * 20000])
        gravar_eventos(self.caminho, ['depois da linha enorme'])
        resultado = verificar_arquivo(self.caminho, CHAVE_TESTE)
        self.assertTrue(resultado.integro, resultado.motivo)
        self.assertEqual(resultado.total_linhas, 2)

    def test_arquivo_de_trava_nao_entra_na_cadeia(self):
        """A trava é um arquivo ao lado do log, e não parte dele."""
        gravar_eventos(self.caminho, ['evento'])
        self.assertTrue(Path(f'{self.caminho}.lock').exists())
        resultado = verificar_arquivo(self.caminho, CHAVE_TESTE)
        self.assertEqual(resultado.total_linhas, 1)
