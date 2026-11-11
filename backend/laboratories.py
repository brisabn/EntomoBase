import models

# Until the routes become per laboratory (phase 3 of the plan), the whole site works with one laboratory:
# the first one. This is the only place that knows that, so phase 3 replaces it in one go.

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

