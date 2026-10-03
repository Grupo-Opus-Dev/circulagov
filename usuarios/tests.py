import time

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.core import mail
from django.test import Client, TestCase
from django.urls import reverse

from alunos.models import Aluno
from dois_fatores.models import DispositivoTOTP
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


class TesteEstadoDo2FANaTelaInicial(TestCase):
    """A tela inicial precisa refletir o estado real do 2FA. Oferecer
    "configurar" a quem já configurou leva a uma página que só avisa que
    já está ativado, o que confunde."""

    def setUp(self):
        self.senha = 'SenhaDeTeste123'
        self.usuario = Usuario.objects.create_user(
            username='usuario_teste', password=self.senha
        )
        self.client.login(username='usuario_teste', password=self.senha)

    def test_sem_2fa_a_tela_oferece_configurar(self):
        resposta = self.client.get(reverse('usuarios:inicio'))
        self.assertContains(resposta, 'Configurar autenticação de dois fatores')

    def test_com_2fa_ativo_a_tela_mostra_que_esta_ativo(self):
        DispositivoTOTP.objects.create(usuario=self.usuario, confirmado=True)
        resposta = self.client.get(reverse('usuarios:inicio'))
        self.assertContains(resposta, 'Autenticação de dois fatores ativa')
        self.assertNotContains(
            resposta, 'Configurar autenticação de dois fatores')

    def test_dispositivo_criado_mas_nao_confirmado_ainda_oferece_configurar(self):
        """Quem começou o cadastro e não terminou precisa poder voltar."""
        DispositivoTOTP.objects.create(usuario=self.usuario, confirmado=False)
        resposta = self.client.get(reverse('usuarios:inicio'))
        self.assertContains(resposta, 'Configurar autenticação de dois fatores')


class TesteAcessoAGestaoDeUsuarios(TestCase):
    """A área de gestão expõe dados de todos os usuários, então o
    controle de acesso dela é o que mais importa testar."""

    def setUp(self):
        self.senha = 'SenhaDeTeste123'
        self.comum = Usuario.objects.create_user(
            username='comum', password=self.senha)
        self.gestor = Usuario.objects.create_user(
            username='gestor', password=self.senha, is_staff=True)
        self.rotas = [
            reverse('usuarios:gestao_lista'),
            reverse('usuarios:gestao_novo'),
            reverse('usuarios:gestao_detalhe', args=[self.comum.id]),
        ]

    def test_sem_login_vai_pro_login_da_aplicacao(self):
        """Nao pro /admin/login/, que tem a aparencia do Django."""
        for rota in self.rotas:
            with self.subTest(rota=rota):
                resposta = self.client.get(rota)
                self.assertEqual(resposta.status_code, 302)
                self.assertTrue(resposta.url.startswith('/contas/login/'))

    def test_usuario_comum_recebe_403(self):
        """403, e nao redirecionamento: mandar quem ja esta logado pra
        tela de entrar nao resolve nada."""
        self.client.login(username='comum', password=self.senha)
        for rota in self.rotas:
            with self.subTest(rota=rota):
                self.assertEqual(self.client.get(rota).status_code, 403)

    def test_usuario_staff_entra(self):
        self.client.login(username='gestor', password=self.senha)
        for rota in self.rotas:
            with self.subTest(rota=rota):
                self.assertEqual(self.client.get(rota).status_code, 200)

    def test_atalho_na_tela_inicial_so_aparece_pra_staff(self):
        self.client.login(username='comum', password=self.senha)
        self.assertNotContains(
            self.client.get(reverse('usuarios:inicio')), 'Gerenciar usuários')

        self.client.login(username='gestor', password=self.senha)
        self.assertContains(
            self.client.get(reverse('usuarios:inicio')), 'Gerenciar usuários')


