import models

# Until the routes become per laboratory (phase 3 of the plan), the whole site works with one laboratory:
# the first one. These helpers are the only place that knows that, so phase 3 replaces them in one go.

# what the first laboratory looks like when none exists (a fresh test database, or the seed on an empty one)
DEFAULT_LABORATORY = {
    "slug": "ufmg",
    "name": "EntomoBase UFMG",
    "institution": "UFMG",
    "collection_code": "EntomoBase",
    "license": "http://creativecommons.org/licenses/by/4.0/legalcode",
    "listed": True,
}


def default_laboratory(db) -> models.Laboratory:
    laboratory = db.query(models.Laboratory).order_by(models.Laboratory.id).first()
    if laboratory is None:
        laboratory = models.Laboratory(**DEFAULT_LABORATORY)
        db.add(laboratory)
        db.commit()
        db.refresh(laboratory)
    return laboratory


# a specimen always belongs to the laboratory of its project; without a project it goes to the default one
def laboratory_id_for_project(db, project_id) -> int:
    if project_id is not None:
        project = db.get(models.Project, project_id)
        if project is not None:
            return project.laboratory_id
    return default_laboratory(db).id


# until visibility is edited on its own (phase 2), it follows the status: a finished project is public
def visibility_from_status(finished) -> str:
    return "public" if finished else "private"
