# the collection points of the whole platform, for the map on the home page: the public specimens with
# coordinates of the listed laboratories. Only fields a visitor already sees in each laboratory are sent
from sqlalchemy.orm import Session

import models
from public_numbers import PUBLIC_PROJECT

# enough for the map to be useful while keeping the answer small; the newest points are kept
MAX_POINTS = 5000


def map_points(db: Session, limit: int = MAX_POINTS):
    rows = db.query(
        models.Specimen.id, models.Specimen.catalog_number, models.Specimen.species, models.Specimen.insect_order,
        models.Specimen.locality, models.Specimen.latitude, models.Specimen.longitude,
        models.Specimen.photo_url, models.Specimen.image_file, models.Project.dataset_url,
        models.Laboratory.slug, models.Laboratory.name,
    ).join(models.Project, models.Specimen.project_id == models.Project.id).join(
        models.Laboratory, models.Specimen.laboratory_id == models.Laboratory.id
    ).filter(
        PUBLIC_PROJECT, models.Laboratory.listed == True,
        models.Specimen.latitude.isnot(None), models.Specimen.longitude.isnot(None),
    ).order_by(models.Specimen.id.desc()).limit(limit)
    return [
        {"id": r[0], "catalog_number": r[1], "species": r[2], "insect_order": r[3], "locality": r[4],
         "latitude": r[5], "longitude": r[6], "photo_url": r[7], "image_file": r[8], "dataset_url": r[9],
         "laboratory": r[10], "laboratory_name": r[11]}
        for r in rows
    ]
