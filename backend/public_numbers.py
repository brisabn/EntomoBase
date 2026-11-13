# the numbers shown on the home page. They count only what a visitor can see: the projects marked public and
# the specimens in them, so a private or link-only project never shows up, not even as a number
from sqlalchemy import and_, distinct, func, or_
from sqlalchemy.orm import Session

import models

PUBLIC_PROJECT = models.Project.visibility == "public"


def public_specimens_query(db: Session, *columns):
    return db.query(*columns).join(models.Project, models.Specimen.project_id == models.Project.id).filter(PUBLIC_PROJECT)


# {laboratory id: {"projects", "specimens", "species"}}, for the given laboratories
def numbers_by_laboratory(db: Session, laboratory_ids):
    numbers = {lab_id: {"projects": 0, "specimens": 0, "species": 0} for lab_id in laboratory_ids}
    if not numbers:
        return numbers
    projects = db.query(models.Project.laboratory_id, func.count(models.Project.id)).filter(
        PUBLIC_PROJECT, models.Project.laboratory_id.in_(numbers)
    ).group_by(models.Project.laboratory_id)
    for lab_id, count in projects:
        numbers[lab_id]["projects"] = count
    specimens = public_specimens_query(
        db, models.Specimen.laboratory_id, func.count(models.Specimen.id), func.count(distinct(models.Specimen.species))
    ).filter(models.Specimen.laboratory_id.in_(numbers)).group_by(models.Specimen.laboratory_id)
    for lab_id, count, species in specimens:
        numbers[lab_id]["specimens"] = count
        numbers[lab_id]["species"] = species
    return numbers


# a public specimen with a picture, to illustrate the laboratory's card: the most recently added one. A file
# only makes a picture together with the repository of its project, where it is stored
def laboratory_cover(db: Session, laboratory_id: int):
    has_photo = models.Specimen.photo_url.like("http%")
    has_file = and_(models.Specimen.image_file.isnot(None), models.Specimen.image_file != "",
                    models.Project.dataset_url.like("http%"))
    row = public_specimens_query(
        db, models.Specimen.id, models.Specimen.photo_url, models.Specimen.image_file, models.Project.dataset_url
    ).filter(models.Specimen.laboratory_id == laboratory_id, or_(has_photo, has_file)).order_by(models.Specimen.id.desc()).first()
    if row is None:
        return None
    specimen_id, photo_url, image_file, dataset_url = row
    return {"specimen_id": specimen_id, "photo_url": photo_url, "image_file": image_file, "dataset_url": dataset_url}


# the whole platform, counting the listed laboratories only, like the list on the home page; a species found
# in two laboratories counts once
def platform_totals(db: Session):
    listed = db.query(models.Laboratory.id).filter(models.Laboratory.listed == True)
    projects = db.query(func.count(models.Project.id)).filter(PUBLIC_PROJECT, models.Project.laboratory_id.in_(listed)).scalar()
    specimens, species = public_specimens_query(
        db, func.count(models.Specimen.id), func.count(distinct(models.Specimen.species))
    ).filter(models.Specimen.laboratory_id.in_(listed)).one()
    return {"laboratories": listed.count(), "projects": projects, "specimens": specimens, "species": species}
