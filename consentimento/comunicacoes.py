"""Comunicações por e-mail, a finalidade opcional do consentimento.

Todo envio dessa finalidade passa por `enviar_comunicacao`, que confere o
consentimento na hora do envio. Assim, quem revoga deixa de receber já no
envio seguinte, sem depender de cada tela lembrar de conferir.

O e-mail de recuperação de senha não passa por aqui: ele faz parte do
cadastro e da autenticação, e é o próprio titular quem o pede.
"""
import logging

from django.conf import settings
from django.core.mail import send_mail

from .models import Finalidade, tem_consentimento

logger = logging.getLogger('seguranca.consentimento')


def enviar_comunicacao(usuario, assunto, mensagem):
    """Envia a comunicação só com consentimento ativo e e-mail cadastrado.
    Devolve True se enviou."""
    if not tem_consentimento(usuario, Finalidade.COMUNICACOES):
        logger.info(
            'comunicacao nao enviada, sem consentimento ativo, usuario_id=%s',
            usuario.pk)
        return False
    if not usuario.email:
        return False
    send_mail(assunto, mensagem, settings.DEFAULT_FROM_EMAIL, [usuario.email])
    return True
