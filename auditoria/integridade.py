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
import os
import time
from dataclasses import dataclass
from pathlib import Path

# Valor inicial da cadeia, usado antes da primeira linha do arquivo.
MAC_INICIAL = '0' * 64

SEPARADOR = ' | mac='

# A trava entre processos usa uma API diferente em cada sistema. Em
# produção (Linux) vale o flock. O msvcrt só existe pra o ambiente de
# desenvolvimento em Windows.
if os.name == 'nt':
    import msvcrt

    def _travar(descritor):
        # Tenta sem bloquear e repete, em vez de LK_LOCK, que espera 1s
        # entre tentativas e deixaria cada log lento sob disputa.
        limite = time.monotonic() + 10
        while True:
            try:
                os.lseek(descritor, 0, os.SEEK_SET)
                msvcrt.locking(descritor, msvcrt.LK_NBLCK, 1)
                return
            except OSError:
                if time.monotonic() > limite:
                    raise
                time.sleep(0.002)

    def _destravar(descritor):
        os.lseek(descritor, 0, os.SEEK_SET)
        msvcrt.locking(descritor, msvcrt.LK_UNLCK, 1)
else:
    import fcntl

    def _travar(descritor):
        fcntl.flock(descritor, fcntl.LOCK_EX)

    def _destravar(descritor):
        fcntl.flock(descritor, fcntl.LOCK_UN)


def _abrir_trava(caminho_do_log):
    """Abre o arquivo de trava que fica ao lado do log.

    É um arquivo separado, e não o próprio log, porque no Windows o lock
    é obrigatório: travar um trecho do log impediria o mesmo handler de
    ler o final dele pra continuar a cadeia.
    """
    descritor = os.open(f'{caminho_do_log}.lock', os.O_RDWR | os.O_CREAT)
    # No Windows não dá pra travar byte além do fim do arquivo vazio de
    # forma portável, então o arquivo tem 1 byte.
    if os.fstat(descritor).st_size == 0:
        os.write(descritor, b'0')
    return descritor


def _ultimo_mac_no_fim(caminho):
    """Lê a assinatura da última linha direto do arquivo.

    Lê só o final, em blocos que dobram de tamanho, em vez de percorrer o
    log inteiro a cada evento.
    """
    caminho = Path(caminho)
    if not caminho.exists():
        return MAC_INICIAL

    with caminho.open('rb') as arquivo:
        arquivo.seek(0, os.SEEK_END)
        tamanho = arquivo.tell()
        bloco = 4096
        while True:
            inicio = max(0, tamanho - bloco)
            arquivo.seek(inicio)
            linhas = [
                l for l in arquivo.read(tamanho - inicio).split(b'\n')
                if l.strip()
            ]
            # Com duas ou mais linhas, a última está inteira: só a
            # primeira pode ter sido cortada pelo começo do bloco. Com
            # uma só, ela pode estar cortada, então amplia a leitura.
            if inicio == 0 or len(linhas) >= 2:
                break
            bloco *= 2

    if not linhas:
        return MAC_INICIAL
    # O arquivo é lido em binário, então no Windows (gravado com \r\n) o
    # \r ficaria grudado no fim da assinatura. A verificação lê em modo
    # texto e não tem esse problema, por isso precisa ser tirado aqui.
    _, mac = separar_linha(linhas[-1].decode('utf-8').rstrip('\r'))
    return mac or MAC_INICIAL


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
    """FileHandler que assina cada linha e encadeia com a anterior.

    A cadeia vive no ARQUIVO, não na memória. Em produção o Gunicorn roda
    vários processos, cada um com o seu handler, todos gravando no mesmo
    log. Se cada handler guardasse o último MAC em memória, cada um
    calcularia a linha seguinte a partir de uma linha que talvez já não
    fosse a última, e a cadeia quebraria sozinha, sem ninguém ter mexido
    no arquivo. Foi o que aconteceu na primeira versão em produção.

    Por isso, a cada evento: pega a trava entre processos, lê a assinatura
    da última linha do arquivo, calcula, grava e solta a trava.
    """

    def __init__(self, filename, chave, **kwargs):
        kwargs.setdefault('encoding', 'utf-8')
        self.chave = decodificar_chave(chave)
        super().__init__(filename, **kwargs)
        self._trava = _abrir_trava(self.baseFilename)

    def emit(self, record):
        # O logging já chama emit() com o lock do handler, que cobre as
        # threads do mesmo processo. A trava abaixo cobre os outros.
        try:
            texto = self.format(record)
            # Quebra de linha na mensagem permitiria forjar uma linha
            # falsa no arquivo (log injection), então vira espaço.
            texto = texto.replace('\r', ' ').replace('\n', ' ')
            if self.stream is None:
                self.stream = self._open()

            _travar(self._trava)
            try:
                anterior = _ultimo_mac_no_fim(self.baseFilename)
                mac = calcular_mac(self.chave, anterior, texto)
                self.stream.write(f'{texto}{SEPARADOR}{mac}\n')
                self.flush()
            finally:
                _destravar(self._trava)
        except Exception:
            self.handleError(record)

    def close(self):
        try:
            super().close()
        finally:
            trava = getattr(self, '_trava', None)
            if trava is not None:
                os.close(trava)
                self._trava = None


