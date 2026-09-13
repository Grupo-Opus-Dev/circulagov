from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from django.urls import reverse

from .models import Consentimento, Finalidade, VERSAO_TERMOS_ATUAL

Usuario = get_user_model()


class ConsentimentoModelTests(TestCase):
    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            username='usuario_teste', password='Senha@123')

    def test_consentimento_guarda_finalidade_e_versao(self):
        c = Consentimento.objects.create(
            usuario=self.usuario, finalidade=Finalidade.CADASTRO)
        self.assertEqual(c.finalidade, Finalidade.CADASTRO)
        self.assertEqual(c.versao_termos, VERSAO_TERMOS_ATUAL)

    def test_consentimento_novo_comeca_ativo(self):
        c = Consentimento.objects.create(
            usuario=self.usuario, finalidade=Finalidade.CADASTRO)
        self.assertTrue(c.ativo)

    def test_revogar_marca_como_inativo(self):
        c = Consentimento.objects.create(
            usuario=self.usuario, finalidade=Finalidade.CADASTRO)
        c.revogar()
        self.assertFalse(c.ativo)
        self.assertIsNotNone(c.revogado_em)

    def test_nao_pode_ter_dois_consentimentos_ativos_pra_mesma_finalidade(self):
        Consentimento.objects.create(
            usuario=self.usuario, finalidade=Finalidade.CADASTRO)
        with self.assertRaises(Exception):
            Consentimento.objects.create(
                usuario=self.usuario, finalidade=Finalidade.CADASTRO)

    def test_pode_reaceitar_apos_revogar(self):
        primeiro = Consentimento.objects.create(
            usuario=self.usuario, finalidade=Finalidade.CADASTRO)
        primeiro.revogar()
        segundo = Consentimento.objects.create(
            usuario=self.usuario, finalidade=Finalidade.CADASTRO)
        self.assertTrue(segundo.ativo)
        self.assertEqual(
            Consentimento.objects.filter(
                usuario=self.usuario, finalidade=Finalidade.CADASTRO).count(), 2
        )

    def test_consentimento_registra_data_de_aceite_automaticamente(self):
        antes = timezone.now()
        c = Consentimento.objects.create(
            usuario=self.usuario, finalidade=Finalidade.CADASTRO)
        depois = timezone.now()
        self.assertIsNotNone(c.aceito_em)
        self.assertTrue(antes <= c.aceito_em <= depois)

    def test_consentimento_usa_versao_atual_dos_termos_por_padrao(self):
        c = Consentimento.objects.create(
            usuario=self.usuario, finalidade=Finalidade.CADASTRO)
        self.assertEqual(c.versao_termos, VERSAO_TERMOS_ATUAL)

    def test_consentimento_pode_guardar_versao_antiga_dos_termos(self):
        c = Consentimento.objects.create(
            usuario=self.usuario, finalidade=Finalidade.CADASTRO, versao_termos='0.9'
        )
        self.assertEqual(c.versao_termos, '0.9')


class GerenciarConsentimentoViewTests(TestCase):
    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            username='usuario_teste', password='Senha@123')
        self.client.force_login(self.usuario)

    def test_exige_login(self):
        self.client.logout()
        resposta = self.client.get(reverse('consentimento:gerenciar'))
        self.assertEqual(resposta.status_code, 302)

    def test_autorizar_finalidade_cria_consentimento(self):
        self.client.post(reverse('consentimento:gerenciar'),
                         {'finalidade': Finalidade.CADASTRO})
        self.assertTrue(
            Consentimento.objects.filter(
                usuario=self.usuario, finalidade=Finalidade.CADASTRO, revogado_em__isnull=True
            ).exists()
        )

    def test_autorizar_a_mesma_finalidade_duas_vezes_nao_duplica(self):
        self.client.post(reverse('consentimento:gerenciar'),
                         {'finalidade': Finalidade.CADASTRO})
        self.client.post(reverse('consentimento:gerenciar'),
                         {'finalidade': Finalidade.CADASTRO})
        self.assertEqual(
            Consentimento.objects.filter(
                usuario=self.usuario, finalidade=Finalidade.CADASTRO).count(), 1
        )

    def test_finalidade_invalida_nao_cria_nada(self):
        self.client.post(reverse('consentimento:gerenciar'),
                         {'finalidade': 'nao_existe'})
        self.assertFalse(Consentimento.objects.filter(
            usuario=self.usuario).exists())

    def test_revogar_marca_consentimento_como_inativo(self):
        c = Consentimento.objects.create(
            usuario=self.usuario, finalidade=Finalidade.CADASTRO)
        self.client.post(reverse('consentimento:revogar', args=[c.id]))
        c.refresh_from_db()
        self.assertFalse(c.ativo)

    def test_revogar_exige_login(self):
        c = Consentimento.objects.create(
            usuario=self.usuario, finalidade=Finalidade.CADASTRO)
        self.client.logout()
        resposta = self.client.post(
            reverse('consentimento:revogar', args=[c.id]))
        self.assertEqual(resposta.status_code, 302)

    def test_nao_pode_revogar_consentimento_de_outro_usuario(self):
        outro_usuario = Usuario.objects.create_user(
            username='outro_usuario', password='Senha@123')
        c_do_outro = Consentimento.objects.create(
            usuario=outro_usuario, finalidade=Finalidade.CADASTRO)
        resposta = self.client.post(
            reverse('consentimento:revogar', args=[c_do_outro.id]))
        self.assertEqual(resposta.status_code, 404)
        c_do_outro.refresh_from_db()
        self.assertTrue(c_do_outro.ativo)

    def test_revogar_via_get_nao_revoga(self):
        c = Consentimento.objects.create(
            usuario=self.usuario, finalidade=Finalidade.CADASTRO)
        self.client.get(reverse('consentimento:revogar', args=[c.id]))
        c.refresh_from_db()
        self.assertTrue(c.ativo)
