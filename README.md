# bp-agro-iot

**BP Agro — Business Management API**

Cloud-hosted Flask API for client and farm management. Business-end only — no node or zone management. Runs on AWS EC2, connects to Aurora.

## Responsibility
- Client registration, lookup, update, delete
- Farm registration with GPS coordinates (for weather)
- Gateway computer type assignment to farm
- Platform-wide dashboard KPIs

**Not handled here:** zones, crops, nodes, soil data. Those belong to the gateway.

## Quick Start
```bash
git clone https://github.com/bp-agro/bp-agro-iot
cd bp-agro-iot
cp .env.example .env
nano .env
bash deploy.sh
```

## Environment Variables
```
DB_HOST=your-aurora-cluster.rds.amazonaws.com
DB_USER=bpagro
DB_PASSWORD=FILL_ME
DB_NAME=soildb
PORT=5000
FLASK_ENV=production
```

## API Endpoints
Base URL: `http://<host>:5000/api/global`

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET/POST | /client | List / create clients |
| GET/PUT/DELETE | /client/{id} | Get / update / delete client |
| GET/POST | /farm | List / create farms |
| GET/PUT/DELETE | /farm/{id} | Get / update / delete farm |
| GET    | /stats | Dashboard KPIs |
| GET    | /health | Service health |

## Repository Structure
```
global_management/
  app.py              — Flask app, blueprint registration, /stats
  routes/
    client_routes.py  — client CRUD
    farm_routes.py    — farm CRUD
  config/
    aurora_config.py  — Aurora connection config
database/
  aws_schema.sql      — Aurora schema
services/
  bpagro-iot.service  — systemd unit
```
