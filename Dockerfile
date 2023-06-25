# Use an official lightweight Python image.
# https://hub.docker.com/_/python
FROM python:3.8-slim-buster

# Set environment variables
ENV PYTHONUNBUFFERED 1
ENV PYTHONDONTWRITEBYTECODE 1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Set work directory
WORKDIR /usr/src/app

# Copy project files into the docker image
COPY . .

# Install project dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Command to run on container start
ENTRYPOINT [ "python" ]
CMD [ "main.py" ]  
