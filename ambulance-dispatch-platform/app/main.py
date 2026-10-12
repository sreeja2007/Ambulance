from contextlib import asynccontextmanager
from datetime import datetime, timezone
from math import radians, sin, cos, asin, sqrt
from uuid import uuid4

from fastapi import FastAPI, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.database import Base, engine, get_db
from app.models import (
    User, Hospital, Ambulance, EmergencyRequest,
    AmbulanceStatus, RequestStatus
)
from app.schemas import EmergencyCreate, EmergencyOut, AmbulanceOut, LocationUpdate
from app.cache import set_location, get_location, nearby_ids
from app.events import publish_event
from app.realtime import connect, disconnect, broadcast

@asynccontextmanager
async def lifespan(app: FastAPI):
    # For a demo only. Use Alembic migrations in production.
    Base.metadata.create_all(bind=engine)
    yield

app = FastAPI(title="Emergency Ambulance Dispatch API", version="1.0.0", lifespan=lifespan)

def distance_km(lat1, lon1, lat2, lon2):
    # Haversine distance; use PostGIS for large production datasets.
    dlat, dlon = radians(lat2-lat1), radians(lon2-lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1))*cos(radians(lat2))*sin(dlon/2)**2
    return 6371 * 2 * asin(sqrt(a))

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/api/v1/users", status_code=201)
def create_user(payload: dict, db: Session = Depends(get_db)):
    user_id = payload.get("id")
    name, phone = payload.get("name"), payload.get("phone")
    if not all([user_id, name, phone]):
        raise HTTPException(400, "id, name and phone are required")
    user = User(id=user_id, name=name, phone=phone)
    db.add(user)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(409, "User ID or phone already exists")
    return {"id": user.id, "name": user.name, "phone": user.phone}

@app.post("/api/v1/hospitals", status_code=201)
def create_hospital(payload: dict, db: Session = Depends(get_db)):
    try:
        hospital = Hospital(
            id=payload["id"], name=payload["name"],
            latitude=float(payload["latitude"]), longitude=float(payload["longitude"]),
            address=payload.get("address", "")
        )
    except (KeyError, TypeError, ValueError):
        raise HTTPException(400, "Provide id, name, latitude and longitude")
    db.add(hospital)
    db.commit()
    return {"id": hospital.id, "name": hospital.name}

@app.post("/api/v1/ambulances", status_code=201)
def create_ambulance(payload: dict, db: Session = Depends(get_db)):
    try:
        ambulance = Ambulance(
            id=payload["id"], registration_number=payload["registration_number"],
            latitude=float(payload["latitude"]), longitude=float(payload["longitude"]),
            status=AmbulanceStatus.AVAILABLE, hospital_id=payload.get("hospital_id")
        )
    except (KeyError, TypeError, ValueError):
        raise HTTPException(400, "Provide id, registration_number, latitude and longitude")
    db.add(ambulance)
    db.commit()
    set_location(ambulance.id, ambulance.latitude, ambulance.longitude)
    return {"id": ambulance.id, "status": ambulance.status.value}

@app.post("/api/v1/emergency-requests", response_model=EmergencyOut, status_code=201)
def create_emergency(payload: EmergencyCreate, db: Session = Depends(get_db)):
    if not db.get(User, payload.user_id):
        raise HTTPException(404, "User not found")
    req = EmergencyRequest(
        id=f"ER-{uuid4().hex[:12].upper()}", user_id=payload.user_id,
        latitude=payload.latitude, longitude=payload.longitude,
        emergency_type=payload.emergency_type, description=payload.description,
        status=RequestStatus.SEARCHING
    )
    db.add(req)
    db.commit()
    db.refresh(req)

    # Redis provides fast candidate IDs; database status is checked before assignment.
    try:
        candidate_ids = nearby_ids(payload.latitude, payload.longitude)
    except Exception:
        candidate_ids = []
    candidates = []
    if candidate_ids:
        candidates = db.scalars(select(Ambulance).where(
            Ambulance.id.in_(candidate_ids),
            Ambulance.status == AmbulanceStatus.AVAILABLE
        )).all()
    if not candidates:
        # Fallback is useful if cache is empty; production should use PostGIS query.
        candidates = db.scalars(select(Ambulance).where(
            Ambulance.status == AmbulanceStatus.AVAILABLE
        )).all()
    candidates.sort(key=lambda a: distance_km(
        payload.latitude, payload.longitude, a.latitude, a.longitude
    ))

    assigned = None
    for candidate in candidates:
        # Conditional UPDATE is the concurrency guard: only one request can claim it.
        result = db.execute(
            select(Ambulance).where(Ambulance.id == candidate.id).with_for_update()
        ).scalar_one_or_none()
        if result and result.status == AmbulanceStatus.AVAILABLE:
            result.status = AmbulanceStatus.ASSIGNED
            req.ambulance_id = result.id
            req.status = RequestStatus.ASSIGNED
            assigned = result
            break
    if assigned is None:
        req.status = RequestStatus.NO_AMBULANCE_AVAILABLE
    db.commit()
    db.refresh(req)

    publish_event({
        "event": "EmergencyRequestCreated",
        "request_id": req.id,
        "status": req.status.value,
        "ambulance_id": req.ambulance_id,
        "created_at": datetime.now(timezone.utc).isoformat()
    })
    if assigned:
        publish_event({"event": "AmbulanceAssigned", "request_id": req.id,
                       "ambulance_id": assigned.id})
    return req

