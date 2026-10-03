"""Site de administração que usa o login da própria aplicação.

O admin do Django traz o login dele, com formulário próprio, e esse login
não passa pelo segundo fator nem pelo bloqueio por tentativas que o
login da aplicação aplica. Quem tinha a senha de uma conta de gestão
entrava no /admin/ sem o código, mesmo com o 2FA ativo, e sem nenhum
limite de tentativas de senha.

Aqui o login do admin deixa de existir: ele só manda a pessoa para o
login da aplicação, e o admin passa a aceitar a sessão que sai de lá.
"""

from django.conf import settings
from django.contrib.admin.sites import AdminSite
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, resolve_url
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme


class AdminSiteCirculaGov(AdminSite):
    def login(self, request, extra_context=None):
        destino = request.GET.get(REDIRECT_FIELD_NAME) or reverse('admin:index')
        if not url_has_allowed_host_and_scheme(
                destino, allowed_hosts={request.get_host()},
                require_https=request.is_secure()):
            destino = reverse('admin:index')

        if request.user.is_authenticated:
            if request.user.is_active and request.user.is_staff:
                return redirect(destino)
            # Logado, mas sem acesso de gestão. Mandar de volta pra tela de
            # entrar não resolveria nada, então é 403, como nas outras
            # telas restritas.
            raise PermissionDenied('Esta área é restrita a quem administra o sistema.')

        # Descarta qualquer credencial enviada aqui: este endereço nunca
        # autentica, só redireciona.
        return redirect_to_login(destino, resolve_url(settings.LOGIN_URL))
