FROM ghcr.io/astral-sh/uv:python3.12-dhi
WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_NO_CACHE=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc git wget curl pv jq \
        libssl-dev libcurl4-openssl-dev libnghttp2-dev ca-certificates \
        libavif-dev libjpeg-dev libpng-dev libtiff-dev libwebp-dev \
        libfreetype6-dev libopenjp2-7-dev \
        python3-dev python3-tk \
        tor \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN uv pip install -r requirements.txt --system

COPY . /app
RUN chmod +x /app/start.sh

# Consider adding a non-root user instead of running as root
CMD ["python", "main.py"]