from pydantic import BaseModel, Field, StringConstraints, field_validator
from typing import Annotated, Literal, Optional, List
from datetime import date, datetime

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


# one problem found in a value; the site turns code, field and params into a message in its language
class Problem(BaseModel):
    code: str
    field: Optional[str] = None
    params: dict = {}


class ImportRowError(BaseModel):
    line: Optional[int] = None
    catalog_number: Optional[str] = None
    problems: List[Problem]

class ImportReport(BaseModel):
    dry_run: bool
    total: int
    created: int
    updated: int
    skipped: int
    errors: List[ImportRowError]
    warnings: List[ImportWarning] = []


# who can see a project: only the laboratory, anyone with the share link, or everyone
Visibility = Literal["private", "unlisted", "public"]


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

# a new project is private until someone in the laboratory publishes it
class ProjectCreate(ProjectBase):
    visibility: Visibility = "private"

class ProjectResponse(ProjectBase):
    id: int
    visibility: str
    # only sent to members of the laboratory
    share_token: Optional[str] = None

    class Config:
        from_attributes = True

class UserLogin(BaseModel):
    email: str = Field(..., min_length=5)
    password: str = Field(..., min_length=3)

# open sign-up: an account with no laboratory, which cannot do anything until the e-mail is confirmed.
# The minimum length of the password is checked by the route, with its own message
class SignupRequest(BaseModel):
    email: Annotated[str, StringConstraints(strip_whitespace=True, min_length=5, max_length=254)]
    password: str = Field(..., max_length=128)
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]

# the code from the link in the confirmation e-mail
class ConfirmRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=100)

class ForgotPasswordRequest(BaseModel):
    email: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=254)]

# the code from the link in the e-mail and the new password; the minimum length is checked by the route
class ResetPasswordRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., max_length=128)

class PasswordChange(BaseModel):
    current_password: str = Field(..., max_length=128)
    new_password: str = Field(..., max_length=128)

class ProjectUpdate(BaseModel):
    title: Optional[str] = None
    year: Optional[int] = None
    insect_group: Optional[str] = None
    measured_traits: Optional[str] = None
    locality: Optional[str] = None
    cover_url: Optional[str] = None
    dataset_url: Optional[str] = None
    finished: Optional[bool] = None
    visibility: Optional[Visibility] = None
    linked_publication: Optional[str] = None
    description: Optional[str] = None


# what anyone may know about a laboratory
class LaboratoryPublic(BaseModel):
    slug: str
    name: str
    institution: str
    collection_code: str

    class Config:
        from_attributes = True


# a person of the team on the About page
class TeamMember(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
    role: Optional[Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)]] = None


# the About page of a laboratory: public, like the rest of what the laboratory shows
class LaboratoryDetails(LaboratoryPublic):
    about: Optional[str] = None
    contact_email: Optional[str] = None
    team: List[TeamMember] = []

    @field_validator("team", mode="before")
    @classmethod
    def no_team_is_an_empty_one(cls, value):
        return value or []


# what the admins of a laboratory change about it; a field left out stays as it is. The address (slug), the
# Darwin Core collection code and the public list stay with the platform administrator
class LaboratoryUpdate(BaseModel):
    name: Optional[Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]] = None
    institution: Optional[Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]] = None
    about: Optional[str] = Field(None, max_length=5000)
    contact_email: Optional[str] = Field(None, max_length=254)
    team: Optional[List[TeamMember]] = Field(None, max_length=30)


# a public specimen whose picture illustrates a laboratory; the site builds the image address from these
# fields, as it does for any specimen
class LaboratoryCover(BaseModel):
    specimen_id: int
    photo_url: Optional[str] = None
    image_file: Optional[str] = None
    dataset_url: Optional[str] = None


# a laboratory in the public list, with the numbers of what visitors can see in it
class LaboratorySummary(LaboratoryPublic):
    projects: int
    specimens: int
    species: int
    cover: Optional[LaboratoryCover] = None


