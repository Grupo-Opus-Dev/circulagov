import time

from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver

CHAVE_INICIO_SESSAO = 'inicio_sessao'


@receiver(user_logged_in)
def gravar_inicio_da_sessao(sender, request, user, **kwargs):
    """O login do Django solta esse sinal depois de autenticar. É basicamente uma função para pegar o início da sessão,
    para que posteriormente podermos fazer o desligamento por timeout.
    Com essa função conseguimos ver quanto tempo uma mesma sessão está durando.
    """
    request.session[CHAVE_INICIO_SESSAO] = time.time()
