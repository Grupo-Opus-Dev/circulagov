from django.contrib.auth.models import AbstractUser


class Usuario(AbstractUser):
    """
    Usuário customizado do CirculaGov.

    Estende o AbstractUser do Django (em vez de usar o User padrão) para
    permitir adicionar campos específicos do domínio (ex: vínculo com
    biblioteca/município, campos de LGPD) sem precisar trocar o model de
    autenticação no meio do projeto.
    """

    class Meta:
        verbose_name = "usuário"
        verbose_name_plural = "usuários"
