FROM mcr.microsoft.com/playwright/python:v1.61.0-jammy

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEPLOYMENT_MODE=railway \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Railway가 PORT 환경변수를 주입
CMD uvicorn server.main:app --host 0.0.0.0 --port ${PORT:-8080}
