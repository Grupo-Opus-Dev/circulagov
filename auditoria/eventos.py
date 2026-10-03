"""Leitura do log de segurança para mostrar na tela.

Não importa nada do Django de propósito, como o resto do módulo de
integridade: assim pode ser testado sem banco e reaproveitado fora de
uma requisição.
"""

import re
from collections import deque
from dataclasses import dataclass
from pathlib import Path

from .integridade import separar_linha

# Quantas linhas, no máximo, são lidas do final do arquivo. O log não
# tem rotação, então sem teto uma tela de consulta ficaria mais lenta a
# cada semana de uso.
LIMITE_DE_LINHAS = 5000

# Formato definido em LOGGING (config/settings.py):
# "%(asctime)s %(levelname)s %(name)s %(message)s"
PADRAO_LINHA = re.compile(
    r'^(?P<data>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),\d+ '
    r'(?P<nivel>[A-Z]+) (?P<logger>[\w.]+) (?P<mensagem>.*)$'
)

# Chave é o final do nome do logger, depois de "seguranca.".
CATEGORIAS = {
    'autenticacao': 'Autenticação',
    'dois_fatores': 'Dois fatores',
    'recuperacao_senha': 'Recuperação de senha',
    'gestao': 'Gestão de usuários',
}

NIVEIS = ('INFO', 'WARNING', 'ERROR')

CATEGORIA_DESCONHECIDA = 'outros'


@dataclass
class Evento:
    numero: int            # linha no arquivo, a partir de 1
    data: str
    nivel: str
    categoria: str
    mensagem: str
    verificado: bool       # True se a linha está antes de qualquer quebra

    @property
    def rotulo_categoria(self):
        return CATEGORIAS.get(self.categoria, 'Outros')


def ler_eventos(caminho, primeira_quebra=None, limite=LIMITE_DE_LINHAS):
    """Devolve (eventos, total_de_linhas), do mais recente para o mais antigo.

    `primeira_quebra` é o número da primeira linha cuja assinatura não
    confere, ou None se a cadeia está íntegra. Linhas antes dela foram
    confirmadas pela verificação. Da quebra em diante, nada se pode
    afirmar, nem sobre as linhas que parecem normais.
    """
    caminho = Path(caminho)
    if not caminho.exists():
        return [], 0

    ultimas = deque(maxlen=limite)
    total = 0
    with caminho.open(encoding='utf-8') as arquivo:
        for numero, linha in enumerate(arquivo, start=1):
            total = numero
            ultimas.append((numero, linha.rstrip('\n')))

    eventos = []
    for numero, linha in ultimas:
        verificado = primeira_quebra is None or numero < primeira_quebra
        texto, _assinatura = separar_linha(linha)
        correspondencia = PADRAO_LINHA.match(texto)

        if correspondencia is None:
            # Linha fora do formato: aparece mesmo assim, porque esconder
            # justamente o que é estranho derrotaria o propósito da tela.
            eventos.append(Evento(
                numero, '', '', CATEGORIA_DESCONHECIDA, texto, verificado))
            continue

        logger = correspondencia.group('logger')
        categoria = logger.removeprefix('seguranca.')
        if categoria not in CATEGORIAS:
            categoria = CATEGORIA_DESCONHECIDA

        eventos.append(Evento(
            numero=numero,
            data=correspondencia.group('data'),
            nivel=correspondencia.group('nivel'),
            categoria=categoria,
            mensagem=correspondencia.group('mensagem'),
            verificado=verificado,
        ))

    eventos.reverse()
    return eventos, total


def filtrar(eventos, categoria='', nivel='', busca=''):
    """Aplica os filtros da tela. Valor desconhecido é ignorado, e não
    erro: um parâmetro inventado na URL não deve derrubar a página."""
    if categoria in CATEGORIAS or categoria == CATEGORIA_DESCONHECIDA:
        eventos = [e for e in eventos if e.categoria == categoria]
    if nivel in NIVEIS:
        eventos = [e for e in eventos if e.nivel == nivel]
    busca = busca.strip().lower()
    if busca:
        eventos = [e for e in eventos if busca in e.mensagem.lower()]
    return eventos
