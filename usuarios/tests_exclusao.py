"""Superusuário só pode ser excluído por outro superusuário."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .exclusao import pode_excluir

Usuario = get_user_model()


class RegraDeExclusaoTests(TestCase):

    def setUp(self):
        self.admin = Usuario.objects.create_superuser(
            username='admin_um', password='Senha@123')
        self.outro_admin = Usuario.objects.create_superuser(
            username='admin_dois', password='Senha@123')
        self.gestor = Usuario.objects.create_user(
            username='gestor', password='Senha@123', is_staff=True)
        self.comum = Usuario.objects.create_user(
            username='comum', password='Senha@123')

    def test_superusuario_nao_se_exclui(self):
        self.assertFalse(pode_excluir(self.admin, self.admin))

    def test_outro_superusuario_pode_excluir(self):
        self.assertTrue(pode_excluir(self.admin, self.outro_admin))

    def test_gestor_nao_exclui_superusuario(self):
        self.assertFalse(pode_excluir(self.admin, self.gestor))

    def test_conta_comum_segue_a_regra_de_sempre(self):
        self.assertTrue(pode_excluir(self.comum, self.comum))
        self.assertTrue(pode_excluir(self.comum, self.admin))


class ExclusaoPeloAdminTests(TestCase):

    def setUp(self):
        self.admin = Usuario.objects.create_superuser(
            username='admin_um', password='Senha@123')
        self.outro_admin = Usuario.objects.create_superuser(
            username='admin_dois', password='Senha@123')
        self.client.force_login(self.admin)

    def _url_excluir(self, usuario):
        return reverse('admin:usuarios_usuario_delete', args=[usuario.pk])

    def test_superusuario_nao_se_exclui_pelo_admin(self):
        resposta = self.client.post(self._url_excluir(self.admin), {'post': 'yes'})
        self.assertEqual(resposta.status_code, 403)
        self.assertTrue(Usuario.objects.filter(pk=self.admin.pk).exists())

    def test_superusuario_exclui_outro_superusuario(self):
        self.client.post(self._url_excluir(self.outro_admin), {'post': 'yes'})
        self.assertFalse(Usuario.objects.filter(pk=self.outro_admin.pk).exists())

    def test_exclusao_em_lote_nao_inclui_a_propria_conta(self):
        self.client.post(reverse('admin:usuarios_usuario_changelist'), {
            'action': 'delete_selected',
            '_selected_action': [self.admin.pk, self.outro_admin.pk],
            'post': 'yes',
        })
        self.assertTrue(Usuario.objects.filter(pk=self.admin.pk).exists())
