FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app/src
WORKDIR /app

COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements-dev.txt

COPY src ./src
COPY data ./data
COPY tests ./tests
COPY pytest.ini ./

RUN useradd --create-home riserbo && chown -R riserbo /app
USER riserbo

EXPOSE 8000
CMD ["uvicorn", "riserbo.server:app", "--host", "0.0.0.0", "--port", "8000"]
