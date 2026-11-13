from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, Date, DateTime, UniqueConstraint
from sqlalchemy.sql import expression
from sqlalchemy.orm import relationship
from database import Base

# roles a user can have inside a laboratory, and who can see a project
ROLES = ("admin", "researcher")
VISIBILITIES = ("private", "unlisted", "public")


# a laboratory owns its projects and specimens; the site shows only what it makes public
class Laboratory(Base):
    __tablename__ = "laboratories"

    id = Column(Integer, primary_key=True, index=True)
    # short name used in addresses (entomobase/lab/<slug>)
    slug = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    # Darwin Core codes and license used when the lab's data is exported
    institution = Column(String, nullable=False)
    collection_code = Column(String, nullable=False)
    license = Column(String, nullable=False)
    # whether the laboratory appears in the public list of the platform
    listed = Column(Boolean, nullable=False, default=False, server_default=expression.false())

    memberships = relationship("Membership", back_populates="laboratory", cascade="all, delete-orphan")


# which users belong to which laboratory, and with what role
class Membership(Base):
    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("user_id", "laboratory_id", name="uq_memberships_user_id_laboratory_id"),)

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    laboratory_id = Column(Integer, ForeignKey("laboratories.id"), nullable=False, index=True)
    role = Column(String, nullable=False)

    user = relationship("User", back_populates="memberships")
    laboratory = relationship("Laboratory", back_populates="memberships")


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    laboratory_id = Column(Integer, ForeignKey("laboratories.id"), nullable=False, index=True)
    title = Column(String, nullable=False, index=True)
    year = Column(Integer, nullable=False, index=True)
    insect_group = Column(String, nullable=False, index=True)
    measured_traits = Column(String, nullable=True)
    locality = Column(String, nullable=True)
    cover_url = Column(String, nullable=True)
    dataset_url = Column(String, nullable=True)
    # scientific status of the project (finished or still in progress)
    finished = Column(Boolean, default=False)
    # who can see the project: private, unlisted (only with the share link) or public
    visibility = Column(String, nullable=False, default="private", server_default="private")
    # random code for the share link of an unlisted project; never the numeric id, which is guessable
    share_token = Column(String, unique=True, index=True, nullable=True)
    linked_publication = Column(String, nullable=True)
    description = Column(String, nullable=True)

    laboratory = relationship("Laboratory")
    specimens = relationship("Specimen", back_populates="project", cascade="all, delete-orphan")


class Specimen(Base):
    __tablename__ = "specimens"
    # the catalog number is unique inside a laboratory, not in the whole database
    __table_args__ = (UniqueConstraint("laboratory_id", "catalog_number", name="uq_specimens_laboratory_id_catalog_number"),)

    id = Column(Integer, primary_key=True, index=True)
    # always the laboratory of the specimen's project
    laboratory_id = Column(Integer, ForeignKey("laboratories.id"), nullable=False, index=True)
    catalog_number = Column(String, index=True, nullable=False)
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

    laboratory = relationship("Laboratory")
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
    name = Column(String, nullable=True)
    # can create and deactivate laboratories (platform administrator)
    is_superadmin = Column(Boolean, nullable=False, default=False, server_default=expression.false())
    # when the person proved they own the e-mail address; empty until then
    email_verified_at = Column(DateTime, nullable=True)

    memberships = relationship("Membership", back_populates="user", cascade="all, delete-orphan")
    email_confirmations = relationship("EmailConfirmation", back_populates="user", cascade="all, delete-orphan")


# a code e-mailed to a user to confirm the address; only the hash is stored, so a copy of the database
# does not let anyone confirm an address that is not theirs
class EmailConfirmation(Base):
    __tablename__ = "email_confirmations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    code_hash = Column(String, unique=True, index=True, nullable=False)
    created_at = Column(DateTime, nullable=False)
    expires_at = Column(DateTime, nullable=False)

    user = relationship("User", back_populates="email_confirmations")


# an admin's invitation for someone to join a laboratory, sent by e-mail. Only the hash of the code is
# stored, like the confirmation codes. A laboratory has at most one invitation per address: inviting again
# replaces it. Accepting deletes it
class Invitation(Base):
    __tablename__ = "invitations"
    __table_args__ = (UniqueConstraint("laboratory_id", "email", name="uq_invitations_laboratory_id_email"),)

    id = Column(Integer, primary_key=True, index=True)
    laboratory_id = Column(Integer, ForeignKey("laboratories.id"), nullable=False, index=True)
    # always lowercase; the account, if any, is found by this address when the invitation is accepted
    email = Column(String, nullable=False)
    role = Column(String, nullable=False)
    # the admin who sent it; the invitation stops working if they are no longer an admin there
    invited_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    code_hash = Column(String, unique=True, index=True, nullable=False)
    created_at = Column(DateTime, nullable=False)
    expires_at = Column(DateTime, nullable=False)

    laboratory = relationship("Laboratory")
    invited_by = relationship("User")


LAB_REQUEST_STATUSES = ("pending", "approved", "rejected")


# someone asking to open a laboratory. A request from a trusted e-mail domain is approved at once; any other
# waits for a platform administrator. The slug is checked when the request is made, but not unique here:
# a rejected request must not keep its slug from being used
class LaboratoryRequest(Base):
    __tablename__ = "laboratory_requests"

    id = Column(Integer, primary_key=True, index=True)
    requester_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    slug = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False)
    institution = Column(String, nullable=False)
    collection_code = Column(String, nullable=False)
    license = Column(String, nullable=True)
    # what the person tells the platform administrator about the laboratory
    message = Column(String, nullable=True)
    status = Column(String, nullable=False, default="pending", server_default="pending")
    created_at = Column(DateTime, nullable=False)
    # who decided and when; empty while pending, and no one when it was approved because of the domain
    decided_at = Column(DateTime, nullable=True)
    decided_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    # the laboratory created when the request was approved
    laboratory_id = Column(Integer, ForeignKey("laboratories.id"), nullable=True)

    requester = relationship("User", foreign_keys=[requester_id])
    decided_by = relationship("User", foreign_keys=[decided_by_id])
    laboratory = relationship("Laboratory")


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
