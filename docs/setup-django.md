\# Django Setup — rfclabs



\## Initial database setup

Run migrations inside the `web` container:



```bash

docker compose exec web python manage.py migrate



