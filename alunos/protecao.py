"""Proteção do RA em repouso (requisito 3.4).

O RA é guardado cifrado com AES-GCM, pela mesma rotina do segredo do 2FA.
Como o valor cifrado muda a cada gravação (nonce novo), ele não serve para
buscar nem para garantir que o RA é único. Para isso existe o índice: um
HMAC-SHA256 do RA, sempre igual para o mesmo RA, que não permite voltar ao
valor original sem a chave.
"""
import base64
import hashlib
import hmac

from django.conf import settings

from dois_fatores import cripto

# Dado associado do AES-GCM: o RA cifrado só decifra como RA.
CONTEXTO = b'circulagov:aluno.ra'


def normalizar(ra):
    return (ra or '').strip()


def _chave_do_indice():
    # Chave própria para o índice, derivada da chave de cifragem, para a
    # mesma chave não ser usada em duas funções diferentes.
    chave = base64.b64decode(settings.CHAVE_CIFRAGEM_2FA)
    return hmac.new(chave, b'circulagov:indice-do-ra', hashlib.sha256).digest()


def indice(ra):
    return hmac.new(
        _chave_do_indice(), normalizar(ra).encode('utf-8'), hashlib.sha256
    ).hexdigest()


def cifrar(ra):
    return cripto.cifrar(normalizar(ra).encode('utf-8'), CONTEXTO)


def decifrar(dado_cifrado):
    return cripto.decifrar(bytes(dado_cifrado), CONTEXTO).decode('utf-8')
