# Cresco

Cresco is a FastAPI MVP for demo wallet transfers, payment requests, transaction statements, and account balances.

## Production-like local run

Use Docker Compose from this folder:

```powershell
docker compose up --build
```

This starts:

- PostgreSQL database
- one database initializer
- two FastAPI API servers
- Nginx load balancer on `http://localhost:8000`
- notification worker
- Prometheus on `http://localhost:9090`

Open the app:

```text
http://localhost:8000
```

Open API docs:

```text
http://localhost:8000/docs
```

Check health:

```text
http://localhost:8000/health
```

## Demo accounts

| Name | Username | Email | Password |
| --- | --- | --- | --- |
| Dip | dip | dip@example.com | Dip@12345 |
| Kafi | kafi | kafi@example.com | Kafi@12345 |

Each demo wallet starts with BDT 100,000.

## Backup

With Docker Compose:

```powershell
docker compose --profile backup run --rm backup
```

With a local PostgreSQL install:

```powershell
cd backend
.\scripts\backup_postgres.ps1
```

The backup output is ignored by Git.
