import json
import redis
from app.config import REDIS_URL, LOCATION_TTL_SECONDS

client = redis.Redis.from_url(REDIS_URL, decode_responses=True)

def set_location(ambulance_id: str, latitude: float, longitude: float):
    payload = json.dumps({
        "ambulance_id": ambulance_id,
        "latitude": latitude,
        "longitude": longitude,
    })
    client.setex(f"ambulance:{ambulance_id}:location", LOCATION_TTL_SECONDS, payload)
    # Redis GEO uses longitude first, then latitude.
    client.geoadd("ambulances:geo", (longitude, latitude, ambulance_id))
    client.expire("ambulances:geo", LOCATION_TTL_SECONDS * 2)

def get_location(ambulance_id: str):
    value = client.get(f"ambulance:{ambulance_id}:location")
    return json.loads(value) if value else None

def nearby_ids(latitude: float, longitude: float, radius_km: float = 10):
    # Requires a reasonably recent location update in the GEO index.
    return client.geosearch(
        "ambulances:geo", longitude=longitude, latitude=latitude,
        radius=radius_km, unit="km", sort="ASC", count=50
    )
