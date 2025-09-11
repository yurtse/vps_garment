FROM python:3.11-slim

# system deps required for psycopg2 and builds
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev gcc && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /code

# copy and install python deps
COPY app/requirements.txt /code/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# copy project code
COPY app/ /code/

# add entrypoint
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]
CMD ["gunicorn", "garment_app.wsgi:application", "--bind", "0.0.0.0:8000"]
