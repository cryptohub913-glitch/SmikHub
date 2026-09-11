FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml ./
COPY smikhub ./smikhub

RUN pip install --no-cache-dir .

CMD ["python", "-m", "smikhub.bot.main"]
