FROM python:3.12

WORKDIR /app

RUN apt update && apt install -y \
    libavif-dev \
    libjpeg-dev \
    libpng-dev \
    libtiff-dev \
    libwebp-dev \
    libfreetype6-dev \
    libopenjp2-7-dev \
    && rm -rf /var/lib/apt/lists/*

RUN python -m pip install --upgrade pip setuptools wheel

COPY requirements.txt .
RUN python -m pip install --no-cache-dir -r requirements.txt

RUN python -m pip install --no-cache-dir --upgrade Pillow

COPY . /app

CMD ["bash", "start.sh"]
