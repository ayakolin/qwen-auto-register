FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt pyproject.toml README.md /app/
COPY src /app/src
COPY scripts /app/scripts

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt \
    && python -m patchright install --with-deps chromium \
    && pip install --no-cache-dir -e .

EXPOSE 18080

ENV AUTO_REGISTER_UI_MODE=web
ENV AUTO_REGISTER_HOST=0.0.0.0
ENV AUTO_REGISTER_PORT=18080
ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "auto_register", "--mode", "web", "--host", "0.0.0.0", "--port", "18080"]
