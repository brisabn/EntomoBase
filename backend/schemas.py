from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date

class MeasurementBase(BaseModel):
    trait: str = Field(..., min_length=1)
    value: float = Field(..., ge=0)
    unit: str = "mm"

class MeasurementCreate(MeasurementBase):
    pass

class MeasurementResponse(MeasurementBase):
    id: int

    class Config:
        from_attributes = True


# fields visitors never receive (API, CSV and Darwin Core)
INTERNAL_FIELDS = {
    "collector", "field_number", "storage_location", "loan_status",
    "loaned_to", "loan_date", "internal_notes",
}


class SpecimenBase(BaseModel):
    catalog_number: str = Field(..., min_length=1)
    insect_order: str = Field(..., min_length=1)
    family: Optional[str] = None
    species: str = Field(..., min_length=1)
    collection_date: Optional[date] = None
    locality: Optional[str] = None
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    elevation_m: Optional[float] = None
    sex: Optional[str] = None
    life_stage: Optional[str] = None
    image_file: Optional[str] = None
    photo_url: Optional[str] = None
    notes: Optional[str] = None
    project_id: Optional[int] = None
    identified_by: Optional[str] = None
    identification_date: Optional[date] = None
    sampling_method: Optional[str] = None
    habitat: Optional[str] = None
    collector: Optional[str] = None
    field_number: Optional[str] = None
    storage_location: Optional[str] = None
    loan_status: Optional[str] = None
    loaned_to: Optional[str] = None
    loan_date: Optional[date] = None
    internal_notes: Optional[str] = None

class SpecimenCreate(SpecimenBase):
    measurements: Optional[List[MeasurementCreate]] = []

class SpecimenUpdate(BaseModel):
    catalog_number: Optional[str] = Field(None, min_length=1)
    insect_order: Optional[str] = Field(None, min_length=1)
    family: Optional[str] = None
    species: Optional[str] = Field(None, min_length=1)
    collection_date: Optional[date] = None
    locality: Optional[str] = None
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    elevation_m: Optional[float] = None
    sex: Optional[str] = None
    life_stage: Optional[str] = None
    image_file: Optional[str] = None
    photo_url: Optional[str] = None
    notes: Optional[str] = None
    project_id: Optional[int] = None
    identified_by: Optional[str] = None
    identification_date: Optional[date] = None
    sampling_method: Optional[str] = None
    habitat: Optional[str] = None
    collector: Optional[str] = None
    field_number: Optional[str] = None
    storage_location: Optional[str] = None
    loan_status: Optional[str] = None
    loaned_to: Optional[str] = None
    loan_date: Optional[date] = None
    internal_notes: Optional[str] = None
    measurements: Optional[List[MeasurementCreate]] = None

class SpecimenResponse(SpecimenBase):
    id: int
    measurements: List[MeasurementResponse] = []

    class Config:
        from_attributes = True


class ImportRequest(BaseModel):
    project_id: Optional[int] = None
    duplicates: str = Field("ignore", pattern="^(ignore|update)$")
    rows: List[dict] = Field(..., max_length=5000)

class ImportWarning(BaseModel):
    name: str
    kind: str
    suggestion: Optional[str] = None
    row_count: int = 0


class ImportRowError(BaseModel):
    line: Optional[int] = None
    catalog_number: Optional[str] = None
    message: str

class ImportReport(BaseModel):
    dry_run: bool
    total: int
    created: int
    updated: int
    skipped: int
    errors: List[ImportRowError]
    warnings: List[ImportWarning] = []


class ProjectBase(BaseModel):
    title: str = Field(..., min_length=1)
    year: int = Field(..., ge=1900, le=2100)
    insect_group: str = Field(..., min_length=1)
    measured_traits: Optional[str] = None
    locality: Optional[str] = None
    cover_url: Optional[str] = None
    dataset_url: Optional[str] = None
    finished: bool = False
    linked_publication: Optional[str] = None
    description: Optional[str] = None

class ProjectCreate(ProjectBase):
    pass

class ProjectResponse(ProjectBase):
    id: int

    class Config:
        from_attributes = True

class UserLogin(BaseModel):
    email: str = Field(..., min_length=5)
    password: str = Field(..., min_length=3)

class ProjectUpdate(BaseModel):
    title: Optional[str] = None
    year: Optional[int] = None
    insect_group: Optional[str] = None
    measured_traits: Optional[str] = None
    locality: Optional[str] = None
    cover_url: Optional[str] = None
    dataset_url: Optional[str] = None
    finished: Optional[bool] = None
    linked_publication: Optional[str] = None
    description: Optional[str] = None


class ValidateNamesRequest(BaseModel):
    names: List[str] = Field(..., max_length=300)


class ValidatedName(BaseModel):
    name: str
    status: str
    suggestion: Optional[str] = None
    family: Optional[str] = None
    order_name: Optional[str] = None
