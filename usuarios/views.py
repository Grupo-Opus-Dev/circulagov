from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required
def inicio(request):
    """Página protegida só pra mostrar que o controle de acesso funciona:
    sem estar logado, o @login_required nem deixa chegar aqui."""
    return render(request, 'usuarios/inicio.html')
