FROM python:3.12-slim
RUN pip install --no-cache-dir -r requirements.txt && \
    adduser --disabled-password --gecos "" --uid 1000 cfpatcher
USER cfpatcher
WORKDIR /app
COPY --chown=cfpatcher:cfpatcher main.py config.example.json ./
ENV PYTHONUNBUFFERED=1
ENTRYPOINT ["python", "main.py"]
