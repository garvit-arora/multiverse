FROM mcr.microsoft.com/playwright/python:v1.49.1-noble
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY services/api/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY services ./services
COPY packages ./packages
COPY infra ./infra
RUN mkdir -p /data/artifacts
CMD ["rq", "worker", "atlas", "--url", "redis://redis:6379/0"]
