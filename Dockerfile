# --- 1. aşama: React arayüzünü derle -----------------------------------------
FROM docker.io/library/node:22-alpine AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# --- 2. aşama: Flask API + derlenmiş arayüz -----------------------------------
FROM docker.io/library/python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    # Küçük matrislerde çok iş parçacıklı BLAS hız kazandırmaz, yalnızca CPU tüketir
    OPENBLAS_NUM_THREADS=1 \
    OMP_NUM_THREADS=1 \
    MPLBACKEND=Agg \
    MPLCONFIGDIR=/app/.mplcache \
    FRONTEND_DIST=/app/frontend \
    # PDF'lerdeki tarih/saat Türkiye saatiyle yazılsın (varsayılan UTC olurdu)
    TZ=Europe/Istanbul \
    PORT=8000

WORKDIR /app
COPY backend/requirements.txt ./
RUN pip install -r requirements.txt

COPY backend/app ./app
COPY backend/data ./data
COPY backend/run.py backend/gunicorn.conf.py ./
COPY --from=frontend /build/dist ./frontend

# matplotlib font önbelleğini imaj içinde hazırla; root olmayan kullanıcıyla çalış
RUN useradd --create-home --uid 1000 app \
    && python -c "import matplotlib.pyplot" \
    && chown -R app:app /app
USER app

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ[\"PORT\"]}/api/health', timeout=4)"

CMD ["gunicorn", "-c", "gunicorn.conf.py", "run:app"]
