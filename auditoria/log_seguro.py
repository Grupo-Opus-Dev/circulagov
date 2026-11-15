"""Proteção contra log injection (CWE-117).

Quem digita uma quebra de linha num campo que vai para o log consegue
forjar uma linha falsa, por exemplo um "login com sucesso" que nunca
aconteceu. O arquivo assinado já troca a quebra por espaço
(auditoria/integridade.py). Aqui ficam as duas proteções do resto:

- `para_log`, para usar na chamada do logger com qualquer valor que veio
  do usuário;
- `FiltroQuebraDeLinha`, no handler do console (o log do container), para
  o caso de alguma chamada esquecer o `para_log`.

A quebra vira o texto "\\n" em vez de sumir, para quem lê o log ver que
alguém tentou.
"""
import copy
import logging


def para_log(valor):
    texto = str(valor)
    texto = texto.replace('\r', '\\r')
    return texto.replace('\n', '\\n')


class FiltroQuebraDeLinha(logging.Filter):
    def filter(self, record):
        # Devolve uma cópia: os outros handlers recebem o registro original.
        limpo = copy.copy(record)
        limpo.msg = para_log(record.getMessage())
        limpo.args = None
        return limpo
