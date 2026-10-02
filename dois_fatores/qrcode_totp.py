"""Geração do QR code que o app autenticador lê para cadastrar o 2FA."""

import io
import re

import qrcode
import qrcode.image.svg

# O XML declaration atrapalha quando o SVG e embutido direto no HTML.
INICIO_XML = re.compile(r'^<\?xml[^>]*\?>\s*')

# A biblioteca fixa width e height em milimetros. Removendo os dois, o
# viewBox continua valendo e quem manda no tamanho passa a ser o CSS.
TAMANHO_FIXO = re.compile(r'\s(?:width|height)="[^"]*"')


def gerar_svg(uri):
    """Devolve o QR code da URI como SVG pronto pra embutir no HTML.

    Gerado aqui no servidor de propósito. Existem serviços que montam QR
    a partir de uma URL, e usar um deles entregaria o segredo do 2FA pra
    um terceiro, furando justamente o mecanismo que deveria proteger a
    conta.

    SVG em vez de PNG porque não exige o Pillow, e porque escala sem
    perder nitidez em qualquer tela.
    """
    imagem = qrcode.make(
        uri,
        image_factory=qrcode.image.svg.SvgPathImage,
        box_size=10,
        border=2,
    )

    buffer = io.BytesIO()
    imagem.save(buffer)
    svg = buffer.getvalue().decode('utf-8')

    svg = INICIO_XML.sub('', svg)
    return TAMANHO_FIXO.sub('', svg, count=2)