@app.get("/api/v1/emergency-requests/{request_id}", response_model=EmergencyOut)
def get_emergency(request_id: str, db: Session = Depends(get_db)):
    req = db.get(EmergencyRequest, request_id)
    if not req:
        raise HTTPException(404, "Emergency request not found")
    return req

@app.get("/api/v1/ambulances/{ambulance_id}", response_model=AmbulanceOut)
def get_ambulance(ambulance_id: str, db: Session = Depends(get_db)):
    ambulance = db.get(Ambulance, ambulance_id)
    if not ambulance:
        raise HTTPException(404, "Ambulance not found")
    return ambulance

@app.get("/api/v1/ambulances/{ambulance_id}/location")
def ambulance_location(ambulance_id: str, db: Session = Depends(get_db)):
    ambulance = db.get(Ambulance, ambulance_id)
    if not ambulance:
        raise HTTPException(404, "Ambulance not found")
    cached = get_location(ambulance_id)
    if cached:
        return cached
    return {"ambulance_id": ambulance.id, "latitude": ambulance.latitude,
            "longitude": ambulance.longitude, "source": "database_fallback"}

@app.patch("/api/v1/ambulances/{ambulance_id}/location")
async def update_location(ambulance_id: str, payload: LocationUpdate, db: Session = Depends(get_db)):
    ambulance = db.get(Ambulance, ambulance_id)
    if not ambulance:
        raise HTTPException(404, "Ambulance not found")
    ambulance.latitude, ambulance.longitude = payload.latitude, payload.longitude
    db.commit()
    set_location(ambulance_id, payload.latitude, payload.longitude)
    active = db.scalars(select(EmergencyRequest).where(
        EmergencyRequest.ambulance_id == ambulance_id,
        EmergencyRequest.status.in_([RequestStatus.ASSIGNED, RequestStatus.EN_ROUTE, RequestStatus.ARRIVED])
    )).all()
    for req in active:
        await broadcast(req.id, {
            "event": "AmbulanceLocationUpdated", "request_id": req.id,
            "ambulance_id": ambulance_id, "latitude": payload.latitude,
            "longitude": payload.longitude
        })
    publish_event({"event": "AmbulanceLocationUpdated", "ambulance_id": ambulance_id,
                   "latitude": payload.latitude, "longitude": payload.longitude})
    return {"ambulance_id": ambulance_id, "updated": True}

@app.patch("/api/v1/emergency-requests/{request_id}/status")
def update_request_status(request_id: str, payload: dict, db: Session = Depends(get_db)):
    req = db.get(EmergencyRequest, request_id)
    if not req:
        raise HTTPException(404, "Emergency request not found")
    try:
        new_status = RequestStatus(payload["status"])
    except (KeyError, ValueError):
        raise HTTPException(400, "Invalid status")
    allowed = {
        RequestStatus.ASSIGNED: {RequestStatus.EN_ROUTE, RequestStatus.CANCELLED},
        RequestStatus.EN_ROUTE: {RequestStatus.ARRIVED, RequestStatus.CANCELLED},
        RequestStatus.ARRIVED: {RequestStatus.COMPLETED},
        RequestStatus.SEARCHING: {RequestStatus.CANCELLED},
    }
    if new_status not in allowed.get(req.status, set()):
        raise HTTPException(409, f"Cannot transition from {req.status.value} to {new_status.value}")
    req.status = new_status
    if req.ambulance_id:
        ambulance = db.get(Ambulance, req.ambulance_id)
        if ambulance:
            if new_status == RequestStatus.EN_ROUTE:
                ambulance.status = AmbulanceStatus.EN_ROUTE
            elif new_status == RequestStatus.ARRIVED:
                ambulance.status = AmbulanceStatus.AT_SCENE
            elif new_status in {RequestStatus.COMPLETED, RequestStatus.CANCELLED}:
                ambulance.status = AmbulanceStatus.AVAILABLE
    db.commit()
    publish_event({"event": "EmergencyStatusUpdated", "request_id": req.id, "status": req.status.value})
    return {"request_id": req.id, "status": req.status.value}

@app.websocket("/ws/emergency-requests/{request_id}")
async def emergency_updates(websocket: WebSocket, request_id: str):
    # Production: authenticate and authorize the caller before accepting.
    await connect(request_id, websocket)
    try:
        while True:
            await websocket.receive_text()  # client may send ping/keepalive
    except WebSocketDisconnect:
        disconnect(request_id, websocket)
