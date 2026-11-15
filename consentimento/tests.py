from django.contrib.auth import get_user_model
from django.core import mail
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
            usuario=self.usuario, finalidade=Finalidade.COMUNICACOES)
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


class EfeitoDaRevogacaoTests(TestCase):
    """Parecer da v1.5.1, item 4: a revogação precisa ter efeito sobre
    cada finalidade, e não só registrar a data."""

    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            username='titular', password='Senha@123',
            email='titular@escola.test')
        self.client.force_login(self.usuario)

    def test_revogar_cadastro_leva_para_a_confirmacao_da_exclusao(self):
        c = Consentimento.objects.create(
            usuario=self.usuario, finalidade=Finalidade.CADASTRO)

        resposta = self.client.post(
            reverse('consentimento:revogar', args=[c.id]), follow=True)

        self.assertRedirects(
            resposta, reverse('direitos_titular:confirmar_exclusao'))
        self.assertContains(resposta, 'confirme a exclusão da conta')

    def test_revogar_cadastro_sem_confirmar_nao_revoga_nem_exclui(self):
        c = Consentimento.objects.create(
            usuario=self.usuario, finalidade=Finalidade.CADASTRO)

        self.client.post(reverse('consentimento:revogar', args=[c.id]))

        c.refresh_from_db()
        self.assertTrue(c.ativo)
        self.assertTrue(Usuario.objects.filter(pk=self.usuario.pk).exists())

    def test_confirmar_a_exclusao_apaga_conta_e_consentimentos(self):
        Consentimento.objects.create(
            usuario=self.usuario, finalidade=Finalidade.CADASTRO)

        self.client.post(reverse('direitos_titular:excluir'))

        self.assertFalse(Usuario.objects.filter(pk=self.usuario.pk).exists())
        self.assertFalse(Consentimento.objects.exists())

    def test_com_consentimento_a_comunicacao_e_enviada(self):
        from .comunicacoes import enviar_comunicacao

        Consentimento.objects.create(
            usuario=self.usuario, finalidade=Finalidade.COMUNICACOES)

        self.assertTrue(enviar_comunicacao(self.usuario, 'Aviso', 'Texto'))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['titular@escola.test'])

    def test_sem_consentimento_a_comunicacao_nao_e_enviada(self):
        from .comunicacoes import enviar_comunicacao

        self.assertFalse(enviar_comunicacao(self.usuario, 'Aviso', 'Texto'))
        self.assertEqual(len(mail.outbox), 0)

    def test_depois_de_revogar_comunicacoes_nada_mais_e_enviado(self):
        from .comunicacoes import enviar_comunicacao

        c = Consentimento.objects.create(
            usuario=self.usuario, finalidade=Finalidade.COMUNICACOES)
        self.assertTrue(enviar_comunicacao(self.usuario, 'Antes', 'Texto'))

        self.client.post(reverse('consentimento:revogar', args=[c.id]))

        self.assertFalse(enviar_comunicacao(self.usuario, 'Depois', 'Texto'))
        self.assertEqual([m.subject for m in mail.outbox], ['Antes'])

    def test_reaceitar_comunicacoes_volta_a_permitir_o_envio(self):
        from .comunicacoes import enviar_comunicacao

        c = Consentimento.objects.create(
            usuario=self.usuario, finalidade=Finalidade.COMUNICACOES)
        c.revogar()
        self.client.post(
            reverse('consentimento:gerenciar'),
            {'finalidade': Finalidade.COMUNICACOES})

        self.assertTrue(enviar_comunicacao(self.usuario, 'De novo', 'Texto'))

    def test_comunicacao_sem_email_cadastrado_nao_e_enviada(self):
        from .comunicacoes import enviar_comunicacao

        self.usuario.email = ''
        self.usuario.save()
        Consentimento.objects.create(
            usuario=self.usuario, finalidade=Finalidade.COMUNICACOES)

        self.assertFalse(enviar_comunicacao(self.usuario, 'Aviso', 'Texto'))
