import threading
import time
from datetime import datetime
from datetime import timezone as dt_timezone
from unittest import mock

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import Client, TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from . import cripto, qrcode_totp
from usuarios import contadores

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


class TesteQrCodeDeCadastro(TestCase):
    """Evidência do requisito 1.5: o cadastro do 2FA é feito pelo
    front-end, escaneando um QR code, sem precisar digitar o segredo."""

    def setUp(self):
        self.senha = 'SenhaDeTeste123'
        self.usuario = Usuario.objects.create_user(
            username='usuario_teste', password=self.senha
        )
        self.client.login(username='usuario_teste', password=self.senha)

    def test_tela_de_cadastro_mostra_um_qrcode(self):
        # O id identifica o contêiner do QR. Procurar só por "<svg"
        # casaria também com o logo do cabeçalho, em base.html.
        resposta = self.client.get(reverse('dois_fatores:cadastrar'))
        self.assertContains(resposta, 'id="qrcode-2fa"')

    def test_segredo_manual_continua_disponivel(self):
        """Quem não consegue escanear precisa do segredo em texto."""
        dispositivo = DispositivoTOTP.objects.create(usuario=self.usuario)
        resposta = self.client.get(reverse('dois_fatores:cadastrar'))
        self.assertContains(resposta, dispositivo.segredo)

    def test_svg_sai_pronto_pra_embutir_no_html(self):
        svg = qrcode_totp.gerar_svg('otpauth://totp/Teste:ana?secret=ABCDEFGH')
        self.assertTrue(svg.startswith('<svg'))
        self.assertNotIn('<?xml', svg)
        # Sem width e height fixos, quem manda no tamanho e o CSS.
        self.assertNotIn('width=', svg)
        self.assertNotIn('height=', svg)
        self.assertIn('viewBox', svg)

    def test_uris_diferentes_geram_qrcodes_diferentes(self):
        """Prova que o QR codifica mesmo a URI recebida, e não um
        desenho fixo."""
        um = qrcode_totp.gerar_svg('otpauth://totp/Teste:ana?secret=AAAAAAAA')
        outro = qrcode_totp.gerar_svg('otpauth://totp/Teste:bruno?secret=BBBBBBBB')
        self.assertNotEqual(um, outro)

    def test_qrcode_nao_aparece_depois_do_2fa_confirmado(self):
        """Com o 2FA já ativo, mostrar o segredo de novo seria exposição
        desnecessária."""
        dispositivo = DispositivoTOTP.objects.create(
            usuario=self.usuario, confirmado=True)
        resposta = self.client.get(reverse('dois_fatores:cadastrar'))
        self.assertNotContains(resposta, 'id="qrcode-2fa"')
        self.assertNotContains(resposta, dispositivo.segredo)


