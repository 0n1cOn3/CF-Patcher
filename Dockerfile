FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt && \
    adduser --disabled-password --gecos "" --uid 1000 cfpatcher
USER cfpatcher
COPY --chown=cfpatcher:cfpatcher main.py zone-locator.py config.example.json ./
ENV PYTHONUNBUFFERED=1
ENTRYPOINT ["python", "main.py"]
