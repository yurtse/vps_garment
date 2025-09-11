FROM python:3.11-slim

# system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev gcc && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /code

# install python deps
COPY app/requirements.txt /code/
RUN pip install --no-cache-dir -r requirements.txt

# copy project
COPY app/ /code/

# entrypoint
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]
CMD ["gunicorn", "garment_app.wsgi:application", "--bind", "0.0.0.0:8000"]
