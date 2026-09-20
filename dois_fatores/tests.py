from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from . import cripto
from .models import DispositivoTOTP

Usuario = get_user_model()


class TesteCifragemDoSegredo(TestCase):
    """Evidência funcional de que o segredo TOTP não fica em texto puro
    no banco, e de que a cifragem detecta adulteração."""

    def test_cifrar_e_decifrar_devolve_o_valor_original(self):
        original = b'segredo-de-teste'
        cifrado = cripto.cifrar(original)
        self.assertEqual(cripto.decifrar(cifrado), original)

    def test_valor_cifrado_e_diferente_do_original(self):
        original = b'segredo-de-teste'
        cifrado = cripto.cifrar(original)
        self.assertNotIn(original, cifrado)

    def test_adulterar_o_cifrado_impede_a_decifragem(self):
        """O AES-GCM é autenticado: qualquer byte alterado no texto
        cifrado faz a decifragem falhar, em vez de devolver lixo."""
        cifrado = bytearray(cripto.cifrar(b'segredo-de-teste'))
        cifrado[-1] ^= 0xFF
        with self.assertRaises(Exception):
            cripto.decifrar(bytes(cifrado))

    def test_dispositivo_gera_segredo_cifrado_automaticamente(self):
        usuario = Usuario.objects.create_user(username='usuario_cripto', password='SenhaDeTeste123')
        dispositivo = DispositivoTOTP.objects.create(usuario=usuario)

        self.assertNotEqual(bytes(dispositivo.segredo_cifrado), b'')
        self.assertNotIn(dispositivo.segredo.encode(), bytes(dispositivo.segredo_cifrado))


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


class TesteLogDeEventosDoisFatores(TestCase):
    """Evidência funcional do requisito 5.2: ativação do 2FA, código certo
    e código errado precisam gerar log, tanto no cadastro quanto no login."""

    def setUp(self):
        self.senha = 'SenhaDeTeste123'
        self.usuario = Usuario.objects.create_user(
            username='usuario_log_2fa', password=self.senha
        )
        self.client.login(username='usuario_log_2fa', password=self.senha)

    def test_ativar_2fa_com_codigo_certo_gera_log_de_codigo_correto_e_de_ativacao(self):
        dispositivo = DispositivoTOTP.objects.create(usuario=self.usuario)
        codigo = dispositivo.totp().now()

        with self.assertLogs('seguranca.dois_fatores', level='INFO') as logs:
            self.client.post(reverse('dois_fatores:cadastrar'), {'codigo': codigo})

        mensagens = ' '.join(logs.output)
        self.assertIn('codigo 2FA correto', mensagens)
        self.assertIn('2FA ativado', mensagens)

    def test_cadastrar_com_codigo_errado_gera_log_de_codigo_incorreto(self):
        DispositivoTOTP.objects.create(usuario=self.usuario)

        with self.assertLogs('seguranca.dois_fatores', level='WARNING') as logs:
            self.client.post(reverse('dois_fatores:cadastrar'), {'codigo': '000000'})

        self.assertIn('codigo 2FA incorreto', logs.output[0])

    def test_verificar_no_login_com_codigo_certo_gera_log(self):
        dispositivo = DispositivoTOTP.objects.create(usuario=self.usuario, confirmado=True)
        self.client.post(reverse('logout'))
        self.client.post(
            reverse('login'), {'username': 'usuario_log_2fa', 'password': self.senha}
        )

        with self.assertLogs('seguranca.dois_fatores', level='INFO') as logs:
            self.client.post(
                reverse('dois_fatores:verificar'), {'codigo': dispositivo.totp().now()}
            )

        self.assertIn('codigo 2FA correto', logs.output[0])

    def test_verificar_no_login_com_codigo_errado_gera_log(self):
        DispositivoTOTP.objects.create(usuario=self.usuario, confirmado=True)
        self.client.post(reverse('logout'))
        self.client.post(
            reverse('login'), {'username': 'usuario_log_2fa', 'password': self.senha}
        )

        with self.assertLogs('seguranca.dois_fatores', level='WARNING') as logs:
            self.client.post(reverse('dois_fatores:verificar'), {'codigo': '000000'})

        self.assertIn('codigo 2FA incorreto', logs.output[0])