class TesteListaDeUsuarios(TestCase):
    def setUp(self):
        self.senha = 'SenhaDeTeste123'
        self.gestor = Usuario.objects.create_user(
            username='gestor', password=self.senha, is_staff=True)
        self.client.login(username='gestor', password=self.senha)

    def test_lista_mostra_os_usuarios(self):
        Usuario.objects.create_user(username='ana', password=self.senha)
        resposta = self.client.get(reverse('usuarios:gestao_lista'))
        self.assertContains(resposta, 'ana')
        self.assertContains(resposta, 'gestor')

    def test_busca_filtra_por_nome_de_usuario(self):
        Usuario.objects.create_user(username='ana', password=self.senha)
        Usuario.objects.create_user(username='bruno', password=self.senha)
        resposta = self.client.get(
            reverse('usuarios:gestao_lista'), {'busca': 'ana'})
        self.assertContains(resposta, 'ana')
        self.assertNotContains(resposta, 'bruno')

    def test_busca_encontra_pelo_ra_do_aluno(self):
        aluno = Usuario.objects.create_user(
            username='carla', password=self.senha, email='carla@escola.test')
        Aluno.objects.create(
            usuario=aluno, ra='RA-9988', nome_completo='Carla Souza')
        resposta = self.client.get(
            reverse('usuarios:gestao_lista'), {'busca': 'RA-9988'})
        self.assertContains(resposta, 'carla')

    def test_lista_nao_expoe_hash_de_senha(self):
        """Mesmo sendo tela de gestão, o hash não tem por que aparecer."""
        resposta = self.client.get(reverse('usuarios:gestao_lista'))
        self.assertNotContains(resposta, 'argon2')


class TesteCriacaoDeUsuario(TestCase):
    def setUp(self):
        self.senha = 'SenhaDeTeste123'
        self.gestor = Usuario.objects.create_user(
            username='gestor', password=self.senha, is_staff=True)
        self.client.login(username='gestor', password=self.senha)
        self.dados = {
            'username': 'novo_aluno',
            'email': 'novo@escola.test',
            'usable_password': 'true',
            'password1': 'SenhaForte!2026',
            'password2': 'SenhaForte!2026',
        }

    def test_cria_usuario_comum(self):
        self.client.post(reverse('usuarios:gestao_novo'), self.dados)
        criado = Usuario.objects.get(username='novo_aluno')
        self.assertEqual(criado.email, 'novo@escola.test')
        self.assertFalse(criado.is_staff)

    def test_senha_e_guardada_como_hash(self):
        self.client.post(reverse('usuarios:gestao_novo'), self.dados)
        criado = Usuario.objects.get(username='novo_aluno')
        self.assertNotEqual(criado.password, 'SenhaForte!2026')
        self.assertTrue(criado.check_password('SenhaForte!2026'))

    def test_senha_fraca_e_recusada(self):
        dados = self.dados | {'password1': '123456', 'password2': '123456'}
        self.client.post(reverse('usuarios:gestao_novo'), dados)
        self.assertFalse(Usuario.objects.filter(username='novo_aluno').exists())

    def test_ra_sem_nome_nao_cria_nada(self):
        dados = self.dados | {'ra': 'RA-1'}
        self.client.post(reverse('usuarios:gestao_novo'), dados)
        self.assertFalse(Usuario.objects.filter(username='novo_aluno').exists())

    def test_ra_e_nome_criam_o_aluno_junto(self):
        dados = self.dados | {'ra': 'RA-1234', 'nome_completo': 'Novo Aluno'}
        self.client.post(reverse('usuarios:gestao_novo'), dados)
        criado = Usuario.objects.get(username='novo_aluno')
        self.assertEqual(criado.aluno.ra, 'RA-1234')

    def test_ra_repetido_e_recusado(self):
        outro = Usuario.objects.create_user(
            username='outro', password=self.senha, email='outro@escola.test')
        Aluno.objects.create(
            usuario=outro, ra='RA-1234', nome_completo='Outro Aluno')

        dados = self.dados | {'ra': 'RA-1234', 'nome_completo': 'Novo Aluno'}
        self.client.post(reverse('usuarios:gestao_novo'), dados)
        self.assertFalse(Usuario.objects.filter(username='novo_aluno').exists())

    def test_criacao_de_usuario_vai_pro_log_de_seguranca(self):
        """Criar conta muda quem tem acesso ao sistema, então é evento
        de segurança e precisa ficar registrado com quem fez."""
        with self.assertLogs('seguranca.gestao', level='INFO') as registro:
            self.client.post(reverse('usuarios:gestao_novo'), self.dados)
        texto = '\n'.join(registro.output)
        self.assertIn('usuario criado', texto)
        self.assertIn('novo_aluno', texto)
        self.assertIn('criado_por=gestor', texto)


