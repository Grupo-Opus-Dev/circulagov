import time

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.test import TestCase
from django.urls import reverse

from usuarios.signals import CHAVE_INICIO_SESSAO

Usuario = get_user_model()


class TesteLoginELogout(TestCase):
    """Evidência funcional dos requisitos 1.9/1.10: sessão criada no login
    e realmente destruída no servidor quando o usuário sai."""

    def setUp(self):
        self.senha = 'SenhaDeTeste123'
        self.usuario = Usuario.objects.create_user(
            username='usuario_teste', password=self.senha
        )

    def test_pagina_inicial_exige_login(self):
        resposta = self.client.get(reverse('usuarios:inicio'))
        self.assertRedirects(
            resposta, f"{reverse('login')}?next={reverse('usuarios:inicio')}"
        )

    def test_login_cria_sessao_no_banco(self):
        self.client.login(username='usuario_teste', password=self.senha)
        chave = self.client.session.session_key
        sessoes_com_essa_chave = Session.objects.filter(session_key=chave)
        self.assertTrue(sessoes_com_essa_chave.exists())

    def test_logout_remove_sessao_do_banco(self):
        self.client.login(username='usuario_teste', password=self.senha)
        chave = self.client.session.session_key

        self.client.post(reverse('logout'))

        sessoes_com_essa_chave = Session.objects.filter(session_key=chave)
        self.assertFalse(sessoes_com_essa_chave.exists())

    def test_cookie_antigo_nao_reautentica_depois_do_logout(self):
        """Este é o teste que realmente prova o requisito 1.10: não basta a
        linha sumir do banco, o cookie que o usuário tinha guardado também
        precisa parar de funcionar."""
        self.client.login(username='usuario_teste', password=self.senha)
        chave_antiga = self.client.session.session_key

        self.client.post(reverse('logout'))

        self.client.cookies[settings.SESSION_COOKIE_NAME] = chave_antiga
        resposta = self.client.get(reverse('usuarios:inicio'))

        self.assertRedirects(
            resposta, f"{reverse('login')}?next={reverse('usuarios:inicio')}"
        )

    def test_logout_via_get_nao_faz_nada(self):
        """O LogoutView do Django 5.2 só aceita POST (http_method_names =
        ["post", "options"]). Um GET nem chega a rodar o logout."""
        self.client.login(username='usuario_teste', password=self.senha)
        chave = self.client.session.session_key

        resposta = self.client.get(reverse('logout'))

        self.assertEqual(resposta.status_code, 405)
        sessoes_com_essa_chave = Session.objects.filter(session_key=chave)
        self.assertTrue(sessoes_com_essa_chave.exists())


class TesteTimeoutDeSessao(TestCase):
    """Evidência funcional do requisito 1.9: a sessão precisa expirar depois
    de um tempo máximo, mesmo que o usuário esteja ativo o tempo todo."""

    def setUp(self):
        self.senha = 'SenhaDeTeste123'
        self.usuario = Usuario.objects.create_user(
            username='usuario_teste', password=self.senha
        )

    def test_login_grava_marca_de_inicio_da_sessao(self):
        self.client.login(username='usuario_teste', password=self.senha)
        self.assertIn(CHAVE_INICIO_SESSAO, self.client.session)

    def test_sessao_sem_marca_de_inicio_e_tratada_como_expirada(self):
        """Fail closed: se por algum motivo a marca não foi gravada, a
        sessão é tratada como inválida, não como "sem limite"."""
        self.client.login(username='usuario_teste', password=self.senha)
        sessao = self.client.session
        del sessao[CHAVE_INICIO_SESSAO]
        sessao.save()

        resposta = self.client.get(reverse('usuarios:inicio'))

        self.assertRedirects(resposta, reverse('login'))

    def test_sessao_expira_apos_tempo_maximo_mesmo_com_uso_continuo(self):
        self.client.login(username='usuario_teste', password=self.senha)
        sessao = self.client.session
        sessao[CHAVE_INICIO_SESSAO] = time.time() - (
            settings.TEMPO_MAXIMO_SESSAO_SEGUNDOS + 60
        )
        sessao.save()

        resposta = self.client.get(reverse('usuarios:inicio'))

        self.assertRedirects(resposta, reverse('login'))

    def test_sessao_dentro_do_tempo_maximo_continua_valida(self):
        self.client.login(username='usuario_teste', password=self.senha)
        sessao = self.client.session
        sessao[CHAVE_INICIO_SESSAO] = time.time() - (
            settings.TEMPO_MAXIMO_SESSAO_SEGUNDOS - 60
        )
        sessao.save()

        resposta = self.client.get(reverse('usuarios:inicio'))

        self.assertEqual(resposta.status_code, 200)


class TesteLogDeAutenticacao(TestCase):
    """Evidência funcional do requisito 5.1: login, logout e tentativa de
    login com falha precisam gerar log."""

    def setUp(self):
        self.senha = 'SenhaDeTeste123'
        self.usuario = Usuario.objects.create_user(
            username='usuario_log', password=self.senha
        )

    def test_login_com_sucesso_gera_log(self):
        with self.assertLogs('seguranca.autenticacao', level='INFO') as logs:
            self.client.post(
                reverse('login'), {'username': 'usuario_log', 'password': self.senha}
            )

        self.assertIn('login com sucesso', logs.output[0])
        self.assertIn('usuario_log', logs.output[0])

    def test_logout_gera_log(self):
        self.client.login(username='usuario_log', password=self.senha)

        with self.assertLogs('seguranca.autenticacao', level='INFO') as logs:
            self.client.post(reverse('logout'))

        self.assertIn('logout', logs.output[0])
        self.assertIn('usuario_log', logs.output[0])

    def test_login_com_senha_errada_gera_log_de_falha(self):
        with self.assertLogs('seguranca.autenticacao', level='WARNING') as logs:
            self.client.post(
                reverse('login'), {'username': 'usuario_log', 'password': 'senha_errada'}
            )

        self.assertIn('tentativa de login com falha', logs.output[0])
        self.assertIn('usuario_log', logs.output[0])

    def test_log_de_falha_nao_vaza_senha(self):
        with self.assertLogs('seguranca.autenticacao', level='WARNING') as logs:
            self.client.post(
                reverse('login'),
                {'username': 'usuario_log', 'password': 'SenhaSecreta@999'},
            )

        mensagens = ' '.join(logs.output)
        self.assertNotIn('SenhaSecreta@999', mensagens)


class TesteLogDeBloqueioPorForcaBruta(TestCase):
    """Evidência funcional do requisito 5.2: o bloqueio por força bruta
    (não só a tentativa de senha errada) também precisa gerar log."""

    def test_bloqueio_apos_limite_de_tentativas_gera_log(self):
        credenciais = {'username': 'usuario_bloqueado', 'password': 'senha_errada'}
        for _ in range(5):
            self.client.post(reverse('login'), credenciais)

        with self.assertLogs('seguranca.autenticacao', level='WARNING') as logs:
            self.client.post(reverse('login'), credenciais)

        # A 6a tentativa também aciona um "tentativa de login com falha"
        # (o form de bloqueio dispara a validação por baixo), então
        # conferimos que a linha de bloqueio está em algum lugar dos logs,
        # sem depender da posição exata.
        self.assertIn('bloqueio por forca bruta', ' '.join(logs.output))
