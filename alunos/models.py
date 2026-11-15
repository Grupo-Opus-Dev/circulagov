from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from . import protecao


# O mesmo limite do campo de texto que existia antes da cifragem.
TAMANHO_MAXIMO_RA = 20


class AlunoQuerySet(models.QuerySet):
    def com_ra(self, ra):
        """Busca pelo RA exato. O RA fica cifrado no banco, então a busca
        compara o índice, e não dá para buscar por parte do RA."""
        return self.filter(ra_indice=protecao.indice(ra))


class Aluno(models.Model):
    """Aluno da rede pública estadual de SP.

    Guarda o RA e o nome completo, e é ligado a uma conta de usuário. O
    `username` dessa conta é escolhido por quem a cria e não precisa ser
    o RA: o cadastro da gestão aceita os dois separados. O que o sistema
    garante é só que o RA é único.
    """

    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='aluno',
    )
    ra_cifrado = models.BinaryField('RA cifrado')
    ra_indice = models.CharField(
        'índice do RA', max_length=64, unique=True, editable=False)
    nome_completo = models.CharField(max_length=150)

    objects = AlunoQuerySet.as_manager()

    class Meta:
        verbose_name = 'aluno'
        verbose_name_plural = 'alunos'

    @property
    def ra(self):
        if not self.ra_cifrado:
            return ''
        return protecao.decifrar(self.ra_cifrado)

    @ra.setter
    def ra(self, valor):
        valor = protecao.normalizar(valor)
        if not valor:
            # Vazio fica vazio, e a validação do model recusa.
            self.ra_cifrado = b''
            self.ra_indice = ''
            return
        self.ra_cifrado = protecao.cifrar(valor)
        self.ra_indice = protecao.indice(valor)

    def __str__(self):
        return f'{self.nome_completo} (RA {self.ra})'

    def clean(self):
        # O e-mail institucional é obrigatório só pro aluno, diferente do
        # Usuario genérico (que tem e-mail opcional). Sem isso, o aluno
        # ficaria sem nenhuma forma de recuperar a senha sozinho.
        if not self.usuario.email:
            raise ValidationError('Aluno precisa de um e-mail institucional.')
        if not self.ra_cifrado or not self.ra_indice:
            raise ValidationError({'ra_cifrado': 'Informe o RA do aluno.'})
        if len(self.ra) > TAMANHO_MAXIMO_RA:
            raise ValidationError(
                {'ra_cifrado': f'O RA tem no máximo {TAMANHO_MAXIMO_RA} caracteres.'})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
