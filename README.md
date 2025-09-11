# rfclabs

Docker-based Django + Postgres template for local, dev VPS, and prod VPS.

## Quickstart (local)
1. Copy `.env.example` -> `.env` and edit values.
2. `docker compose up -d --build`
3. `docker compose exec web python manage.py createsuperuser`

## Deploy (dev VPS)
See `docs/setup-vps.md`.

## Docs
See the `docs/` folder for scenario-driven instructions.
