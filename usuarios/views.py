import logging
import time

from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect, render

from dois_fatores.models import DispositivoTOTP
from dois_fatores.views import iniciar_etapa_pendente
from .seguranca import (
    calcular_atraso, ip_do_cliente, limpar_tentativas, registrar_falha,
    usuario_bloqueado,
)

logger = logging.getLogger('seguranca.autenticacao')


class LoginComDoisFatoresView(LoginView):
    """Essa classe é baseado (similar) ao LoginView do próprio DJango, com a diferença de que
    se o usuário tiver 2FA confirmado, a senha certa NÃO chama a função login() de imediato.
    Ao invés disso, manda pra tela de código do 2FA, e dai que ela chama o login().

    Também protege contra força bruta (requisito 1.11): bloqueia o usuário
    depois de várias falhas seguidas e atrasa a resposta a cada tentativa errada."""

    def post(self, request, *args, **kwargs):
        nome_usuario = request.POST.get('username', '')
        ip = ip_do_cliente(request)

        if nome_usuario and usuario_bloqueado(nome_usuario, ip):
            # Requisito 5.2: esse bloqueio acontece antes mesmo de tentar
            # autenticar, então é um evento diferente da falha de login comum.
            logger.warning('bloqueio por forca bruta, username=%s', nome_usuario)
            formulario = self.get_form()
            formulario.add_error(
                None,
                'Muitas tentativas de login com esse usuário. '
                'Aguarde alguns minutos e tente novamente.',
            )
            # Vai pelo form_invalid do pai de propósito: o desta classe
            # soma uma falha, e somar durante o bloqueio renovaria o prazo
            # de quem insiste, que nunca mais sairia dele.
            return super().form_invalid(formulario)

        if nome_usuario:
            time.sleep(calcular_atraso(nome_usuario, ip))

        return super().post(request, *args, **kwargs)

    def form_invalid(self, formulario):
        nome_usuario = formulario.data.get('username', '')
        if nome_usuario:
            registrar_falha(nome_usuario, ip_do_cliente(self.request))
        return super().form_invalid(formulario)

    def form_valid(self, formulario):
        usuario = formulario.get_user()
        limpar_tentativas(usuario.get_username(), ip_do_cliente(self.request))

        dispositivos_confirmados = DispositivoTOTP.objects.filter(
            usuario=usuario, confirmado=True
        )
        tem_2fa = dispositivos_confirmados.exists()

        if tem_2fa:
            iniciar_etapa_pendente(self.request.session, usuario.pk)
            return redirect('dois_fatores:verificar')

        return super().form_valid(formulario)


@login_required
def inicio(request):
    """Página protegida só pra mostrar que o controle de acesso funciona:
    sem estar logado, o @login_required nem deixa chegar aqui."""
    # A tela precisa saber se o 2FA já está ativo pra não oferecer
    # "configurar" a quem já configurou, o que leva a uma página que só
    # diz que já está ativado.
    tem_2fa = DispositivoTOTP.objects.filter(
        usuario=request.user, confirmado=True
    ).exists()
    return render(request, 'usuarios/inicio.html', {'tem_2fa': tem_2fa})
