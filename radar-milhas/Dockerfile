# Imagem oficial do Playwright: já traz Chromium e dependências do sistema.
FROM mcr.microsoft.com/playwright/python:v1.55.0-noble

WORKDIR /app
COPY pyproject.toml README.md ./
COPY radar ./radar
RUN pip install --no-cache-dir . "playwright==1.55.0"

ENV RADAR_DB_PATH=/data/radar.db \
    RADAR_BROWSER_PROFILE_DIR=/data/browser
VOLUME /data
EXPOSE 8000

# Painel web + busca diária no horário RADAR_RUN_AT
CMD ["radar", "web", "--host", "0.0.0.0", "--porta", "8000", "--agendar"]