# a public specimen on the map of the home page, with the laboratory it belongs to
class MapPoint(BaseModel):
    id: int
    catalog_number: str
    species: str
    insect_order: str
    locality: Optional[str] = None
    latitude: float
    longitude: float
    photo_url: Optional[str] = None
    image_file: Optional[str] = None
    dataset_url: Optional[str] = None
    laboratory: str
    laboratory_name: str


# the numbers of the whole platform, for the home page
class PlatformTotals(BaseModel):
    laboratories: int
    projects: int
    specimens: int
    species: int


# a project opened by its share link also says whose it is, so whoever received the link knows where the
# data comes from (and whom to cite)
class SharedProjectResponse(ProjectResponse):
    laboratory: LaboratoryPublic


# the slug is part of the address, so only lowercase letters, digits and single hyphens between them
SLUG_PATTERN = r"^[a-z0-9]+(-[a-z0-9]+)*$"


# every laboratory, listed or not, as the platform administrator sees it: who manages each one and how many
# people it has, but none of its data (the platform administrator has no access to it)
class PlatformLaboratory(BaseModel):
    slug: str
    name: str
    institution: str
    collection_code: str
    license: str
    listed: bool
    members: int
    admins: List[str]


class LaboratoryCreate(BaseModel):
    slug: str = Field(..., min_length=2, max_length=40, pattern=SLUG_PATTERN)
    name: str = Field(..., min_length=1)
    institution: str = Field(..., min_length=1)
    collection_code: str = Field(..., min_length=1)
    license: Optional[str] = None
    listed: bool = False
    # an existing user who becomes the first admin; without one nobody could manage the laboratory
    admin_email: str = Field(..., min_length=3)


# a member of a laboratory, as the laboratory's admins see them; the id is the membership, not the user
class MemberResponse(BaseModel):
    id: int
    email: str
    name: Optional[str] = None
    role: str


# the signed-in person and the laboratories they belong to, so the site knows what to show them
class MyLaboratory(BaseModel):
    slug: str
    name: str
    role: str


class Me(BaseModel):
    email: str
    name: Optional[str] = None
    is_superadmin: bool
    laboratories: List[MyLaboratory]


class MemberUpdate(BaseModel):
    role: Literal["admin", "researcher"]


# one change of who can see a project, as the laboratory's admins see it; project_id is empty once the project
# was deleted (the title is the one it had at the time)
class VisibilityChangeResponse(BaseModel):
    id: int
    project_id: Optional[int] = None
    project_title: str
    user_email: str
    from_visibility: Optional[str] = None
    to_visibility: str
    changed_at: datetime

    class Config:
        from_attributes = True


class InvitationCreate(BaseModel):
    email: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=254)]
    role: Literal["admin", "researcher"] = "researcher"


# a pending invitation, as the laboratory's admins see it; the code is never shown again after the e-mail
class InvitationResponse(BaseModel):
    id: int
    email: str
    role: str
    created_at: datetime
    expires_at: datetime

    class Config:
        from_attributes = True


class InvitationLaboratory(BaseModel):
    slug: str
    name: str


# what the page of the link shows to whoever opens it: where, as what, and whether to sign in or to create
# an account. Only someone with the code (sent to that address) sees it
class InvitationPublic(BaseModel):
    laboratory: InvitationLaboratory
    email: str
    role: str
    has_account: bool


# a person without an account creates it while accepting; someone with one sends nothing and signs in instead
class InvitationAccept(BaseModel):
    name: Optional[Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)]] = None
    password: Optional[str] = Field(None, max_length=128)


class ValidateNamesRequest(BaseModel):
    names: List[str] = Field(..., max_length=300)


class ValidatedName(BaseModel):
    name: str
    status: str
    suggestion: Optional[str] = None
    family: Optional[str] = None
    order_name: Optional[str] = None
