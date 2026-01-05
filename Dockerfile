FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN adduser --disabled-password --gecos "" appuser \
    && chown -R appuser /app

COPY python/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY python ./python

WORKDIR /app/python

USER appuser

CMD ["python", "WOM.py"]
