FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1

COPY python/requirements.txt /app/python/requirements.txt
RUN pip install --no-cache-dir -r /app/python/requirements.txt

COPY python /app/python

EXPOSE 8080

CMD ["python", "python/WOM.py"]
