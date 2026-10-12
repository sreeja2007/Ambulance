from pydantic import BaseModel, Field, ConfigDict
from app.models import RequestStatus, AmbulanceStatus

class EmergencyCreate(BaseModel):
    user_id: str = Field(min_length=1, max_length=64)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    emergency_type: str = Field(min_length=2, max_length=80)
    description: str = Field(default="", max_length=2000)

class EmergencyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    user_id: str
    latitude: float
    longitude: float
    emergency_type: str
    description: str
    status: RequestStatus
    ambulance_id: str | None

class AmbulanceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    registration_number: str
    status: AmbulanceStatus
    latitude: float
    longitude: float

class LocationUpdate(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
