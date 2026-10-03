from django.contrib.auth.models import AbstractUser
from django.db import models


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


class ContadorDeTentativas(models.Model):
    """Contador de tentativas com janela de tempo, guardado no banco.

    Serve ao bloqueio de login, ao limite do 2FA e ao limite de e-mails de
    recuperação. A chave é um hash, pra não guardar nomes de usuário nem
    endereços em claro, e pra caber no campo mesmo que alguém envie um
    nome de usuário enorme. Ver usuarios/contadores.py."""

    chave = models.CharField(max_length=64, unique=True)
    valor = models.PositiveIntegerField(default=0)
    # Segundos desde 1970 (time.time()), e não datetime, pra ficar
    # independente de fuso e simples de comparar.
    expira_em = models.FloatField()

    class Meta:
        verbose_name = 'contador de tentativas'
        verbose_name_plural = 'contadores de tentativas'