class TesteEdicaoDeUsuario(TestCase):
    def setUp(self):
        self.senha = 'SenhaDeTeste123'
        self.gestor = Usuario.objects.create_user(
            username='gestor', password=self.senha,
            email='gestor@escola.test', is_staff=True)
        self.alvo = Usuario.objects.create_user(
            username='alvo', password=self.senha, email='alvo@escola.test')
        self.client.login(username='gestor', password=self.senha)
        self.url = reverse('usuarios:gestao_editar', args=[self.alvo.id])

    def test_altera_email(self):
        self.client.post(self.url, {
            'email': 'novo@escola.test', 'is_active': 'on'})
        self.alvo.refresh_from_db()
        self.assertEqual(self.alvo.email, 'novo@escola.test')

    def test_promove_a_gestor(self):
        self.client.post(self.url, {
            'email': 'alvo@escola.test', 'is_staff': 'on', 'is_active': 'on'})
        self.alvo.refresh_from_db()
        self.assertTrue(self.alvo.is_staff)

    def test_desativar_impede_o_login(self):
        self.client.post(self.url, {'email': 'alvo@escola.test'})
        self.alvo.refresh_from_db()
        self.assertFalse(self.alvo.is_active)

        outro = Client()
        self.assertFalse(outro.login(username='alvo', password=self.senha))

    def test_email_nao_pode_ficar_vazio(self):
        """Sem e-mail a pessoa nao recupera a propria senha."""
        self.client.post(self.url, {'email': '', 'is_active': 'on'})
        self.alvo.refresh_from_db()
        self.assertEqual(self.alvo.email, 'alvo@escola.test')

    def test_vincula_aluno_na_edicao(self):
        self.client.post(self.url, {
            'email': 'alvo@escola.test', 'is_active': 'on',
            'ra': '55443322', 'nome_completo': 'Alvo Da Silva'})
        self.alvo.refresh_from_db()
        self.assertEqual(self.alvo.aluno.ra, '55443322')

    def test_nao_pode_remover_o_proprio_acesso_de_gestao(self):
        """Senao o sistema pode ficar sem administrador nenhum."""
        url = reverse('usuarios:gestao_editar', args=[self.gestor.id])
        self.client.post(url, {'email': 'gestor@escola.test', 'is_active': 'on'})
        self.gestor.refresh_from_db()
        self.assertTrue(self.gestor.is_staff)

    def test_nao_pode_desativar_a_propria_conta(self):
        url = reverse('usuarios:gestao_editar', args=[self.gestor.id])
        self.client.post(url, {'email': 'gestor@escola.test', 'is_staff': 'on'})
        self.gestor.refresh_from_db()
        self.assertTrue(self.gestor.is_active)

    def test_edicao_vai_pro_log_de_seguranca(self):
        with self.assertLogs('seguranca.gestao', level='INFO') as registro:
            self.client.post(self.url, {
                'email': 'novo@escola.test', 'is_active': 'on'})
        texto = chr(10).join(registro.output)
        self.assertIn('usuario alterado', texto)
        self.assertIn('alterado_por=gestor', texto)


class TesteSenhaPelaGestao(TestCase):
    def setUp(self):
        self.senha = 'SenhaDeTeste123'
        self.gestor = Usuario.objects.create_user(
            username='gestor', password=self.senha, is_staff=True)
        self.alvo = Usuario.objects.create_user(
            username='alvo', password=self.senha, email='alvo@escola.test')
        self.client.login(username='gestor', password=self.senha)

    def test_administrador_define_senha_nova(self):
        self.client.post(
            reverse('usuarios:gestao_definir_senha', args=[self.alvo.id]),
            {'new_password1': 'OutraSenha!2026',
             'new_password2': 'OutraSenha!2026'})
        self.alvo.refresh_from_db()
        self.assertTrue(self.alvo.check_password('OutraSenha!2026'))

    def test_senha_fraca_e_recusada(self):
        self.client.post(
            reverse('usuarios:gestao_definir_senha', args=[self.alvo.id]),
            {'new_password1': '123456', 'new_password2': '123456'})
        self.alvo.refresh_from_db()
        self.assertTrue(self.alvo.check_password(self.senha))

    def test_definir_senha_vai_pro_log(self):
        with self.assertLogs('seguranca.gestao', level='WARNING') as registro:
            self.client.post(
                reverse('usuarios:gestao_definir_senha', args=[self.alvo.id]),
                {'new_password1': 'OutraSenha!2026',
                 'new_password2': 'OutraSenha!2026'})
        self.assertIn('senha definida por administrador',
                      chr(10).join(registro.output))

    def test_envio_do_link_manda_email(self):
        self.client.post(
            reverse('usuarios:gestao_enviar_link_senha', args=[self.alvo.id]))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('alvo@escola.test', mail.outbox[0].to)

    def test_sem_email_cadastrado_nao_envia_nada(self):
        sem_email = Usuario.objects.create_user(
            username='sem_email', password=self.senha)
        self.client.post(
            reverse('usuarios:gestao_enviar_link_senha', args=[sem_email.id]))
        self.assertEqual(len(mail.outbox), 0)

    def test_envio_do_link_so_por_post(self):
        self.client.get(
            reverse('usuarios:gestao_enviar_link_senha', args=[self.alvo.id]))
        self.assertEqual(len(mail.outbox), 0)


