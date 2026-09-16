"""Proteção contra alteração do log de segurança (requisito 5.3).

Cada linha gravada recebe um HMAC calculado sobre o próprio texto e
sobre o HMAC da linha anterior, formando uma cadeia. Alterar, apagar ou
inserir uma linha quebra a cadeia a partir desse ponto.

Este módulo não importa nada do Django de propósito: ele é carregado
pela configuração de LOGGING antes dos apps estarem prontos.
"""

import base64
import hashlib
import hmac
import logging
from dataclasses import dataclass
from pathlib import Path

# Valor inicial da cadeia, usado antes da primeira linha do arquivo.
MAC_INICIAL = '0' * 64

SEPARADOR = ' | mac='


def calcular_mac(chave, mac_anterior, texto):
    mensagem = f'{mac_anterior}{texto}'.encode('utf-8')
    return hmac.new(chave, mensagem, hashlib.sha256).hexdigest()


def decodificar_chave(chave_base64):
    chave = base64.b64decode(chave_base64)
    # Chave curta deixaria o HMAC fácil de forjar por força bruta.
    if len(chave) < 32:
        raise ValueError('CHAVE_INTEGRIDADE_LOGS precisa ter pelo menos 32 bytes.')
    return chave


def separar_linha(linha):
    """Devolve (texto, mac) ou (linha, None) se a linha não tiver assinatura.

    Usa a última ocorrência do separador, porque o texto do evento pode
    conter " | mac=" digitado por um usuário (ex: no campo de login).
    """
    if SEPARADOR not in linha:
        return linha, None
    texto, mac = linha.rsplit(SEPARADOR, 1)
    return texto, mac


class HandlerLogIntegro(logging.FileHandler):
    """FileHandler que assina cada linha e encadeia com a anterior."""

    def __init__(self, filename, chave, **kwargs):
        kwargs.setdefault('encoding', 'utf-8')
        self.chave = decodificar_chave(chave)
        # Ao reiniciar o servidor, a cadeia continua de onde o arquivo parou.
        self.ultimo_mac = self._ler_ultimo_mac(filename)
        super().__init__(filename, **kwargs)

    @staticmethod
    def _ler_ultimo_mac(filename):
        caminho = Path(filename)
        if not caminho.exists():
            return MAC_INICIAL
        ultima_linha = ''
        with caminho.open(encoding='utf-8') as arquivo:
            for linha in arquivo:
                if linha.strip():
                    ultima_linha = linha.rstrip('\n')
        _, mac = separar_linha(ultima_linha)
        return mac or MAC_INICIAL

    def emit(self, record):
        # O logging já chama emit() com o lock do handler, então duas
        # threads não calculam a cadeia ao mesmo tempo.
        try:
            texto = self.format(record)
            # Quebra de linha na mensagem permitiria forjar uma linha
            # falsa no arquivo (log injection), então vira espaço.
            texto = texto.replace('\r', ' ').replace('\n', ' ')
            mac = calcular_mac(self.chave, self.ultimo_mac, texto)
            if self.stream is None:
                self.stream = self._open()
            self.stream.write(f'{texto}{SEPARADOR}{mac}\n')
            self.flush()
            self.ultimo_mac = mac
        except Exception:
            self.handleError(record)


@dataclass
class ResultadoVerificacao:
    integro: bool
    total_linhas: int
    linha_com_problema: int | None = None
    motivo: str | None = None
    ultimo_mac: str = MAC_INICIAL


def verificar_arquivo(caminho, chave_base64):
    """Refaz a cadeia desde a primeira linha e para no primeiro problema."""
    chave = decodificar_chave(chave_base64)
    caminho = Path(caminho)

    if not caminho.exists():
        return ResultadoVerificacao(integro=True, total_linhas=0)

    mac_anterior = MAC_INICIAL
    total = 0
    with caminho.open(encoding='utf-8') as arquivo:
        for numero, linha in enumerate(arquivo, start=1):
            linha = linha.rstrip('\n')
            total = numero

            if not linha.strip():
                return ResultadoVerificacao(
                    False, total, numero, 'linha em branco inserida', mac_anterior
                )

            texto, mac = separar_linha(linha)
            if mac is None:
                return ResultadoVerificacao(
                    False, total, numero, 'linha sem assinatura', mac_anterior
                )

            esperado = calcular_mac(chave, mac_anterior, texto)
            # compare_digest evita vazar informação pelo tempo da comparação.
            if not hmac.compare_digest(esperado, mac):
                return ResultadoVerificacao(
                    False, total, numero,
                    'assinatura não confere (linha alterada, removida ou inserida)',
                    mac_anterior,
                )
            mac_anterior = mac

    return ResultadoVerificacao(True, total, ultimo_mac=mac_anterior)
