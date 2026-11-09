FROM python:3.10-slim AS base

LABEL org.opencontainers.image.source https://github.com/MoritzGrossmann/jellyfin-auto-collections

ENV RUNNING_IN_DOCKER true

FROM base AS build

WORKDIR /app
COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt
# Chromium (+ system dependencies) for the headless browser used by the IMDb plugins
RUN playwright install --with-deps chromium
COPY . .

FROM build AS final

WORKDIR /app
COPY --from=build /app /app

VOLUME [ "/app/config" ]

ENTRYPOINT [ "python3.10", "-u", "main.py", "--config", "/app/config/config.yaml" ]
