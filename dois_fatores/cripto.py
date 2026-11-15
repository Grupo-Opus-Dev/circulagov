import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from django.conf import settings

TAMANHO_NONCE = 12


def cifrar(dado, contexto=None):
    """Cifra o dado com AES-GCM. Um nonce novo, que é basicamente um
    número aleatório usado uma única vez, é gerado a cada chamada e
    guardado junto do resultado, na frente, porque é preciso pra
    decifrar depois.

    O contexto, quando informado, entra como dado associado: não é
    cifrado, mas precisa ser o mesmo na hora de decifrar. Assim um valor
    cifrado de um campo não pode ser copiado para outro campo."""
    chave = base64.b64decode(settings.CHAVE_CIFRAGEM_2FA)
    nonce = os.urandom(TAMANHO_NONCE)
    gerador = AESGCM(chave)
    dado_cifrado = gerador.encrypt(nonce, dado, contexto)
    return nonce + dado_cifrado


def decifrar(dado_cifrado, contexto=None):
    chave = base64.b64decode(settings.CHAVE_CIFRAGEM_2FA)
    nonce = dado_cifrado[:TAMANHO_NONCE]
    resto = dado_cifrado[TAMANHO_NONCE:]
    gerador = AESGCM(chave)
    return gerador.decrypt(nonce, resto, contexto)
