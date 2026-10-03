from urllib.parse import urlencode

from django.conf import settings
from django.core.paginator import Paginator
from django.shortcuts import render

from usuarios.decoradores import exige_gestor

from .eventos import CATEGORIAS, LIMITE_DE_LINHAS, NIVEIS, filtrar, ler_eventos
from .integridade import verificar_arquivo

EVENTOS_POR_PAGINA = 50


@exige_gestor
def integridade(request):
    """Mostra se o log de segurança está íntegro.

    Só administradores acessam: o resultado indica onde o log foi
    mexido, informação útil pra um invasor tentar esconder rastros.
    """
    resultado = verificar_arquivo(
        settings.LOG_DIR / 'seguranca.log', settings.CHAVE_INTEGRIDADE_LOGS
    )
    return render(request, 'auditoria/integridade.html', {'resultado': resultado})


@exige_gestor
def eventos(request):
    """Lista os eventos do log de segurança, do mais recente ao mais antigo.

    Existe pra os requisitos 5.1 e 5.2 poderem ser vistos pelo front-end:
    sem esta tela, os logs de autenticação, de falhas e de 2FA só
    apareceriam abrindo o arquivo no servidor.

    A verificação de integridade roda a cada abertura, e cada linha mostra
    se está antes de qualquer quebra da cadeia. Uma lista de log sem isso
    pediria pra confiar no arquivo sem poder conferir.
    """
    caminho = settings.LOG_DIR / 'seguranca.log'
    resultado = verificar_arquivo(caminho, settings.CHAVE_INTEGRIDADE_LOGS)

    todos, total_de_linhas = ler_eventos(
        caminho, primeira_quebra=resultado.linha_com_problema,
        limite=LIMITE_DE_LINHAS)

    categoria = request.GET.get('categoria', '')
    nivel = request.GET.get('nivel', '')
    busca = request.GET.get('busca', '')
    filtrados = filtrar(todos, categoria, nivel, busca)

    pagina = Paginator(filtrados, EVENTOS_POR_PAGINA).get_page(
        request.GET.get('page'))

    # Os links de paginação precisam carregar os filtros ativos, senão
    # ir pra página 2 jogaria a busca fora.
    ativos = {
        chave: valor for chave, valor in
        (('categoria', categoria), ('nivel', nivel), ('busca', busca.strip()))
        if valor
    }

    return render(request, 'auditoria/eventos.html', {
        'pagina': pagina,
        'resultado': resultado,
        'categorias': CATEGORIAS,
        'niveis': NIVEIS,
        'categoria': categoria,
        'nivel': nivel,
        'busca': busca,
        'consulta': urlencode(ativos),
        'total_filtrado': len(filtrados),
        'lidos': len(todos),
        'total_de_linhas': total_de_linhas,
        'truncado': total_de_linhas > LIMITE_DE_LINHAS,
        'limite': LIMITE_DE_LINHAS,
    })
