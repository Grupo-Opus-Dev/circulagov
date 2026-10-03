"""Contadores de tentativas com janela, atômicos entre processos.

Antes eles usavam cache.incr(). No cache em banco do Django o incr() é uma
leitura seguida de uma gravação, então duas falhas simultâneas (os workers
do Gunicorn rodam em paralelo) podiam contar como uma só. Aqui a linha do
contador é travada no banco (SELECT ... FOR UPDATE) durante a soma, e cada
falha é contada uma vez."""
import hashlib
import time

from django.db import IntegrityError, transaction

from .models import ContadorDeTentativas


def _chave(nome):
    return hashlib.sha256(nome.encode('utf-8')).hexdigest()


def ler(nome):
    """Valor atual, ou 0 se não existe ou a janela já venceu."""
    contador = ContadorDeTentativas.objects.filter(chave=_chave(nome)).first()
    if contador is None or contador.expira_em <= time.time():
        return 0
    return contador.valor


def somar(nome, segundos, limite=None):
    """Soma uma ocorrência e devolve o novo valor.

    A janela começa na primeira ocorrência e não anda a cada uma. Ao chegar
    em `limite`, ela recomeça por `segundos` cheios, pro bloqueio durar o
    tempo todo a partir dali."""
    chave = _chave(nome)
    for _ in range(3):
        try:
            with transaction.atomic():
                agora = time.time()
                contador = (ContadorDeTentativas.objects
                            .select_for_update().filter(chave=chave).first())
                if contador is None:
                    # Aproveita pra limpar o que venceu, sem job separado.
                    ContadorDeTentativas.objects.filter(
                        expira_em__lt=agora).delete()
                    ContadorDeTentativas.objects.create(
                        chave=chave, valor=1, expira_em=agora + segundos)
                    return 1
                if contador.expira_em <= agora:
                    contador.valor = 1
                    contador.expira_em = agora + segundos
                else:
                    contador.valor += 1
                    if limite is not None and contador.valor == limite:
                        contador.expira_em = agora + segundos
                contador.save(update_fields=['valor', 'expira_em'])
                return contador.valor
        except IntegrityError:
            # Dois processos criaram a mesma linha ao mesmo tempo: o outro
            # ganhou. Tenta de novo, agora a linha existe e é só travar.
            continue
    raise RuntimeError('não foi possível atualizar o contador de tentativas')


def apagar(nome):
    ContadorDeTentativas.objects.filter(chave=_chave(nome)).delete()
