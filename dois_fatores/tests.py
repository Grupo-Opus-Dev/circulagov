from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import DispositivoTOTP

Usuario = get_user_model()


class TesteCadastroDoDispositivo(TestCase):
    """Evidência funcional do requisito 1.5: dá pra ativar o 2FA de verdade."""

    def setUp(self):
        self.senha = 'SenhaDeTeste123'
        self.usuario = Usuario.objects.create_user(
            username='usuario_teste', password=self.senha
        )
        self.client.login(username='usuario_teste', password=self.senha)

    def test_codigo_certo_confirma_o_dispositivo(self):
        dispositivo = DispositivoTOTP.objects.create(usuario=self.usuario)
        gerador_totp = dispositivo.totp()
        codigo = gerador_totp.now()

        self.client.post(reverse('dois_fatores:cadastrar'), {'codigo': codigo})

        dispositivo.refresh_from_db()
        self.assertTrue(dispositivo.confirmado)

    def test_codigo_errado_nao_confirma_o_dispositivo(self):
        dispositivo = DispositivoTOTP.objects.create(usuario=self.usuario)

        self.client.post(reverse('dois_fatores:cadastrar'), {'codigo': '000000'})

        dispositivo.refresh_from_db()
        self.assertFalse(dispositivo.confirmado)


class TesteLoginComDoisFatores(TestCase):
    """Evidência funcional do requisito 1.6: a senha sozinha não pode
    autenticar quem tem 2FA ativado - só depois do código certo."""

    def setUp(self):
        self.senha = 'SenhaDeTeste123'
        self.usuario = Usuario.objects.create_user(
            username='usuario_com_2fa', password=self.senha
        )
        self.dispositivo = DispositivoTOTP.objects.create(
            usuario=self.usuario, confirmado=True
        )

    def _codigo_atual(self):
        gerador_totp = self.dispositivo.totp()
        return gerador_totp.now()

    def test_senha_correta_sozinha_nao_autentica(self):
        self.client.post(
            reverse('login'),
            {'username': 'usuario_com_2fa', 'password': self.senha},
        )

        resposta = self.client.get(reverse('usuarios:inicio'))
        self.assertRedirects(resposta, f"{reverse('login')}?next={reverse('usuarios:inicio')}")

    def test_senha_e_codigo_certos_autenticam(self):
        self.client.post(
            reverse('login'),
            {'username': 'usuario_com_2fa', 'password': self.senha},
        )
        self.client.post(reverse('dois_fatores:verificar'), {'codigo': self._codigo_atual()})

        resposta = self.client.get(reverse('usuarios:inicio'))
        self.assertEqual(resposta.status_code, 200)

    def test_codigo_errado_nao_autentica(self):
        self.client.post(
            reverse('login'),
            {'username': 'usuario_com_2fa', 'password': self.senha},
        )
        self.client.post(reverse('dois_fatores:verificar'), {'codigo': '000000'})

        resposta = self.client.get(reverse('usuarios:inicio'))
        self.assertRedirects(resposta, f"{reverse('login')}?next={reverse('usuarios:inicio')}")

    def test_acessar_verificacao_sem_passar_pela_senha_e_recusado(self):
        resposta = self.client.post(
            reverse('dois_fatores:verificar'), {'codigo': self._codigo_atual()}
        )
        self.assertRedirects(resposta, reverse('login'))

    def test_login_com_2fa_tambem_grava_marca_de_inicio_da_sessao(self):
        """O sinal user_logged_in dispara igual, porque login() é chamado
        na hora certa (só depois do código) - não precisamos duplicar essa
        lógica aqui, ela já existe em usuarios/signals.py."""
        from usuarios.signals import CHAVE_INICIO_SESSAO

        self.client.post(
            reverse('login'),
            {'username': 'usuario_com_2fa', 'password': self.senha},
        )
        self.client.post(reverse('dois_fatores:verificar'), {'codigo': self._codigo_atual()})

        self.assertIn(CHAVE_INICIO_SESSAO, self.client.session)

    def test_usuario_sem_2fa_continua_autenticando_so_com_senha(self):
        Usuario.objects.create_user(username='usuario_sem_2fa', password=self.senha)

        self.client.post(
            reverse('login'),
            {'username': 'usuario_sem_2fa', 'password': self.senha},
        )

        resposta = self.client.get(reverse('usuarios:inicio'))
        self.assertEqual(resposta.status_code, 200)