class TesteRemocaoDoDoisFatores(TestCase):
    """Única saída de quem perdeu o aparelho com o app autenticador.
    Sem isto a conta fica inacessível para sempre."""

    def setUp(self):
        self.senha = 'SenhaDeTeste123'
        self.gestor = Usuario.objects.create_user(
            username='gestor', password=self.senha, is_staff=True)
        self.alvo = Usuario.objects.create_user(
            username='alvo', password=self.senha)
        self.client.login(username='gestor', password=self.senha)
        self.url = reverse('usuarios:gestao_remover_2fa', args=[self.alvo.id])

    def test_remove_o_dispositivo(self):
        DispositivoTOTP.objects.create(usuario=self.alvo, confirmado=True)
        self.client.post(self.url)
        self.assertFalse(
            DispositivoTOTP.objects.filter(usuario=self.alvo).exists())

    def test_remocao_vai_pro_log_como_aviso(self):
        """Reduz a proteção da conta, então precisa aparecer numa
        leitura rápida do log."""
        DispositivoTOTP.objects.create(usuario=self.alvo, confirmado=True)
        with self.assertLogs('seguranca.gestao', level='WARNING') as registro:
            self.client.post(self.url)
        texto = chr(10).join(registro.output)
        self.assertIn('2FA removido por administrador', texto)
        self.assertIn('removido_por=gestor', texto)

    def test_so_por_post(self):
        DispositivoTOTP.objects.create(usuario=self.alvo, confirmado=True)
        self.client.get(self.url)
        self.assertTrue(
            DispositivoTOTP.objects.filter(usuario=self.alvo).exists())

    def test_usuario_comum_nao_remove_2fa_de_ninguem(self):
        DispositivoTOTP.objects.create(usuario=self.alvo, confirmado=True)
        Usuario.objects.create_user(username='comum', password=self.senha)
        outro = Client()
        outro.login(username='comum', password=self.senha)
        self.assertEqual(outro.post(self.url).status_code, 403)
        self.assertTrue(
            DispositivoTOTP.objects.filter(usuario=self.alvo).exists())


class TesteTelaDeAuditoriaUsaOLoginDaAplicacao(TestCase):
    """A tela de integridade do log tinha o mesmo defeito das telas de
    gestão: mandava para o login do admin do Django."""

    def test_sem_login_vai_pro_login_da_aplicacao(self):
        resposta = self.client.get(reverse('auditoria:integridade'))
        self.assertTrue(resposta.url.startswith('/contas/login/'))

    def test_usuario_comum_recebe_403(self):
        Usuario.objects.create_user(
            username='comum', password='SenhaDeTeste123')
        self.client.login(username='comum', password='SenhaDeTeste123')
        self.assertEqual(
            self.client.get(reverse('auditoria:integridade')).status_code, 403)


