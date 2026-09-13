from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class Aluno(models.Model):
    """Aluno da rede pública estadual de SP.

    O RA também vira o `username` do Usuario ligado a esse aluno, então
    o login continua funcionando pela tela normal, sem nenhuma view nova
    (usuário digita o RA no campo de usuário e a senha).
    """

    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='aluno',
    )
    ra = models.CharField('RA', max_length=20, unique=True)
    nome_completo = models.CharField(max_length=150)

    class Meta:
        verbose_name = 'aluno'
        verbose_name_plural = 'alunos'

    def __str__(self):
        return f'{self.nome_completo} (RA {self.ra})'

    def clean(self):
        # O e-mail institucional é obrigatório só pro aluno, diferente do
        # Usuario genérico (que tem e-mail opcional). Sem isso, o aluno
        # ficaria sem nenhuma forma de recuperar a senha sozinho.
        if not self.usuario.email:
            raise ValidationError('Aluno precisa de um e-mail institucional.')

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
