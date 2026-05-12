from pydantic import BaseModel


class LocationProperties(BaseModel):
    name: str
    category: str


class Location(BaseModel):
    type: str = "Feature"
    id: int
    geometry: dict
    properties: LocationProperties


class LocationCollection(BaseModel):
    type: str = "FeatureCollection"
    features: list[Location]
