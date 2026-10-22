FROM python:3.12-slim
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend /app/backend
COPY demo /app/demo
COPY scripts /app/scripts
COPY tests /app/tests
COPY knowledge /app/knowledge
ENV PYTHONUNBUFFERED=1 PYTHONPATH=/app
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
