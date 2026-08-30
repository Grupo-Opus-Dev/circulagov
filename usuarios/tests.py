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
