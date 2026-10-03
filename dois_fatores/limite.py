"""Trava de tentativas do segundo fator, por conta.

Um código TOTP tem 6 dígitos, e sem trava quem já sabe a senha pode tentar
os 10^6 possíveis até acertar o da janela de 30 segundos. O limite é por
conta (e não por endereço) porque aqui a conta já está identificada pela
senha certa, e trocar de endereço não deve dar tentativas novas."""
from django.core.cache import cache

LIMITE_TENTATIVAS_2FA = 5
MINUTOS_BLOQUEIO_2FA = 15


def _chave(usuario_id):
    return f'tentativas_2fa_{usuario_id}'


def bloqueado(usuario_id):
    return cache.get(_chave(usuario_id), 0) >= LIMITE_TENTATIVAS_2FA


def registrar_falha(usuario_id):
    """A janela começa na primeira falha. Ao chegar no limite ela recomeça,
    pro bloqueio durar o tempo cheio. Quem já está bloqueado não deve
    chegar aqui, senão insistir renovaria o prazo."""
    chave = _chave(usuario_id)
    segundos = MINUTOS_BLOQUEIO_2FA * 60
    cache.add(chave, 0, segundos)
    try:
        total = cache.incr(chave)
    except ValueError:
        cache.set(chave, 1, segundos)
        return
    if total == LIMITE_TENTATIVAS_2FA:
        cache.set(chave, total, segundos)


def limpar(usuario_id):
    cache.delete(_chave(usuario_id))
