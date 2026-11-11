from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, Date, DateTime
from sqlalchemy.orm import relationship
from database import Base

class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False, index=True)
    year = Column(Integer, nullable=False, index=True)
    insect_group = Column(String, nullable=False, index=True)
    measured_traits = Column(String, nullable=True)
    locality = Column(String, nullable=True)
    cover_url = Column(String, nullable=True)
    dataset_url = Column(String, nullable=True)
    finished = Column(Boolean, default=False)
    linked_publication = Column(String, nullable=True)
    description = Column(String, nullable=True)

    specimens = relationship("Specimen", back_populates="project", cascade="all, delete-orphan")


class Specimen(Base):
    __tablename__ = "specimens"

    id = Column(Integer, primary_key=True, index=True)
    catalog_number = Column(String, unique=True, index=True, nullable=False)
    insect_order = Column(String, index=True, nullable=False)
    family = Column(String, index=True, nullable=True)
    species = Column(String, index=True, nullable=False)
    collection_date = Column(Date, nullable=True)
    locality = Column(String, nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    elevation_m = Column(Float, nullable=True)
    sex = Column(String, nullable=True)
    life_stage = Column(String, nullable=True)
    # file name inside the project's Zenodo record (e.g. COL-001.jpg)
    image_file = Column(String, nullable=True)
    photo_url = Column(String, nullable=True)
    notes = Column(String, nullable=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)

    # public identification and collection fields
    identified_by = Column(String, nullable=True)
    identification_date = Column(Date, nullable=True)
    sampling_method = Column(String, nullable=True)
    habitat = Column(String, nullable=True)

    # internal fields: only the logged-in lab sees them (see INTERNAL_FIELDS in schemas.py)
    collector = Column(String, nullable=True)
    field_number = Column(String, nullable=True)
    storage_location = Column(String, nullable=True)
    loan_status = Column(String, nullable=True)
    loaned_to = Column(String, nullable=True)
    loan_date = Column(Date, nullable=True)
    internal_notes = Column(String, nullable=True)

    project = relationship("Project", back_populates="specimens")
    measurements = relationship("Measurement", back_populates="specimen", cascade="all, delete-orphan", order_by="Measurement.id")


class Measurement(Base):
    __tablename__ = "measurements"

    id = Column(Integer, primary_key=True, index=True)
    specimen_id = Column(Integer, ForeignKey("specimens.id"), nullable=False, index=True)
    trait = Column(String, nullable=False)
    value = Column(Float, nullable=False)
    unit = Column(String, nullable=False, default="mm")

    specimen = relationship("Specimen", back_populates="measurements")



class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)


# cache of scientific name lookups on GBIF
class Taxon(Base):
    __tablename__ = "taxa"

    id = Column(Integer, primary_key=True, index=True)
    queried_name = Column(String, unique=True, index=True, nullable=False)
    status = Column(String, nullable=False)
    suggestion = Column(String, nullable=True)
    gbif_key = Column(Integer, nullable=True)
    family = Column(String, nullable=True)
    order_name = Column(String, nullable=True)
    queried_at = Column(DateTime, nullable=False)
