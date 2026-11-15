from io import StringIO

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase
from django.urls import reverse

from . import protecao
from .models import Aluno

Usuario = get_user_model()


class TesteCadastroDoAluno(TestCase):
    """Evidência funcional de que o Aluno tem só os dados definidos em
    docs/DADOS_PESSOAIS.md: RA, nome completo e e-mail institucional."""

    def test_aluno_com_email_institucional_e_criado_normalmente(self):
        usuario = Usuario.objects.create_user(
            username='12345678',
            password='SenhaDeTeste123',
            email='12345678@aluno.educacao.sp.gov.br',
        )
        aluno = Aluno.objects.create(
            usuario=usuario, ra='12345678', nome_completo='Maria da Silva'
        )

        self.assertEqual(aluno.ra, '12345678')
        self.assertEqual(str(aluno), 'Maria da Silva (RA 12345678)')

    def test_aluno_sem_email_institucional_nao_e_criado(self):
        usuario = Usuario.objects.create_user(
            username='87654321', password='SenhaDeTeste123'
        )

        with self.assertRaises(ValidationError):
            Aluno.objects.create(
                usuario=usuario, ra='87654321', nome_completo='João Souza'
            )

    def test_ra_repetido_nao_e_permitido(self):
        usuario_1 = Usuario.objects.create_user(
            username='11111111',
            password='SenhaDeTeste123',
            email='11111111@aluno.educacao.sp.gov.br',
        )
        Aluno.objects.create(usuario=usuario_1, ra='11111111', nome_completo='Aluno Um')

        usuario_2 = Usuario.objects.create_user(
            username='outro_usuario',
            password='SenhaDeTeste123',
            email='11111111-outro@aluno.educacao.sp.gov.br',
        )
        with self.assertRaises(ValidationError):
            Aluno.objects.create(usuario=usuario_2, ra='11111111', nome_completo='Aluno Dois')


class TesteLoginDoAlunoComRA(TestCase):
    """Evidência de que o aluno entra pela tela de login normal, digitando
    o RA no campo de usuário, sem nenhuma tela nova."""

    def setUp(self):
        self.senha = 'SenhaDeTeste123'
        self.usuario = Usuario.objects.create_user(
            username='99998888',
            password=self.senha,
            email='99998888@aluno.educacao.sp.gov.br',
        )
        Aluno.objects.create(
            usuario=self.usuario, ra='99998888', nome_completo='Aluno Teste'
        )

    def test_login_com_ra_e_senha_funciona(self):
        self.client.post(
            reverse('login'), {'username': '99998888', 'password': self.senha}
        )

        resposta = self.client.get(reverse('usuarios:inicio'))
        self.assertEqual(resposta.status_code, 200)


class TesteRACifradoEmRepouso(TestCase):
    """Evidência do requisito 3.4: o RA não fica em texto puro no banco,
    mas o sistema continua lendo, buscando e garantindo que ele é único."""

    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            username='aluno_cifrado',
            password='SenhaDeTeste123',
            email='cifrado@aluno.educacao.sp.gov.br',
        )
        self.aluno = Aluno.objects.create(
            usuario=self.usuario, ra='000123456789',
            nome_completo='Aluno Cifrado')

    def test_ra_nao_aparece_em_texto_puro_na_tabela(self):
        with connection.cursor() as cursor:
            cursor.execute('SELECT * FROM alunos_aluno')
            linhas = cursor.fetchall()

        conteudo = b''.join(
            bytes(valor) if isinstance(valor, (bytes, memoryview))
            else str(valor).encode() for linha in linhas for valor in linha)
        self.assertNotIn(b'000123456789', conteudo)

    def test_dumpdata_mostra_o_ra_cifrado(self):
        saida = StringIO()
        call_command('dumpdata', 'alunos', stdout=saida)

        self.assertNotIn('000123456789', saida.getvalue())
        self.assertIn('ra_cifrado', saida.getvalue())

    def test_ra_e_lido_normalmente_depois_de_gravado(self):
        recarregado = Aluno.objects.get(pk=self.aluno.pk)
        self.assertEqual(recarregado.ra, '000123456789')

    def test_busca_pelo_ra_completo_encontra(self):
        self.assertEqual(
            Aluno.objects.com_ra('000123456789').get(), self.aluno)
        self.assertEqual(
            Aluno.objects.com_ra('  000123456789 ').get(), self.aluno)

    def test_busca_por_parte_do_ra_nao_encontra(self):
        self.assertFalse(Aluno.objects.com_ra('0001234').exists())

    def test_mesmo_ra_cifrado_duas_vezes_da_valores_diferentes(self):
        """Nonce novo a cada gravação: dois alunos com RA parecido não
        ficam com o mesmo valor cifrado, o que revelaria a coincidência."""
        primeiro = bytes(self.aluno.ra_cifrado)
        self.aluno.ra = '000123456789'
        self.assertNotEqual(primeiro, bytes(self.aluno.ra_cifrado))

    def test_ra_cifrado_nao_decifra_em_outro_contexto(self):
        """O RA cifrado não pode ser colado no lugar do segredo do 2FA."""
        from cryptography.exceptions import InvalidTag

        from dois_fatores import cripto

        with self.assertRaises(InvalidTag):
            cripto.decifrar(bytes(self.aluno.ra_cifrado))

    def test_ra_vazio_nao_e_aceito(self):
        outro = Usuario.objects.create_user(
            username='sem_ra', password='SenhaDeTeste123',
            email='semra@aluno.educacao.sp.gov.br')
        with self.assertRaises(ValidationError):
            Aluno.objects.create(usuario=outro, ra='  ', nome_completo='Sem RA')

    def test_ra_longo_demais_nao_e_aceito(self):
        outro = Usuario.objects.create_user(
            username='ra_longo', password='SenhaDeTeste123',
            email='longo@aluno.educacao.sp.gov.br')
        with self.assertRaises(ValidationError):
            Aluno.objects.create(
                usuario=outro, ra='1' * 21, nome_completo='RA Longo')