@dataclass
class ResultadoVerificacao:
    integro: bool
    total_linhas: int
    linha_com_problema: int | None = None
    motivo: str | None = None
    ultimo_mac: str = MAC_INICIAL
    ancoras_conferidas: int = 0


SEPARADOR_ASSINATURA = ' | sig='


@dataclass
class Ancora:
    """Foto da cadeia num instante: quantas linhas havia e qual era a
    assinatura da última."""
    linhas: int
    mac: str
    em: str


def _assinar_ancora(chave, linhas, mac, em):
    mensagem = f'ancora|{linhas}|{mac}|{em}'.encode('utf-8')
    return hmac.new(chave, mensagem, hashlib.sha256).hexdigest()


def gerar_ancora(chave_base64, linhas, mac, em):
    """Texto de uma âncora, assinado com a mesma chave do log.

    A cadeia sozinha não prova que o FINAL do log está inteiro: quem apaga
    as últimas linhas (ou o arquivo todo) deixa o que sobrou válido. Uma
    âncora guardada FORA do servidor fecha essa lacuna: depois, o log só
    confere se ainda tem aquelas linhas e a mesma assinatura na linha N.

    A assinatura impede forjar uma âncora sem a chave, o que importa porque
    ela é guardada em lugares onde outras pessoas podem escrever.
    """
    chave = decodificar_chave(chave_base64)
    sig = _assinar_ancora(chave, linhas, mac, em)
    return f'ancora linhas={linhas} mac={mac} em={em}{SEPARADOR_ASSINATURA}{sig}'


def ler_ancoras(texto, chave_base64):
    """Lê as âncoras de um texto (uma por linha). Devolve (ancoras,
    problemas). Linhas que não começam com "ancora " são ignoradas, pra
    o arquivo poder ter comentários."""
    chave = decodificar_chave(chave_base64)
    ancoras, problemas = [], []
    for numero, linha in enumerate(texto.splitlines(), start=1):
        linha = linha.strip()
        if not linha.startswith('ancora '):
            continue
        corpo, _, sig = linha.partition(SEPARADOR_ASSINATURA)
        try:
            campos = dict(parte.split('=', 1) for parte in corpo.split()[1:])
            ancora = Ancora(int(campos['linhas']), campos['mac'], campos['em'])
        except (KeyError, ValueError):
            problemas.append(f'âncora ilegível na linha {numero}')
            continue
        esperado = _assinar_ancora(chave, ancora.linhas, ancora.mac, ancora.em)
        if not hmac.compare_digest(esperado, sig):
            problemas.append(
                f'âncora com assinatura inválida na linha {numero} '
                f'(adulterada ou feita com outra chave)')
            continue
        ancoras.append(ancora)
    return ancoras, problemas


def verificar_arquivo(caminho, chave_base64, ancoras=()):
    """Refaz a cadeia desde a primeira linha e para no primeiro problema.

    Com âncoras, confere também que o final do log não foi cortado."""
    chave = decodificar_chave(chave_base64)
    caminho = Path(caminho)
    ancoras = list(ancoras)

    if not caminho.exists():
        if ancoras:
            return ResultadoVerificacao(
                False, 0, None,
                'o arquivo de log não existe, mas há âncoras que provam '
                'que ele já teve linhas (arquivo apagado ou movido)')
        return ResultadoVerificacao(integro=True, total_linhas=0)

    mac_anterior = MAC_INICIAL
    total = 0
    precisadas = {a.linhas for a in ancoras}
    macs_das_ancoras = {}
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
            if numero in precisadas:
                macs_das_ancoras[numero] = mac

    for ancora in sorted(ancoras, key=lambda a: a.linhas):
        if ancora.linhas > total:
            return ResultadoVerificacao(
                False, total, None,
                f'o log tem {total} linhas, e a âncora de {ancora.em} prova '
                f'que já teve {ancora.linhas} (linhas do final foram apagadas)',
                mac_anterior)
        if macs_das_ancoras.get(ancora.linhas) != ancora.mac:
            return ResultadoVerificacao(
                False, total, ancora.linhas,
                f'a linha {ancora.linhas} não é a que a âncora de '
                f'{ancora.em} registrou (log reescrito)',
                mac_anterior)

    return ResultadoVerificacao(
        True, total, ultimo_mac=mac_anterior, ancoras_conferidas=len(ancoras))
