from django.core.cache import cache

# Depois de LIMITE_TENTATIVAS falhas seguidas, o login fica bloqueado
# por MINUTOS_BLOQUEIO minutos.
LIMITE_TENTATIVAS = 5
MINUTOS_BLOQUEIO = 15


def chave_cache(nome_usuario):
    return f'tentativas_login_{nome_usuario}'


def usuario_bloqueado(nome_usuario):
    """True se esse usuário já errou demais e precisa esperar."""
    tentativas = cache.get(chave_cache(nome_usuario), 0)
    return tentativas >= LIMITE_TENTATIVAS


def registrar_falha(nome_usuario):
    """Soma mais uma tentativa errada pra esse usuário."""
    chave = chave_cache(nome_usuario)
    tentativas = cache.get(chave, 0)
    cache.set(chave, tentativas + 1, MINUTOS_BLOQUEIO * 60)


def limpar_tentativas(nome_usuario):
    """Zera o contador depois que o usuário acerta a senha."""
    cache.delete(chave_cache(nome_usuario))


def calcular_atraso(nome_usuario):
    """Atraso em segundos, proporcional às falhas recentes (até 2.5s)."""
    tentativas = cache.get(chave_cache(nome_usuario), 0)
    return min(tentativas, 5) * 0.5
