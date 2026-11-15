import hmac
import logging

import pyotp
from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from . import cripto

logger = logging.getLogger('seguranca.dois_fatores')


class DispositivoTOTP(models.Model):
    """ Essa classe serve para guardar o código TOTP de um usuário.

    O usuário só precisa validar o código no login depois que esse dispositivo existir e estiver confirmado,
    antes disso ele continua entrando só com senha, colocamos o 2FA como opicional, assim como em alguns sistemas conhecidos.
    """

    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='dispositivo_totp',
    )
    segredo_cifrado = models.BinaryField()
    confirmado = models.BooleanField(default=False)
    criado_em = models.DateTimeField(auto_now_add=True)
    # Intervalo de 30 s do último código aceito. Um código só vale uma vez:
    # quem o interceptar não consegue reutilizá-lo dentro da janela.
    ultimo_passo_usado = models.BigIntegerField(null=True, blank=True)

    def __str__(self):
        return f'2FA de {self.usuario}'

    def save(self, *args, **kwargs):
        # Gera o segredo só na primeira vez que o dispositivo é salvo,
        # já cifrado. O valor puro nunca é salvo em lugar nenhum,
        # existe só aqui, na memória, durante essa chamada.
        if not self.segredo_cifrado:
            segredo_novo = pyotp.random_base32()
            self.segredo_cifrado = cripto.cifrar(segredo_novo.encode())
        super().save(*args, **kwargs)

    @property
    def segredo(self):
        return cripto.decifrar(bytes(self.segredo_cifrado)).decode()

    def totp(self):
        return pyotp.TOTP(self.segredo)

    def verificar_codigo(self, codigo):
        # Requisito 5.2. Fica aqui, e não em cada view, porque tanto o
        # cadastro do 2FA quanto o login passam por esse método, então um
        # log só nesse lugar já cobre os dois casos sem repetir código.
        # O código digitado nunca entra na mensagem, só o resultado.
        username = self.usuario.get_username()
        passo = self._passo_do_codigo(codigo)
        if passo is None:
            logger.warning('codigo 2FA incorreto, username=%s', username)
            return False

        # Uso único (RFC 6238, seção 5.2). O UPDATE só acontece se o passo
        # for mais novo que o último aceito, e o banco faz isso numa
        # operação só: duas requisições simultâneas com o mesmo código não
        # passam as duas.
        aceitos = DispositivoTOTP.objects.filter(
            Q(ultimo_passo_usado__isnull=True) | Q(ultimo_passo_usado__lt=passo),
            pk=self.pk,
        ).update(ultimo_passo_usado=passo)
        if not aceitos:
            logger.warning('codigo 2FA ja usado, username=%s', username)
            return False

        self.ultimo_passo_usado = passo
        logger.info('codigo 2FA correto, username=%s', username)
        return True

    def _passo_do_codigo(self, codigo):
        """Intervalo de 30 s a que o código pertence, aceitando um antes e
        um depois do atual para tolerar relógio dessincronizado. None se o
        código não bate com nenhum."""
        codigo = str(codigo or '')
        gerador = self.totp()
        atual = gerador.timecode(timezone.now())
        for passo in (atual - 1, atual, atual + 1):
            if hmac.compare_digest(gerador.generate_otp(passo), codigo):
                return passo
        return None
