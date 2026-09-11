import pyotp
from django.conf import settings
from django.db import models

from . import cripto


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
        gerador = self.totp()
        return gerador.verify(codigo, valid_window=1)
