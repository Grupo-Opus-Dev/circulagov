from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect, render

from dois_fatores.models import DispositivoTOTP
from dois_fatores.views import CHAVE_USUARIO_PENDENTE


class LoginComDoisFatoresView(LoginView):
    """Essa classe é baseado (similar) ao LoginView do próprio DJango, com a diferença de que
    se o usuário tiver 2FA confirmado, a senha certa NÃO chama a função login() de imediato.
    Ao invés disso, manda pra tela de código do 2FA, e dai que ela chama o login()."""

    def form_valid(self, form):
        usuario = form.get_user()
        dispositivos_confirmados = DispositivoTOTP.objects.filter(
            usuario=usuario, confirmado=True
        )
        tem_2fa = dispositivos_confirmados.exists()

        if tem_2fa:
            self.request.session[CHAVE_USUARIO_PENDENTE] = usuario.pk
            return redirect('dois_fatores:verificar')

        return super().form_valid(form)


@login_required
def inicio(request):
    """Página protegida só pra mostrar que o controle de acesso funciona:
    sem estar logado, o @login_required nem deixa chegar aqui."""
    return render(request, 'usuarios/inicio.html')