class TesteMigracaoQueCifraORA(TransactionTestCase):
    """A migração 0002 cifra o RA de quem já estava cadastrado e a volta
    devolve o texto original."""

    antes = [('alunos', '0001_initial')]
    depois = [('alunos', '0002_ra_cifrado')]

    def tearDown(self):
        MigrationExecutor(connection).migrate(
            MigrationExecutor(connection).loader.graph.leaf_nodes())

    def _migrar(self, alvo):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(alvo)
        return executor.loader.project_state(alvo).apps

    def test_aluno_existente_tem_o_ra_cifrado_e_volta_igual(self):
        apps = self._migrar(self.antes)
        UsuarioAntigo = apps.get_model('usuarios', 'Usuario')
        AlunoAntigo = apps.get_model('alunos', 'Aluno')
        usuario = UsuarioAntigo.objects.create(
            username='antigo', email='antigo@aluno.educacao.sp.gov.br')
        AlunoAntigo.objects.create(
            usuario=usuario, ra='55554444', nome_completo='Aluno Antigo')

        apps = self._migrar(self.depois)
        AlunoNovo = apps.get_model('alunos', 'Aluno')
        migrado = AlunoNovo.objects.get(usuario_id=usuario.pk)
        self.assertNotIn(b'55554444', bytes(migrado.ra_cifrado))
        self.assertEqual(protecao.decifrar(migrado.ra_cifrado), '55554444')
        self.assertEqual(migrado.ra_indice, protecao.indice('55554444'))

        apps = self._migrar(self.antes)
        AlunoAntigo = apps.get_model('alunos', 'Aluno')
        self.assertEqual(
            AlunoAntigo.objects.get(usuario_id=usuario.pk).ra, '55554444')


class TesteFormularioDoAdmin(TestCase):
    """O admin não enxerga o RA como campo do model, então o formulário
    dele precisa gravar pela propriedade e recusar RA repetido."""

    def _usuario(self, nome):
        return Usuario.objects.create_user(
            username=nome, password='SenhaDeTeste123',
            email=f'{nome}@aluno.educacao.sp.gov.br')

    def test_cria_aluno_com_ra_cifrado(self):
        from .admin import FormularioAlunoAdmin

        form = FormularioAlunoAdmin(data={
            'usuario': self._usuario('pelo_admin').pk,
            'ra': '7777', 'nome_completo': 'Pelo Admin'})
        self.assertTrue(form.is_valid(), form.errors)
        aluno = form.save()
        self.assertEqual(Aluno.objects.get(pk=aluno.pk).ra, '7777')

    def test_recusa_ra_repetido(self):
        from .admin import FormularioAlunoAdmin

        Aluno.objects.create(
            usuario=self._usuario('primeiro'), ra='8888',
            nome_completo='Primeiro')
        form = FormularioAlunoAdmin(data={
            'usuario': self._usuario('segundo').pk,
            'ra': '8888', 'nome_completo': 'Segundo'})
        self.assertFalse(form.is_valid())
        self.assertIn('ra', form.errors)
