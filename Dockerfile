# syntax=docker/dockerfile:1
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /opt/app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY tradingbot/ tradingbot/
COPY config.example.toml .

EXPOSE 8000

# Mount your own config with: -v $(pwd)/config.toml:/opt/app/config.toml
CMD ["sh", "-c", "python -m tradingbot -c $( [ -f config.toml ] && echo config.toml || echo config.example.toml ) serve --host 0.0.0.0 --port 8000"]
