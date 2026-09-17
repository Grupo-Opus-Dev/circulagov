import logging
import time

from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver

CHAVE_INICIO_SESSAO = 'inicio_sessao'

logger = logging.getLogger('seguranca.autenticacao')


@receiver(user_logged_in)
def gravar_inicio_da_sessao(sender, request, user, **kwargs):
    """O login do Django solta esse sinal depois de autenticar. É basicamente uma função para pegar o início da sessão,
    para que posteriormente podermos fazer o desligamento por timeout.
    Com essa função conseguimos ver quanto tempo uma mesma sessão está durando.
    """
    request.session[CHAVE_INICIO_SESSAO] = time.time()


@receiver(user_logged_in)
def registrar_login_com_sucesso(sender, request, user, **kwargs):
    """Requisito 5.1. Usa o mesmo sinal nativo do login acima, só que numa
    função separada, pra não misturar a lógica de sessão com a de log."""
    logger.info('login com sucesso, username=%s', user.get_username())


@receiver(user_logged_out)
def registrar_logout(sender, request, user, **kwargs):
    """Requisito 5.1. O Django manda `user` aqui, mas pode vir None se o
    logout for chamado numa sessão que já não tinha ninguém logado."""
    if user is not None:
        logger.info('logout, username=%s', user.get_username())


@receiver(user_login_failed)
def registrar_falha_de_login(sender, credentials, request=None, **kwargs):
    """Requisito 5.1. O Django já tira a senha de `credentials` antes de
    disparar esse sinal, mas pegamos só o username mesmo assim, por
    garantia de nunca logar nada além do necessário."""
    logger.warning('tentativa de login com falha, username=%s', credentials.get('username'))
