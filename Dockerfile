FROM python:3.13-slim

# Nao gerar .pyc e nao bufferizar a saida, pra o log do container
# aparecer na hora em vez de ficar preso no buffer do Python.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# libpq e a biblioteca cliente do PostgreSQL, exigida pelo psycopg.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Dependencias antes do codigo: enquanto o requirements nao mudar, o
# Docker reaproveita esta camada e o build fica rapido.
#
# O pip sai da imagem logo depois de instalar. Em producao nada o usa (o
# entrypoint so roda migrate, collectstatic e o gunicorn), e as copias de
# bibliotecas que ele carrega em pip/_vendor tinham CVE apontadas pelo Trivy.
# Precisa ser no mesmo RUN: num RUN separado os arquivos continuariam numa
# camada de baixo e iriam junto na imagem. Se um dia precisar dele dentro do
# container, `python -m ensurepip` traz de volta.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt     && pip uninstall -y pip

COPY . .

# Container nao roda como root. Se a aplicacao for comprometida, o
# invasor nao cai direto em root dentro do container.
# O chmod aqui e proposital: o bit de execucao nem sempre sobrevive ao
# checkout do git em Windows, entao garantimos no build.
RUN chmod +x /app/entrypoint.sh \
    && useradd --create-home --uid 1000 circulagov \
    && mkdir -p /app/logs /app/staticfiles \
    && chown -R circulagov:circulagov /app

USER circulagov

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
