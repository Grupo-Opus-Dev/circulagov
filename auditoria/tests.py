import base64
import logging
import re
import subprocess
import sys
import tempfile
import time
from io import StringIO
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from .integridade import (
    HandlerLogIntegro, gerar_ancora, ler_ancoras, verificar_arquivo,
)

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


def gravar_como_em_producao(caminho, eventos, chave=CHAVE_TESTE):
    """Grava no formato real de LOGGING, com data, nivel e origem.

    Cria o registro e entrega direto ao handler, em vez de passar pelo
    logger "seguranca", que tambem escreveria no log de verdade.
    """
    handler = HandlerLogIntegro(caminho, chave)
    handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s %(name)s %(message)s'))
    for origem, nivel, mensagem in eventos:
        registro = logging.LogRecord(
            name=f'seguranca.{origem}', level=getattr(logging, nivel),
            pathname='', lineno=0, msg=mensagem, args=(), exc_info=None)
        handler.handle(registro)
    handler.close()


class ListaDeEventosTests(TestCase):
    """Os logs de autenticação, de falha e de 2FA (5.1 e 5.2) precisam
    poder ser vistos pelo front-end, e não só abrindo o arquivo."""

    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.caminho = Path(self.pasta.name) / 'seguranca.log'
        self.override = override_settings(
            LOG_DIR=Path(self.pasta.name), CHAVE_INTEGRIDADE_LOGS=CHAVE_TESTE)
        self.override.enable()
        self.url = reverse('auditoria:eventos')
        Usuario.objects.create_user(
            username='gestor', password='Senha@12345', is_staff=True)
        self.client.login(username='gestor', password='Senha@12345')

    def tearDown(self):
        self.override.disable()
        self.pasta.cleanup()

    def test_sem_login_vai_pro_login_da_aplicacao(self):
        resposta = Client().get(self.url)
        self.assertEqual(resposta.status_code, 302)
        self.assertTrue(resposta.url.startswith('/contas/login/'))

    def test_usuario_comum_recebe_403(self):
        Usuario.objects.create_user(username='comum', password='Senha@12345')
        comum = Client()
        comum.login(username='comum', password='Senha@12345')
        self.assertEqual(comum.get(self.url).status_code, 403)

    def test_mostra_os_eventos_do_arquivo(self):
        gravar_como_em_producao(self.caminho, [
            ('autenticacao', 'INFO', 'login com sucesso, username=ana'),
            ('autenticacao', 'WARNING', 'tentativa de login com falha, username=bruno'),
            ('dois_fatores', 'INFO', 'codigo 2FA correto, username=ana'),
        ])
        resposta = self.client.get(self.url)
        self.assertContains(resposta, 'login com sucesso, username=ana')
        self.assertContains(resposta, 'tentativa de login com falha, username=bruno')
        self.assertContains(resposta, 'codigo 2FA correto')
        self.assertContains(resposta, 'Dois fatores')

    def test_mais_recente_primeiro(self):
        gravar_como_em_producao(self.caminho, [
            ('autenticacao', 'INFO', 'primeiro evento'),
            ('autenticacao', 'INFO', 'segundo evento'),
            ('autenticacao', 'INFO', 'terceiro evento'),
        ])
        corpo = self.client.get(self.url).content.decode()
        self.assertLess(corpo.index('terceiro evento'), corpo.index('segundo evento'))
        self.assertLess(corpo.index('segundo evento'), corpo.index('primeiro evento'))

    def test_filtra_por_origem(self):
        gravar_como_em_producao(self.caminho, [
            ('autenticacao', 'INFO', 'evento de autenticacao'),
            ('dois_fatores', 'INFO', 'evento de dois fatores'),
        ])
        resposta = self.client.get(self.url, {'categoria': 'dois_fatores'})
        self.assertContains(resposta, 'evento de dois fatores')
        self.assertNotContains(resposta, 'evento de autenticacao')

    def test_filtra_por_nivel(self):
        gravar_como_em_producao(self.caminho, [
            ('autenticacao', 'INFO', 'tudo bem'),
            ('autenticacao', 'WARNING', 'algo suspeito'),
        ])
        resposta = self.client.get(self.url, {'nivel': 'WARNING'})
        self.assertContains(resposta, 'algo suspeito')
        self.assertNotContains(resposta, 'tudo bem')

    def test_busca_por_usuario(self):
        gravar_como_em_producao(self.caminho, [
            ('autenticacao', 'INFO', 'login com sucesso, username=ana'),
            ('autenticacao', 'INFO', 'login com sucesso, username=bruno'),
        ])
        resposta = self.client.get(self.url, {'busca': 'BRUNO'})
        self.assertContains(resposta, 'username=bruno')
        self.assertNotContains(resposta, 'username=ana')

    def test_filtro_inventado_na_url_nao_derruba_a_pagina(self):
        gravar_como_em_producao(self.caminho, [
            ('autenticacao', 'INFO', 'um evento')])
        resposta = self.client.get(
            self.url, {'categoria': 'nao_existe', 'nivel': 'XPTO', 'page': 'abc'})
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'um evento')

    def test_html_digitado_pelo_usuario_nao_e_executado(self):
        """O nome de usuário de uma tentativa falha vem do formulário de
        login, aberto a qualquer um. Aparece na tela do administrador, e
        não pode virar script."""
        gravar_como_em_producao(self.caminho, [
            ('autenticacao', 'WARNING',
             'tentativa de login com falha, username=<script>alert(1)</script>'),
        ])
        resposta = self.client.get(self.url)
        self.assertNotContains(resposta, '<script>alert(1)</script>')
        self.assertContains(resposta, '&lt;script&gt;alert(1)&lt;/script&gt;')

    def test_cadeia_integra_marca_todas_as_linhas(self):
        gravar_como_em_producao(self.caminho, [
            ('autenticacao', 'INFO', 'um'), ('autenticacao', 'INFO', 'dois')])
        resposta = self.client.get(self.url)
        self.assertContains(resposta, 'Cadeia íntegra')
        self.assertNotContains(resposta, 'depois da quebra')

    def test_log_adulterado_aparece_na_lista_e_marca_o_que_vem_depois(self):
        gravar_como_em_producao(self.caminho, [
            ('autenticacao', 'INFO', 'evento 1 evento'),
            ('autenticacao', 'INFO', 'evento 2 evento'),
            ('autenticacao', 'INFO', 'evento 3 evento'),
        ])
        linhas = self.caminho.read_text(encoding='utf-8').splitlines()
        linhas[1] = linhas[1].replace('evento 2', 'EVENTO 2')
        self.caminho.write_text('\n'.join(linhas) + '\n', encoding='utf-8')

        resposta = self.client.get(self.url)
        self.assertContains(resposta, 'Cadeia quebrada na linha 2')
        # A linha 1 continua confirmada. A 2 e a 3 nao.
        self.assertContains(resposta, 'Linha 1: confirmada pela cadeia')
        self.assertContains(resposta, 'Linha 2: depois da quebra')
        self.assertContains(resposta, 'Linha 3: depois da quebra')

    def test_linha_fora_do_formato_aparece_em_vez_de_sumir(self):
        gravar_como_em_producao(self.caminho, [
            ('autenticacao', 'INFO', 'normal')])
        with self.caminho.open('a', encoding='utf-8') as arquivo:
            arquivo.write('texto solto sem formato nenhum\n')
        resposta = self.client.get(self.url)
        self.assertContains(resposta, 'texto solto sem formato nenhum')
        self.assertContains(resposta, 'formato desconhecido')

    def test_sem_arquivo_de_log_mostra_aviso_em_vez_de_erro(self):
        resposta = self.client.get(self.url)
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'Nenhum evento registrado ainda')

    def test_pagina_os_eventos_e_mantem_os_filtros_nos_links(self):
        gravar_como_em_producao(self.caminho, [
            ('autenticacao', 'INFO', f'evento numero {i:03d}') for i in range(120)
        ])
        primeira = self.client.get(self.url, {'categoria': 'autenticacao'})
        self.assertEqual(len(primeira.context['pagina']), 50)
        # O link da proxima pagina nao pode perder o filtro.
        self.assertContains(primeira, 'categoria=autenticacao&amp;page=2')

        ultima = self.client.get(self.url, {'page': 3})
        self.assertEqual(len(ultima.context['pagina']), 20)
        self.assertContains(ultima, 'evento numero 000')

    def test_aviso_quando_o_arquivo_e_maior_que_o_limite_lido(self):
        gravar_como_em_producao(self.caminho, [
            ('autenticacao', 'INFO', f'evento {i}') for i in range(12)
        ])
        with mock.patch('auditoria.views.LIMITE_DE_LINHAS', 5):
            resposta = self.client.get(self.url)
        self.assertContains(resposta, 'Estão sendo lidas as últimas 5')
        self.assertEqual(resposta.context['lidos'], 5)


