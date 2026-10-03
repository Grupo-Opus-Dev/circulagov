from django.conf import settings

from . import contadores

# Depois de LIMITE_TENTATIVAS falhas seguidas vindas do mesmo endereço contra
# o mesmo usuário, esse par fica bloqueado por MINUTOS_BLOQUEIO minutos.
LIMITE_TENTATIVAS = 5
MINUTOS_BLOQUEIO = 15

# Teto por conta, somando todos os endereços. Sem ele, quem troca de
# endereço a cada 5 tentativas nunca é bloqueado. É bem maior que o limite
# por par pra que um desconhecido não consiga trancar a conta de outra
# pessoa só errando a senha de outro endereço.
LIMITE_TENTATIVAS_POR_CONTA = 25


def ip_do_cliente(request):
    """Endereço de quem fez a requisição. Atrás do nginx o REMOTE_ADDR é
    sempre o do próprio proxy, então em produção o cabeçalho vem do
    settings (CABECALHO_IP_DO_CLIENTE), que o nginx sobrescreve."""
    cabecalho = getattr(settings, 'CABECALHO_IP_DO_CLIENTE', 'REMOTE_ADDR')
    valor = request.META.get(cabecalho, '') or request.META.get('REMOTE_ADDR', '')
    return valor.split(',')[0].strip()


def chave_cache(nome_usuario):
    """Contador da conta, somando todos os endereços."""
    return f'tentativas_login_{nome_usuario}'


def chave_cache_par(nome_usuario, ip):
    return f'tentativas_login_{nome_usuario}|{ip}'


def usuario_bloqueado(nome_usuario, ip=''):
    """True se esse usuário já errou demais e precisa esperar."""
    if contadores.ler(chave_cache(nome_usuario)) >= LIMITE_TENTATIVAS_POR_CONTA:
        return True
    return contadores.ler(chave_cache_par(nome_usuario, ip)) >= LIMITE_TENTATIVAS


def registrar_falha(nome_usuario, ip=''):
    """Soma mais uma tentativa errada pra esse usuário. Quem já está
    bloqueado não deve chegar aqui: renovar o contador durante o bloqueio
    faria quem insiste ficar bloqueado pra sempre."""
    segundos = MINUTOS_BLOQUEIO * 60
    contadores.somar(
        chave_cache(nome_usuario), segundos, LIMITE_TENTATIVAS_POR_CONTA)
    contadores.somar(
        chave_cache_par(nome_usuario, ip), segundos, LIMITE_TENTATIVAS)


def limpar_tentativas(nome_usuario, ip=''):
    """Zera o contador do par depois que o usuário acerta a senha. O da
    conta continua, senão quem tem a senha de uma conta apagaria o teto
    com um login certo a cada 24 erros."""
    contadores.apagar(chave_cache_par(nome_usuario, ip))


def calcular_atraso(nome_usuario, ip=''):
    """Atraso em segundos, proporcional às falhas recentes (até 2.5s)."""
    tentativas = contadores.ler(chave_cache_par(nome_usuario, ip))
    return min(tentativas, 5) * 0.5
