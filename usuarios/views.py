import time

from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect, render

from dois_fatores.models import DispositivoTOTP
from dois_fatores.views import CHAVE_USUARIO_PENDENTE
from .seguranca import calcular_atraso, limpar_tentativas, registrar_falha, usuario_bloqueado


class LoginComDoisFatoresView(LoginView):
    """Essa classe é baseado (similar) ao LoginView do próprio DJango, com a diferença de que
    se o usuário tiver 2FA confirmado, a senha certa NÃO chama a função login() de imediato.
    Ao invés disso, manda pra tela de código do 2FA, e dai que ela chama o login().

    Também protege contra força bruta (requisito 1.11): bloqueia o usuário
    depois de várias falhas seguidas e atrasa a resposta a cada tentativa errada."""

    def post(self, request, *args, **kwargs):
        nome_usuario = request.POST.get('username', '')

        if nome_usuario and usuario_bloqueado(nome_usuario):
            formulario = self.get_form()
            formulario.add_error(
                None,
                'Muitas tentativas de login com esse usuário. '
                'Aguarde alguns minutos e tente novamente.',
            )
            return self.form_invalid(formulario)

        if nome_usuario:
            time.sleep(calcular_atraso(nome_usuario))

        return super().post(request, *args, **kwargs)

    def form_invalid(self, formulario):
        nome_usuario = formulario.data.get('username', '')
        if nome_usuario:
            registrar_falha(nome_usuario)
        return super().form_invalid(formulario)

    def form_valid(self, formulario):
        usuario = formulario.get_user()
        limpar_tentativas(usuario.get_username())

        dispositivos_confirmados = DispositivoTOTP.objects.filter(
            usuario=usuario, confirmado=True
        )
        tem_2fa = dispositivos_confirmados.exists()

        if tem_2fa:
            self.request.session[CHAVE_USUARIO_PENDENTE] = usuario.pk
            return redirect('dois_fatores:verificar')

        return super().form_valid(formulario)


@login_required
def inicio(request):
    """Página protegida só pra mostrar que o controle de acesso funciona:
    sem estar logado, o @login_required nem deixa chegar aqui."""
    return render(request, 'usuarios/inicio.html')
