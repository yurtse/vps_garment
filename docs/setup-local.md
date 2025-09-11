# Setup — Local

Steps:
- Copy `.env.example` to `.env` and update values.
- Use `docker compose -f docker-compose.yml -f docker-compose.override.yml up --build` for development.
- Create superuser and run migrations locally.
