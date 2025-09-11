# Setup — Dev VPS

Steps:
- Clone the repo on the VPS.
- Create `.env` (from `.env.example`) with secure values.
- Ensure Docker & docker-compose are installed.
- Run `docker compose up -d --build`, then run migrations and create superuser.
