"""Trava de tentativas do segundo fator, por conta.

Um código TOTP tem 6 dígitos, e sem trava quem já sabe a senha pode tentar
os 10^6 possíveis até acertar o da janela de 30 segundos. O limite é por
conta (e não por endereço) porque aqui a conta já está identificada pela
senha certa, e trocar de endereço não deve dar tentativas novas."""
from usuarios import contadores

LIMITE_TENTATIVAS_2FA = 5
MINUTOS_BLOQUEIO_2FA = 15


def _chave(usuario_id):
    return f'tentativas_2fa_{usuario_id}'


def bloqueado(usuario_id):
    return contadores.ler(_chave(usuario_id)) >= LIMITE_TENTATIVAS_2FA


def registrar_falha(usuario_id):
    """A janela começa na primeira falha. Ao chegar no limite ela recomeça,
    pro bloqueio durar o tempo cheio. Quem já está bloqueado não deve
    chegar aqui, senão insistir renovaria o prazo."""
    contadores.somar(
        _chave(usuario_id), MINUTOS_BLOQUEIO_2FA * 60, LIMITE_TENTATIVAS_2FA)


def limpar(usuario_id):
    contadores.apagar(_chave(usuario_id))