class TesteTravaDoSegundoFator(TestCase):
    """Com a senha certa, a pessoa chega na tela do código. Sem trava, dá
    pra tentar os 10^6 códigos possíveis, e a etapa não expirava nunca."""

    def setUp(self):
        self.senha = 'SenhaDeTeste123'
        self.usuario = Usuario.objects.create_user(
            username='com_2fa', password=self.senha)
        self.dispositivo = DispositivoTOTP.objects.create(
            usuario=self.usuario, confirmado=True)

    def _passar_pela_senha(self):
        resposta = self.client.post(
            reverse('login'),
            {'username': 'com_2fa', 'password': self.senha})
        self.assertRedirects(
            resposta, reverse('dois_fatores:verificar'),
            fetch_redirect_response=False)

    def _errar(self, vezes):
        for _ in range(vezes):
            self.client.post(
                reverse('dois_fatores:verificar'), {'codigo': '000000'})

    def _logado(self):
        return '_auth_user_id' in self.client.session

    def test_codigo_certo_entra(self):
        self._passar_pela_senha()
        self.client.post(
            reverse('dois_fatores:verificar'),
            {'codigo': self.dispositivo.totp().now()})
        self.assertTrue(self._logado())

    def test_depois_de_5_erros_nem_o_codigo_certo_entra(self):
        self._passar_pela_senha()
        self._errar(5)
        resposta = self.client.post(
            reverse('dois_fatores:verificar'),
            {'codigo': self.dispositivo.totp().now()})
        self.assertEqual(resposta.status_code, 200)
        self.assertFalse(self._logado())

    def test_o_bloqueio_vale_mesmo_passando_pela_senha_de_novo(self):
        self._passar_pela_senha()
        self._errar(5)
        self.client.logout()
        self._passar_pela_senha()
        self.client.post(
            reverse('dois_fatores:verificar'),
            {'codigo': self.dispositivo.totp().now()})
        self.assertFalse(self._logado())

    def test_tentativas_durante_o_bloqueio_nao_renovam_o_prazo(self):
        self._passar_pela_senha()
        self._errar(5)
        agora = time.time()
        for minuto in range(1, 11):
            with mock.patch('time.time', return_value=agora + minuto * 60):
                self._errar(3)
        # Mais de 15 minutos depois do bloqueio, dentro de uma etapa nova.
        with mock.patch('time.time', return_value=agora + 16 * 60):
            self.client.logout()
            self._passar_pela_senha()
            self.client.post(
                reverse('dois_fatores:verificar'),
                {'codigo': self.dispositivo.totp().now()})
            self.assertTrue(self._logado())

    def test_acerto_zera_a_contagem(self):
        self._passar_pela_senha()
        self._errar(4)
        self.client.post(
            reverse('dois_fatores:verificar'),
            {'codigo': self.dispositivo.totp().now()})
        self.assertTrue(self._logado())
        self.assertEqual(
            contadores.ler(f'tentativas_2fa_{self.usuario.pk}'), 0)

    def test_bloqueio_vai_pro_log(self):
        self._passar_pela_senha()
        self._errar(5)
        with self.assertLogs('seguranca.dois_fatores', level='WARNING') as logs:
            self._errar(1)
        self.assertIn('bloqueio por forca bruta no 2FA', ' '.join(logs.output))

    def test_etapa_do_codigo_expira(self):
        self._passar_pela_senha()
        with mock.patch('time.time', return_value=time.time() + 5 * 60 + 1):
            resposta = self.client.post(
                reverse('dois_fatores:verificar'),
                {'codigo': self.dispositivo.totp().now()})
        self.assertRedirects(
            resposta, reverse('login'), fetch_redirect_response=False)
        self.assertFalse(self._logado())

    def test_etapa_expirada_nao_volta_a_valer(self):
        self._passar_pela_senha()
        with mock.patch('time.time', return_value=time.time() + 5 * 60 + 1):
            self.client.get(reverse('dois_fatores:verificar'))
        resposta = self.client.get(reverse('dois_fatores:verificar'))
        self.assertRedirects(
            resposta, reverse('login'), fetch_redirect_response=False)

    def test_expiracao_vai_pro_log(self):
        self._passar_pela_senha()
        with mock.patch('time.time', return_value=time.time() + 5 * 60 + 1):
            with self.assertLogs(
                    'seguranca.dois_fatores', level='WARNING') as logs:
                self.client.get(reverse('dois_fatores:verificar'))
        self.assertIn('etapa do 2FA expirou', ' '.join(logs.output))

    def test_dentro_do_prazo_a_etapa_segue_valendo(self):
        self._passar_pela_senha()
        with mock.patch('time.time', return_value=time.time() + 4 * 60):
            resposta = self.client.get(reverse('dois_fatores:verificar'))
        self.assertEqual(resposta.status_code, 200)


