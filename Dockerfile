FROM tiangolo/uvicorn-gunicorn-fastapi:python3.8-slim

COPY ./app /app
COPY ./requirements.txt /

# Upgrade
RUN apt-get update && apt-get -y upgrade && apt clean && \
    pip3 install -r /requirements.txt

EXPOSE 80