class TesteComentariosDeTemplate(SimpleTestCase):
    """O {# #} do Django so vale numa linha. Escrito em varias, o texto
    inteiro aparece na pagina, e ja aconteceu duas vezes. Comentario
    longo precisa de {% comment %}."""

    def test_nenhum_comentario_de_chaves_ocupa_mais_de_uma_linha(self):
        padrao = re.compile(r'\{#(?:(?!#\}).)*?\n(?:(?!#\}).)*?#\}', re.S)
        com_problema = []
        for caminho in Path(settings.BASE_DIR, 'templates').rglob('*.html'):
            texto = caminho.read_text(encoding='utf-8')
            for achado in padrao.finditer(texto):
                linha = texto.count('\n', 0, achado.start()) + 1
                com_problema.append(f'{caminho.name}:{linha}')
        self.assertEqual(com_problema, [])


class AncorasDoLogTests(TestCase):
    """A cadeia sozinha não detecta o corte do FINAL do log: o que sobra
    continua válido. A âncora, guardada fora, fecha essa lacuna."""

    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.caminho = Path(self.pasta.name) / 'seguranca.log'
        self.extra = Path(self.pasta.name) / 'copia-externa.txt'
        self.ancoras_local = Path(self.pasta.name) / 'ancoras.log'
        self.override = override_settings(
            LOG_DIR=Path(self.pasta.name), CHAVE_INTEGRIDADE_LOGS=CHAVE_TESTE)
        self.override.enable()
        gravar_eventos(self.caminho, [f'evento {n}' for n in range(1, 7)])

    def tearDown(self):
        self.override.disable()
        self.pasta.cleanup()

    def emitir(self, *argumentos):
        saida = StringIO()
        call_command('emitir_ancora', *argumentos, stdout=saida)
        return saida.getvalue()

    def linha_da_ancora(self):
        texto = self.ancoras_local.read_text(encoding='utf-8')
        return [l for l in texto.splitlines() if l.startswith('ancora ')][-1]

    def cortar_final(self, quantas):
        linhas = self.caminho.read_text(encoding='utf-8').splitlines()
        self.caminho.write_text(
            '\n'.join(linhas[:-quantas]) + '\n', encoding='utf-8')

    def test_sem_ancora_o_corte_do_final_passa_batido(self):
        """Limitação conhecida, registrada de propósito: sem âncora, o log
        cortado continua parecendo íntegro."""
        self.cortar_final(3)
        resultado = verificar_arquivo(self.caminho, CHAVE_TESTE)
        self.assertTrue(resultado.integro)

    def test_ancora_detecta_o_corte_do_final(self):
        self.emitir()
        self.cortar_final(3)
        with self.assertRaises(CommandError) as erro:
            call_command('verificar_logs', stdout=StringIO())
        self.assertIn('apagadas', str(erro.exception))

    def test_ancora_detecta_arquivo_apagado(self):
        self.emitir()
        self.caminho.unlink()
        with self.assertRaises(CommandError) as erro:
            call_command('verificar_logs', stdout=StringIO())
        self.assertIn('não existe', str(erro.exception))

    def test_ancora_detecta_log_reescrito_com_o_mesmo_tamanho(self):
        # Quem tem a chave reescreve a cadeia inteira, com o mesmo número
        # de linhas, e a cadeia fecha. A âncora de antes denuncia.
        self.emitir()
        self.caminho.unlink()
        gravar_eventos(self.caminho, [f'outro {n}' for n in range(1, 7)])
        with self.assertRaises(CommandError) as erro:
            call_command('verificar_logs', stdout=StringIO())
        self.assertIn('reescrito', str(erro.exception))

    def test_log_que_cresceu_depois_da_ancora_continua_valendo(self):
        self.emitir()
        gravar_eventos(self.caminho, ['evento 7', 'evento 8'])
        saida = StringIO()
        call_command('verificar_logs', stdout=saida)
        self.assertIn('1 âncora(s) conferida(s)', saida.getvalue())

    def test_copia_externa_funciona_mesmo_sem_o_arquivo_local(self):
        """O atacante apaga as âncoras do servidor junto com o final do
        log, mas a cópia que ficou fora ainda denuncia."""
        saida = self.emitir()
        self.extra.write_text(saida.splitlines()[0] + '\n', encoding='utf-8')
        self.ancoras_local.unlink()
        self.cortar_final(2)
        with self.assertRaises(CommandError):
            call_command(
                'verificar_logs', '--ancoras', str(self.extra),
                stdout=StringIO())

    def test_ancora_forjada_com_outra_chave_e_recusada(self):
        falsa = gerar_ancora(
            OUTRA_CHAVE, 6, 'a' * 64, '2026-01-01T00:00:00+00:00')
        self.ancoras_local.write_text(falsa + '\n', encoding='utf-8')
        with self.assertRaises(CommandError) as erro:
            call_command('verificar_logs', stdout=StringIO())
        self.assertIn('assinatura inválida', str(erro.exception))

    def test_ancora_com_numero_de_linhas_adulterado_e_recusada(self):
        self.emitir()
        self.ancoras_local.write_text(
            self.ancoras_local.read_text(encoding='utf-8').replace(
                'linhas=6', 'linhas=2'),
            encoding='utf-8')
        with self.assertRaises(CommandError):
            call_command('verificar_logs', stdout=StringIO())

    def test_apagar_so_a_ancora_do_servidor_nao_gera_alarme(self):
        """Limitação conhecida: o arquivo local está no mesmo servidor do
        log. É por isso que a cópia externa importa."""
        self.emitir()
        self.ancoras_local.unlink()
        self.cortar_final(3)
        saida = StringIO()
        call_command('verificar_logs', stdout=saida)
        self.assertIn('Nenhuma âncora conferida', saida.getvalue())

    def test_nao_emite_ancora_de_log_adulterado(self):
        linhas = self.caminho.read_text(encoding='utf-8').splitlines()
        linhas[1] = linhas[1].replace('evento', 'EVENTO')
        self.caminho.write_text('\n'.join(linhas) + '\n', encoding='utf-8')
        with self.assertRaises(CommandError):
            self.emitir()
        self.assertFalse(self.ancoras_local.exists())

    def test_nao_emite_ancora_de_log_vazio(self):
        self.caminho.unlink()
        with self.assertRaises(CommandError):
            self.emitir()

    def test_email_leva_a_ancora_pra_fora_do_servidor(self):
        self.emitir('--email', 'guardiao@exemplo.com')
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['guardiao@exemplo.com'])
        self.assertIn(self.linha_da_ancora(), mail.outbox[0].body)

    def test_ancora_nao_contem_a_chave(self):
        self.emitir()
        texto = self.linha_da_ancora()
        self.assertNotIn(CHAVE_TESTE, texto)
        self.assertNotIn(base64.b64decode(CHAVE_TESTE).decode(), texto)

    def test_ler_ancoras_ignora_comentarios_e_linhas_soltas(self):
        valida = gerar_ancora(
            CHAVE_TESTE, 3, 'b' * 64, '2026-01-01T00:00:00+00:00')
        ancoras, problemas = ler_ancoras(
            f'# minhas ancoras\n\n{valida}\nqualquer coisa\n', CHAVE_TESTE)
        self.assertEqual(len(ancoras), 1)
        self.assertEqual(problemas, [])

    def test_tela_mostra_o_corte_do_final(self):
        self.emitir()
        self.cortar_final(3)
        admin = Usuario.objects.create_user(
            username='admin_ancora', password='Senha@12345', is_staff=True)
        self.client.force_login(admin)
        for rota in ('auditoria:integridade', 'auditoria:eventos'):
            with self.subTest(rota=rota):
                resposta = self.client.get(reverse(rota))
                self.assertContains(resposta, 'apagadas')

    def test_tela_avisa_quando_nao_ha_ancora(self):
        admin = Usuario.objects.create_user(
            username='admin_sem', password='Senha@12345', is_staff=True)
        self.client.force_login(admin)
        resposta = self.client.get(reverse('auditoria:integridade'))
        self.assertContains(resposta, 'Nenhuma âncora conferida')
