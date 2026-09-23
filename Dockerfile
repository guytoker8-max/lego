# The website and its API in one image: the React site is built once and
# served by the same uvicorn process that answers /api.
#
#   docker build -t kitsnap .
#   docker run -p 8000:8000 -v kitsnap-data:/data \
#     -e BRICKSNAP_ADMIN_TOKEN=... -e BRICKSNAP_PUBLIC_URL=https://... kitsnap

FROM node:20-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json* ./
ENV PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1
RUN npm ci --no-audit --no-fund || npm install --no-audit --no-fund
COPY web/ ./
RUN npx vite build

FROM python:3.11-slim
WORKDIR /srv/server
COPY server/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY server/ ./
COPY --from=web /web/dist /srv/web/dist
ENV BRICKSNAP_DATA=/data \
    BRICKSNAP_WEB_DIST=/srv/web/dist \
    PYTHONUNBUFFERED=1
VOLUME /data
EXPOSE 8000
# Hosts such as Render and Railway say which port to use in $PORT.
CMD uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --proxy-headers --forwarded-allow-ips="*"