class TesteCodigoDeUsoUnico(TestCase):
    """Um código TOTP vale uma vez só (RFC 6238, seção 5.2). Sem isso, quem
    visse ou interceptasse o código conseguiria usá-lo de novo dentro da
    janela de tolerância, de 30 a 90 segundos."""

    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            username='uso_unico', password='Senha@12345')
        self.dispositivo = DispositivoTOTP.objects.create(
            usuario=self.usuario, confirmado=True)
        self.gerador = self.dispositivo.totp()
        self.instante = self.gerador.timecode(timezone.now()) * 30 + 5

    def _no_instante(self, segundos):
        quando = datetime.fromtimestamp(segundos, tz=dt_timezone.utc)
        return mock.patch('dois_fatores.models.timezone.now', return_value=quando)

    def _codigo(self, segundos):
        return self.gerador.at(segundos)

    def _verificar(self, codigo, segundos):
        with self._no_instante(segundos):
            dispositivo = DispositivoTOTP.objects.get(pk=self.dispositivo.pk)
            return dispositivo.verificar_codigo(codigo)

    def test_o_mesmo_codigo_nao_vale_duas_vezes(self):
        codigo = self._codigo(self.instante)

        self.assertTrue(self._verificar(codigo, self.instante))
        self.assertFalse(self._verificar(codigo, self.instante + 1))

    def test_codigo_do_intervalo_seguinte_e_aceito(self):
        self.assertTrue(self._verificar(
            self._codigo(self.instante), self.instante))
        self.assertTrue(self._verificar(
            self._codigo(self.instante + 30), self.instante + 30))

    def test_codigo_mais_antigo_que_o_ultimo_aceito_e_recusado(self):
        """Quem tem um código anterior, ainda dentro da tolerância de
        relógio, não entra depois que um mais novo foi usado."""
        antigo = self._codigo(self.instante)
        novo = self._codigo(self.instante + 30)

        self.assertTrue(self._verificar(novo, self.instante + 30))
        self.assertFalse(self._verificar(antigo, self.instante + 30))

    def test_tolerancia_de_um_intervalo_continua_valendo(self):
        anterior = self._codigo(self.instante - 30)
        self.assertTrue(self._verificar(anterior, self.instante))

    def test_reuso_fica_registrado_no_log(self):
        codigo = self._codigo(self.instante)
        self._verificar(codigo, self.instante)

        with self.assertLogs('seguranca.dois_fatores', 'WARNING') as registro:
            self._verificar(codigo, self.instante)

        self.assertIn('codigo 2FA ja usado', registro.output[0])

    def test_reuso_pela_tela_de_login_nao_autentica(self):
        senha = 'Senha@12345'
        codigo = self._codigo(self.instante)
        with self._no_instante(self.instante):
            self.client.post(
                reverse('login'), {'username': 'uso_unico', 'password': senha})
            self.client.post(reverse('dois_fatores:verificar'), {'codigo': codigo})
        self.client.logout()

        outro = Client()
        with self._no_instante(self.instante + 2):
            outro.post(
                reverse('login'), {'username': 'uso_unico', 'password': senha})
            outro.post(reverse('dois_fatores:verificar'), {'codigo': codigo})
        resposta = outro.get(reverse('usuarios:inicio'))
        self.assertNotEqual(resposta.status_code, 200)


class TesteCodigoDeUsoUnicoEmParalelo(TransactionTestCase):
    """Duas requisições ao mesmo tempo com o mesmo código: só uma passa.
    Teste sequencial não provaria isso, por isso as threads."""

    def test_so_uma_de_varias_tentativas_simultaneas_passa(self):
        usuario = Usuario.objects.create_user(
            username='paralelo', password='Senha@12345')
        dispositivo = DispositivoTOTP.objects.create(
            usuario=usuario, confirmado=True)
        codigo = dispositivo.totp().now()
        largada = threading.Barrier(5)
        resultados = []

        def tentar():
            try:
                copia = DispositivoTOTP.objects.get(pk=dispositivo.pk)
                largada.wait()
                resultados.append(copia.verificar_codigo(codigo))
            finally:
                connection.close()

        threads = [threading.Thread(target=tentar) for _ in range(5)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual(sorted(resultados), [False, False, False, False, True])
