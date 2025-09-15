# Dockerfile (recommended)
FROM python:3.11-slim

# avoid interactive tz prompts
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONPATH=/code

# Dockerfile snippet — replace the apt-get RUN block with this
RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential libpq-dev gcc curl ca-certificates netcat-openbsd \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /code

# copy and install python deps (use WORKDIR so relative path works)
COPY app/requirements.txt /code/requirements.txt
RUN python -m pip install --upgrade pip setuptools wheel \
 && python -m pip install --no-cache-dir -r /code/requirements.txt

# copy project code
COPY app/ /code/

# copy entrypoint outside of /code so bind-mounts won't hide it
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8000

# ensure the container runs entrypoint, with CMD providing default gunicorn args
ENTRYPOINT ["/entrypoint.sh"]
# default to config.wsgi rather than old garment_app.wsgi
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--log-level", "info"]
