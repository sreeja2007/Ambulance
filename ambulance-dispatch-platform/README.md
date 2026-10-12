# Emergency Ambulance Dispatch Platform (demo)

## Requirements
- Docker Desktop / Docker Engine with Docker Compose
- curl or Postman

## Run
```bash
docker compose up --build
```
API docs: http://localhost:8000/docs  
Health: http://localhost:8000/health  
RabbitMQ UI: http://localhost:15672 (demo credentials: guest / guest)

## Quick test
Create a user:
```bash
curl -X POST http://localhost:8000/api/v1/users \
  -H 'Content-Type: application/json' \
  -d '{"id":"U101","name":"Demo Patient","phone":"+910000000001"}'
```

Create an ambulance (coordinates are example data):
```bash
curl -X POST http://localhost:8000/api/v1/ambulances \
  -H 'Content-Type: application/json' \
  -d '{"id":"AMB101","registration_number":"TN00DEMO1","latitude":9.9252,"longitude":78.1198}'
```

Request an ambulance:
```bash
curl -X POST http://localhost:8000/api/v1/emergency-requests \
  -H 'Content-Type: application/json' \
  -d '{"user_id":"U101","latitude":9.9300,"longitude":78.1200,"emergency_type":"Medical Emergency","description":"Demo only"}'
```
Copy the returned `id`, then check:
```bash
curl http://localhost:8000/api/v1/emergency-requests/ER-REPLACE_ME
```

Update ambulance GPS:
```bash
curl -X PATCH http://localhost:8000/api/v1/ambulances/AMB101/location \
  -H 'Content-Type: application/json' \
  -d '{"latitude":9.9260,"longitude":78.1210}'
```

Open a WebSocket client to:
`ws://localhost:8000/ws/emergency-requests/REQUEST_ID`
Location updates for an active assigned request are broadcast to connected clients.

## Status transitions
- SEARCHING -> CANCELLED
- ASSIGNED -> EN_ROUTE or CANCELLED
- EN_ROUTE -> ARRIVED or CANCELLED
- ARRIVED -> COMPLETED

## Important limitations before production
This is a learning/demo scaffold, not a safety-certified emergency dispatch system.
- Add real authentication and authorization; secure the WebSocket endpoint.
- Use Alembic migrations instead of `create_all`.
- The sample event publisher is best-effort. Use a transactional outbox and retry policy so database commits and event delivery cannot diverge.
- The dispatch transaction should be strengthened with a conditional UPDATE / row locking strategy and tested under concurrent requests.
- Use PostGIS geography indexes and `ST_DWithin` for large fleets instead of loading candidates into Python.
- Configure secrets, TLS, private networking, backups, monitoring, audit logs, rate limits, and data-retention policies.
- Do not use demo coordinates, credentials, or this scaffold for live emergency operations.
