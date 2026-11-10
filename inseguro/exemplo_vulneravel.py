"""ARQUIVO DE TESTE DA ESTEIRA. Nunca deve chegar na main.

Contem de proposito tres tipos de problema para provar que a esteira bloqueia:
chave de criptografia escrita no codigo, injecao de comando e execucao de
codigo vindo do usuario. Os valores abaixo sao inventados.
"""
import os
import subprocess

# Chave inventada, no mesmo formato das usadas pelo projeto (32 bytes em base64).
CHAVE_CIFRAGEM_2FA = "Zm9vYmFyYmF6cXV4Zm9vYmFyYmF6cXV4Zm9vYmFyYmFAMTI="


def executar_comando(request):
    # Injecao de comando: o texto do usuario vai direto para o shell.
    os.system(request.GET["cmd"])
    subprocess.call(request.GET["cmd"], shell=True)


def calcular(request):
    # Execucao de codigo vindo do usuario.
    return eval(request.GET["expr"])
