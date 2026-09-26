FROM python:3.12-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 BOT_DB_PATH=/app/data/bot.sqlite3

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot ./bot
VOLUME ["/app/data"]
CMD ["python", "-m", "bot.main"]
