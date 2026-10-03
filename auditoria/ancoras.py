"""Âncoras do log de segurança no lado do Django (arquivo e configuração).

A parte criptográfica está em integridade.py, que não importa o Django."""
from django.conf import settings

from .integridade import ResultadoVerificacao, ler_ancoras, verificar_arquivo


def arquivo_de_ancoras():
    return settings.LOG_DIR / 'ancoras.log'


def verificar_com_ancoras(extras=()):
    """Verifica o log de segurança conferindo as âncoras guardadas no
    servidor (logs/ancoras.log) e as de arquivos extras, que de preferência
    estão em outro lugar. Uma âncora ilegível ou com assinatura inválida
    também reprova: ignorá-la deixaria quem a adulterou sem consequência."""
    chave = settings.CHAVE_INTEGRIDADE_LOGS
    ancoras, problemas = [], []
    for caminho in [arquivo_de_ancoras(), *extras]:
        try:
            texto = caminho.read_text(encoding='utf-8')
        except FileNotFoundError:
            continue
        lidas, ruins = ler_ancoras(texto, chave)
        ancoras.extend(lidas)
        problemas.extend(f'{caminho.name}: {r}' for r in ruins)

    resultado = verificar_arquivo(
        settings.LOG_DIR / 'seguranca.log', chave, ancoras)
    if resultado.integro and problemas:
        return ResultadoVerificacao(
            False, resultado.total_linhas, None, '; '.join(problemas),
            resultado.ultimo_mac)
    return resultado
