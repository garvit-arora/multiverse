FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY services/api/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY services ./services
COPY packages ./packages
COPY infra ./infra
RUN mkdir -p /data/artifacts
EXPOSE 8001
CMD ["uvicorn", "services.api.main:app", "--host", "0.0.0.0", "--port", "8001"]
