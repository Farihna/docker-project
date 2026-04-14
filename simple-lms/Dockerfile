FROM python:3.11-slim

# Mencegah Python membuat file .pyc dan memastikan output log terlihat real-time
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

WORKDIR /code

# Copy requirements.txt dulu agar bisa memanfaatkan cache layer Docker
COPY requirements.txt /code/

# Install dependencies dan pastikan pip terbaru
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Baru copy seluruh sisa file (termasuk folder code)
COPY . /code/