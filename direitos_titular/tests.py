import json
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from alunos.models import Aluno
from consentimento.models import Consentimento, Finalidade

Usuario = get_user_model()


class ConsultarDadosViewTests(TestCase):
    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            username='usuario_teste', password='Senha@123', email='teste@exemplo.com'
        )
        self.client.force_login(self.usuario)

    def test_exige_login(self):
        self.client.logout()
        resposta = self.client.get(reverse('direitos_titular:consultar'))
        self.assertEqual(resposta.status_code, 302)

    def test_mostra_dados_cadastrais_do_usuario(self):
        resposta = self.client.get(reverse('direitos_titular:consultar'))
        self.assertContains(resposta, 'usuario_teste')
        self.assertContains(resposta, 'teste@exemplo.com')

    def test_mostra_dados_de_aluno_quando_existir(self):
        Aluno.objects.create(usuario=self.usuario,
                             ra='123456', nome_completo='Aluno Teste')
        resposta = self.client.get(reverse('direitos_titular:consultar'))
        self.assertContains(resposta, '123456')
        self.assertContains(resposta, 'Aluno Teste')

    def test_nao_mostra_dados_de_aluno_quando_usuario_nao_e_aluno(self):
        resposta = self.client.get(reverse('direitos_titular:consultar'))
        self.assertNotContains(resposta, 'RA')

    def test_mostra_consentimentos_do_usuario(self):
        Consentimento.objects.create(
            usuario=self.usuario, finalidade=Finalidade.CADASTRO)
        resposta = self.client.get(reverse('direitos_titular:consultar'))
        self.assertContains(resposta, 'Cadastro e autenticação na plataforma')

    def test_nao_mostra_dados_de_outro_usuario(self):
        outro_usuario = Usuario.objects.create_user(
            username='outro_usuario', password='Senha@123', email='outro@exemplo.com'
        )
        Aluno.objects.create(usuario=outro_usuario,
                             ra='999999', nome_completo='Outro Aluno')
        resposta = self.client.get(reverse('direitos_titular:consultar'))
        self.assertNotContains(resposta, '999999')
        self.assertNotContains(resposta, 'Outro Aluno')


class ExportarDadosViewTests(TestCase):
    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            username='usuario_teste', password='Senha@123', email='teste@exemplo.com'
        )
        self.client.force_login(self.usuario)

    def test_exige_login(self):
        self.client.logout()
        resposta = self.client.get(reverse('direitos_titular:exportar'))
        self.assertEqual(resposta.status_code, 302)

    def test_resposta_e_um_arquivo_para_download(self):
        resposta = self.client.get(reverse('direitos_titular:exportar'))
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta['Content-Type'], 'application/json')
        self.assertIn('attachment', resposta['Content-Disposition'])

    def test_json_contem_dados_do_usuario(self):
        resposta = self.client.get(reverse('direitos_titular:exportar'))
        conteudo = json.loads(resposta.content)
        self.assertEqual(conteudo['dados_pessoais']
                         ['Nome de usuário'], 'usuario_teste')

    def test_json_contem_consentimentos_do_usuario(self):
        Consentimento.objects.create(
            usuario=self.usuario, finalidade=Finalidade.CADASTRO)
        resposta = self.client.get(reverse('direitos_titular:exportar'))
        conteudo = json.loads(resposta.content)
        self.assertEqual(len(conteudo['consentimentos']), 1)
        self.assertEqual(
            conteudo['consentimentos'][0]['finalidade'], 'Cadastro e autenticação na plataforma'
        )

    def test_nao_exporta_dados_de_outro_usuario(self):
        outro_usuario = Usuario.objects.create_user(
            username='outro_usuario', password='Senha@123', email='outro@exemplo.com'
        )
        Consentimento.objects.create(
            usuario=outro_usuario, finalidade=Finalidade.CADASTRO)
        resposta = self.client.get(reverse('direitos_titular:exportar'))
        conteudo = json.loads(resposta.content)
        self.assertEqual(len(conteudo['consentimentos']), 0)


class ExcluirDadosViewTests(TestCase):
    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            username='usuario_teste', password='Senha@123', email='teste@exemplo.com'
        )
        self.client.force_login(self.usuario)

    def test_exige_login(self):
        self.client.logout()
        resposta = self.client.post(reverse('direitos_titular:excluir'))
        self.assertEqual(resposta.status_code, 302)

    def test_get_nao_exclui_mostra_redireciona_para_confirmacao(self):
        resposta = self.client.get(reverse('direitos_titular:excluir'))
        self.assertRedirects(resposta, reverse(
            'direitos_titular:confirmar_exclusao'))
        self.assertTrue(Usuario.objects.filter(id=self.usuario.id).exists())

    def test_post_exclui_o_usuario(self):
        usuario_id = self.usuario.id
        self.client.post(reverse('direitos_titular:excluir'))
        self.assertFalse(Usuario.objects.filter(id=usuario_id).exists())

    def test_excluir_apaga_aluno_vinculado(self):
        Aluno.objects.create(usuario=self.usuario,
                             ra='123456', nome_completo='Aluno Teste')
        self.client.post(reverse('direitos_titular:excluir'))
        self.assertFalse(Aluno.objects.filter(ra='123456').exists())

    def test_excluir_apaga_consentimentos(self):
        Consentimento.objects.create(
            usuario=self.usuario, finalidade=Finalidade.CADASTRO)
        self.client.post(reverse('direitos_titular:excluir'))
        self.assertEqual(Consentimento.objects.count(), 0)

    def test_apos_excluir_usuario_e_deslogado(self):
        self.client.post(reverse('direitos_titular:excluir'))
        resposta = self.client.get(reverse('direitos_titular:consultar'))
        self.assertEqual(resposta.status_code, 302)

    def test_confirmar_exclusao_exige_login(self):
        self.client.logout()
        resposta = self.client.get(
            reverse('direitos_titular:confirmar_exclusao'))
        self.assertEqual(resposta.status_code, 302)
