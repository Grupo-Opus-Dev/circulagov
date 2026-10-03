import time

from django.conf import settings
from django.contrib.auth import logout
from django.shortcuts import redirect

from .signals import CHAVE_INICIO_SESSAO


class TimeoutAbsolutoMiddleware:
    """Essa classe serve para encerrar uma sessão após o TEMPO_MAXIMO_SESSAO_SEGUNDOS desde o login,
    mesmo se o usuário estiver ativo durante o período conforme o requisito 1.9.

    Estou implementando essa parte porque o Django sozinho só cobre timeout de INATIVIDADE,
    via SESSION_COOKIE_AGE junto com SESSION_SAVE_EVERY_REQUEST (de acordo com sua documentação). 
    Sem esse middleware, uma sessão que fica sendo usada sem parar nunca iria expirar, e é exatamente
    o que acontece quando uma sessão é roubada e usada aos poucos para não parecer inativa.
    Então pelos motivos acima que foi criado essa parte do código.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        usuario = getattr(request, 'user', None)

        if usuario is not None and usuario.is_authenticated:
            inicio = request.session.get(CHAVE_INICIO_SESSAO)
            sem_marca = inicio is None
            tempo_esgotado = (
                inicio is not None
                and time.time() - inicio > settings.TEMPO_MAXIMO_SESSAO_SEGUNDOS
            )

            if sem_marca or tempo_esgotado:
                logout(request)
                return redirect(settings.LOGIN_URL)

        return self.get_response(request)


# Tudo vem do proprio site, exceto a fonte Inter, que o Google Fonts serve
# (folha de estilo em fonts.googleapis.com e arquivos em fonts.gstatic.com).
# Sem 'unsafe-inline' em script-src e style-src: se alguem injetar um
# <script> ou um onclick no HTML, o navegador se recusa a executar.
POLITICA_DE_CONTEUDO = '; '.join([
    "default-src 'self'",
    "script-src 'self'",
    "style-src 'self' https://fonts.googleapis.com",
    "font-src https://fonts.gstatic.com",
    "img-src 'self' data:",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
])


class PoliticaDeConteudoMiddleware:
    """Envia o cabecalho Content-Security-Policy em toda resposta.

    Ele e a segunda camada contra XSS: o escape automatico dos templates
    impede a injecao, e a politica limita o estrago se alguma passar."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        resposta = self.get_response(request)
        resposta.headers.setdefault(
            'Content-Security-Policy', POLITICA_DE_CONTEUDO)
        return resposta
