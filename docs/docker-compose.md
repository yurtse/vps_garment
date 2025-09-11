\# Docker Compose — rfclabs



This project uses Docker Compose to run the Django app, Postgres DB, and Caddy reverse proxy.



\## Services

\- \*\*web\*\*: Django app (runs via Gunicorn, migrations, collectstatic at startup).

\- \*\*db\*\*: Postgres 15 with data stored in the `pgdata` volume.

\- \*\*caddy\*\*: Reverse proxy on ports 80/443. Uses `caddy/Caddyfile` and auto-manages TLS for `$DOMAIN`.



\## Volumes

\- `pgdata`: persistent Postgres data.

\- `static\_volume`: stores collected Django static files.

\- `caddy\_data` and `caddy\_config`: TLS certs and configs.



\## Usage

\### Start stack (build + run)

```bash

docker compose up -d --build