class TesteCadastroComLinkDeSenha(TestCase):
    """No modo padrão a conta nasce sem senha utilizável e a pessoa
    recebe um link para criar a própria. Quem cadastra nunca conhece
    senha nenhuma."""

    def setUp(self):
        self.senha = 'SenhaDeTeste123'
        Usuario.objects.create_user(
            username='gestor', password=self.senha, is_staff=True)
        self.client.login(username='gestor', password=self.senha)
        self.dados = {
            'username': 'convidado',
            'email': 'convidado@escola.test',
            'usable_password': 'false',
        }

    def test_conta_nasce_sem_senha_utilizavel(self):
        self.client.post(reverse('usuarios:gestao_novo'), self.dados)
        criado = Usuario.objects.get(username='convidado')
        self.assertFalse(criado.has_usable_password())

    def test_nao_exige_digitar_senha(self):
        resposta = self.client.post(reverse('usuarios:gestao_novo'), self.dados)
        self.assertEqual(resposta.status_code, 302)
        self.assertTrue(Usuario.objects.filter(username='convidado').exists())

    def test_senha_digitada_e_ignorada_no_modo_de_link(self):
        """Se alguém preencher os campos e escolher o link, vale o link."""
        dados = self.dados | {
            'password1': 'IgnoradaAqui!2026', 'password2': 'IgnoradaAqui!2026'}
        self.client.post(reverse('usuarios:gestao_novo'), dados)
        criado = Usuario.objects.get(username='convidado')
        self.assertFalse(criado.has_usable_password())

    def test_envia_o_email_de_conta_criada(self):
        self.client.post(reverse('usuarios:gestao_novo'), self.dados)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['convidado@escola.test'])
        self.assertIn('sua conta foi criada', mail.outbox[0].subject)
        self.assertIn('convidado', mail.outbox[0].body)

    def test_nao_entra_antes_de_criar_a_senha(self):
        self.client.post(reverse('usuarios:gestao_novo'), self.dados)
        outro = Client()
        self.assertFalse(outro.login(username='convidado', password=''))

    def test_fluxo_completo_do_convite_ate_o_login(self):
        """Cadastro, e-mail, link, senha nova e login. Ponta a ponta."""
        self.client.post(reverse('usuarios:gestao_novo'), self.dados)

        corpo = mail.outbox[0].body
        caminho = corpo[corpo.index('/recuperar-senha/redefinir/'):].split()[0]

        pessoa = Client()
        pessoa.post(caminho, {
            'senha_nova': 'MinhaPropria!2026', 'confirmacao': 'MinhaPropria!2026'})

        self.assertTrue(
            pessoa.login(username='convidado', password='MinhaPropria!2026'))

    def test_criacao_por_link_fica_registrada_no_log(self):
        with self.assertLogs('seguranca.gestao', level='INFO') as registro:
            self.client.post(reverse('usuarios:gestao_novo'), self.dados)
        self.assertIn('senha=por_link', chr(10).join(registro.output))

    def test_perfil_mostra_que_aguarda_a_senha(self):
        self.client.post(reverse('usuarios:gestao_novo'), self.dados)
        criado = Usuario.objects.get(username='convidado')
        resposta = self.client.get(
            reverse('usuarios:gestao_detalhe', args=[criado.id]))
        self.assertContains(resposta, 'aguardando a pessoa criar pelo link')

    def test_falha_no_email_nao_esconde_o_problema(self):
        """A conta fica criada, mas a tela avisa que o e-mail falhou."""
        from unittest import mock
        from smtplib import SMTPException

        with mock.patch(
                'usuarios.views_gestao.enviar_email_recuperacao',
                side_effect=SMTPException('servidor fora')):
            resposta = self.client.post(
                reverse('usuarios:gestao_novo'), self.dados, follow=True)

        self.assertTrue(Usuario.objects.filter(username='convidado').exists())
        mensagens = [m.message for m in resposta.context['messages']]
        self.assertTrue(any('não pôde ser enviado' in m for m in mensagens))

    def test_modo_definir_agora_continua_exigindo_senha(self):
        dados = self.dados | {'usable_password': 'true'}
        self.client.post(reverse('usuarios:gestao_novo'), dados)
        self.assertFalse(Usuario.objects.filter(username='convidado').exists())

    def test_modo_definir_agora_nao_manda_email(self):
        dados = self.dados | {
            'usable_password': 'true',
            'password1': 'SenhaForte!2026', 'password2': 'SenhaForte!2026'}
        self.client.post(reverse('usuarios:gestao_novo'), dados)
        self.assertEqual(len(mail.outbox), 0)
        criado = Usuario.objects.get(username='convidado')
        self.assertTrue(criado.check_password('SenhaForte!2026'))
