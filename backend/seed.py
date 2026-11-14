import random
import secrets
import sys
from datetime import date, datetime, timezone

import models
from database import SessionLocal
from db_setup import initialize_database
from laboratories import DEFAULT_LABORATORY, default_laboratory
from security import hash_password

# demo data for the site; the text values (places, traits, sex, life stage) stay in Portuguese
# because they are shown to the site's users

# field sites: name, latitude, longitude, elevation in meters
SITES = {
    "rio_doce": ("Parque Estadual do Rio Doce", -19.75, -42.60, 250),
    "cipo": ("Parque Nacional da Serra do Cipó", -19.28, -43.59, 1100),
    "itacolomi": ("Parque Estadual do Itacolomi", -20.43, -43.48, 1200),
    "caparao": ("Parque Nacional do Caparaó", -20.42, -41.83, 1400),
    "brigadeiro": ("Parque Estadual da Serra do Brigadeiro", -20.70, -42.47, 1300),
    "pampulha": ("Campus Pampulha, UFMG", -19.869, -43.965, 850),
    "mangabeiras": ("Parque das Mangabeiras, Belo Horizonte", -19.94, -43.91, 1100),
    "pirapitinga": ("Estação Ecológica de Pirapitinga", -18.35, -45.26, 600),
    "paraopeba": ("Floresta Nacional de Paraopeba", -19.28, -44.40, 750),
    "chapada": ("Parque Nacional da Chapada Diamantina", -12.60, -41.45, 900),
}

IDENTIFIERS = ["A. Ribeiro", "M. Costa", "J. Almeida", "L. Fernandes"]
METHODS = ["armadilha de queda", "armadilha luminosa", "rede entomológica", "busca ativa", "armadilha Malaise"]
HABITATS = ["Mata Atlântica", "Cerrado", "Campo rupestre", "Mata de galeria", "Borda de mata"]
COLLECTORS = ["Equipe de campo A", "Equipe de campo B", "N. Silva", "R. Souza"]


# order, family, species and typical measurement ranges (min, max) in mm
def sp(order, family, species, **ranges):
    return {"order": order, "family": family, "species": species, "ranges": ranges}


COLEOPTERA = {
    "Coccinella septempunctata": sp("Coleoptera", "Coccinellidae", "Coccinella septempunctata", body=(6, 8)),
    "Harmonia axyridis": sp("Coleoptera", "Coccinellidae", "Harmonia axyridis", body=(5.5, 8)),
    "Cycloneda sanguinea": sp("Coleoptera", "Coccinellidae", "Cycloneda sanguinea", body=(4, 6)),
    "Hippodamia convergens": sp("Coleoptera", "Coccinellidae", "Hippodamia convergens", body=(4, 6.5)),
    "Eriopis connexa": sp("Coleoptera", "Coccinellidae", "Eriopis connexa", body=(4, 5.5)),
    "Coleomegilla maculata": sp("Coleoptera", "Coccinellidae", "Coleomegilla maculata", body=(4.5, 6)),
    "Dynastes hercules": sp("Coleoptera", "Scarabaeidae", "Dynastes hercules", body=(45, 75), horn=True),
    "Megasoma actaeon": sp("Coleoptera", "Scarabaeidae", "Megasoma actaeon", body=(50, 85), horn=True),
    "Strategus aloeus": sp("Coleoptera", "Scarabaeidae", "Strategus aloeus", body=(30, 50), horn=True),
    "Cyclocephala melanocephala": sp("Coleoptera", "Scarabaeidae", "Cyclocephala melanocephala", body=(11, 14)),
    "Canthon virens": sp("Coleoptera", "Scarabaeidae", "Canthon virens", body=(8, 11)),
    "Dichotomius bos": sp("Coleoptera", "Scarabaeidae", "Dichotomius bos", body=(17, 24)),
    "Phanaeus splendidulus": sp("Coleoptera", "Scarabaeidae", "Phanaeus splendidulus", body=(14, 20)),
    "Deltochilum morbillosum": sp("Coleoptera", "Scarabaeidae", "Deltochilum morbillosum", body=(22, 30)),
    "Coprophanaeus ensifer": sp("Coleoptera", "Scarabaeidae", "Coprophanaeus ensifer", body=(28, 38)),
    "Calosoma granulatum": sp("Coleoptera", "Carabidae", "Calosoma granulatum", body=(22, 28)),
    "Pheropsophus aequinoctialis": sp("Coleoptera", "Carabidae", "Pheropsophus aequinoctialis", body=(14, 18)),
    "Odontochila nodicornis": sp("Coleoptera", "Carabidae", "Odontochila nodicornis", body=(10, 13)),
    "Diabrotica speciosa": sp("Coleoptera", "Chrysomelidae", "Diabrotica speciosa", body=(5, 6.5)),
    "Cerotoma arcuata": sp("Coleoptera", "Chrysomelidae", "Cerotoma arcuata", body=(4.5, 6)),
    "Omophoita aequinoctialis": sp("Coleoptera", "Chrysomelidae", "Omophoita aequinoctialis", body=(5, 7)),
    "Acrocinus longimanus": sp("Coleoptera", "Cerambycidae", "Acrocinus longimanus", body=(40, 75)),
    "Trachyderes thoracicus": sp("Coleoptera", "Cerambycidae", "Trachyderes thoracicus", body=(24, 34)),
    "Rhynchophorus palmarum": sp("Coleoptera", "Curculionidae", "Rhynchophorus palmarum", body=(30, 45)),
    "Cosmopolites sordidus": sp("Coleoptera", "Curculionidae", "Cosmopolites sordidus", body=(10, 14)),
}

LEPIDOPTERA = {
    "Danaus plexippus": sp("Lepidoptera", "Nymphalidae", "Danaus plexippus", wingspan=(90, 110)),
    "Heliconius erato": sp("Lepidoptera", "Nymphalidae", "Heliconius erato", wingspan=(65, 80)),
    "Heliconius melpomene": sp("Lepidoptera", "Nymphalidae", "Heliconius melpomene", wingspan=(60, 75)),
    "Dryas iulia": sp("Lepidoptera", "Nymphalidae", "Dryas iulia", wingspan=(80, 90)),
    "Agraulis vanillae": sp("Lepidoptera", "Nymphalidae", "Agraulis vanillae", wingspan=(62, 80)),
    "Morpho helenor": sp("Lepidoptera", "Nymphalidae", "Morpho helenor", wingspan=(100, 130)),
    "Caligo brasiliensis": sp("Lepidoptera", "Nymphalidae", "Caligo brasiliensis", wingspan=(110, 150)),
    "Biblis hyperia": sp("Lepidoptera", "Nymphalidae", "Biblis hyperia", wingspan=(55, 65)),
    "Siproeta stelenes": sp("Lepidoptera", "Nymphalidae", "Siproeta stelenes", wingspan=(70, 90)),
    "Hamadryas februa": sp("Lepidoptera", "Nymphalidae", "Hamadryas februa", wingspan=(55, 65)),
    "Junonia evarete": sp("Lepidoptera", "Nymphalidae", "Junonia evarete", wingspan=(45, 60)),
    "Battus polydamas": sp("Lepidoptera", "Papilionidae", "Battus polydamas", wingspan=(70, 95)),
    "Heraclides thoas": sp("Lepidoptera", "Papilionidae", "Heraclides thoas", wingspan=(90, 120)),
    "Parides agavus": sp("Lepidoptera", "Papilionidae", "Parides agavus", wingspan=(65, 80)),
    "Phoebis sennae": sp("Lepidoptera", "Pieridae", "Phoebis sennae", wingspan=(55, 70)),
    "Eurema albula": sp("Lepidoptera", "Pieridae", "Eurema albula", wingspan=(35, 45)),
    "Ascia monuste": sp("Lepidoptera", "Pieridae", "Ascia monuste", wingspan=(50, 65)),
    "Pyrisitia nise": sp("Lepidoptera", "Pieridae", "Pyrisitia nise", wingspan=(28, 36)),
    "Menander menander": sp("Lepidoptera", "Riodinidae", "Menander menander", wingspan=(30, 38)),
}

ANTS = {
    "Atta sexdens": sp("Hymenoptera", "Formicidae", "Atta sexdens", weber=(3.2, 4.6), castes=("operária", "soldado")),
    "Atta laevigata": sp("Hymenoptera", "Formicidae", "Atta laevigata", weber=(3.5, 5.0), castes=("operária", "soldado")),
    "Camponotus rufipes": sp("Hymenoptera", "Formicidae", "Camponotus rufipes", weber=(3.0, 4.0), castes=("operária", "soldado")),
    "Camponotus crassus": sp("Hymenoptera", "Formicidae", "Camponotus crassus", weber=(2.4, 3.3), castes=("operária", "soldado")),
    "Pheidole megacephala": sp("Hymenoptera", "Formicidae", "Pheidole megacephala", weber=(0.55, 0.75), castes=("operária", "soldado")),
    "Ectatomma tuberculatum": sp("Hymenoptera", "Formicidae", "Ectatomma tuberculatum", weber=(3.0, 3.6), castes=("operária",)),
    "Solenopsis invicta": sp("Hymenoptera", "Formicidae", "Solenopsis invicta", weber=(0.6, 1.5), castes=("operária",)),
    "Paratrechina longicornis": sp("Hymenoptera", "Formicidae", "Paratrechina longicornis", weber=(0.6, 0.8), castes=("operária",)),
    "Acromyrmex subterraneus": sp("Hymenoptera", "Formicidae", "Acromyrmex subterraneus", weber=(1.6, 2.4), castes=("operária",)),
    "Cephalotes atratus": sp("Hymenoptera", "Formicidae", "Cephalotes atratus", weber=(3.5, 4.5), castes=("operária", "soldado")),
}

BEES_AND_WASPS = {
    "Apis mellifera": sp("Hymenoptera", "Apidae", "Apis mellifera", wing=(8.5, 9.5), intertegular=(1.5, 1.8), castes=("operária",)),
    "Tetragonisca angustula": sp("Hymenoptera", "Apidae", "Tetragonisca angustula", wing=(3.5, 4.2), intertegular=(0.9, 1.1), castes=("operária",)),
    "Melipona quadrifasciata": sp("Hymenoptera", "Apidae", "Melipona quadrifasciata", wing=(6, 7), intertegular=(1.5, 1.7), castes=("operária",)),
    "Trigona spinipes": sp("Hymenoptera", "Apidae", "Trigona spinipes", wing=(5.5, 6.5), intertegular=(1.1, 1.4), castes=("operária",)),
    "Bombus pauloensis": sp("Hymenoptera", "Apidae", "Bombus pauloensis", wing=(11, 14), intertegular=(3.2, 4.2), castes=("operária", "rainha")),
    "Xylocopa frontalis": sp("Hymenoptera", "Apidae", "Xylocopa frontalis", wing=(17, 21), intertegular=(4.5, 5.8), castes=("adulto",)),
    "Euglossa cordata": sp("Hymenoptera", "Apidae", "Euglossa cordata", wing=(9, 11), intertegular=(2.4, 3.0), castes=("adulto",)),
    "Polybia paulista": sp("Hymenoptera", "Vespidae", "Polybia paulista", wing=(9, 11), intertegular=(1.8, 2.2), castes=("operária",)),
    "Synoeca cyanea": sp("Hymenoptera", "Vespidae", "Synoeca cyanea", wing=(17, 20), intertegular=(3.4, 4.0), castes=("operária",)),
    "Polistes versicolor": sp("Hymenoptera", "Vespidae", "Polistes versicolor", wing=(14, 17), intertegular=(2.6, 3.1), castes=("operária",)),
    "Brachygastra lecheguana": sp("Hymenoptera", "Vespidae", "Brachygastra lecheguana", wing=(8, 10), intertegular=(1.8, 2.2), castes=("operária",)),
}


def pick(table, *names):
    return [table[n] for n in names]


# prefix, title, year, group, finished, main locality, field sites, traits, description, repository, publication, species, count
PROJECTS = [
    {
        "prefix": "RDO", "title": "Besouros de serapilheira do Parque Estadual do Rio Doce", "year": 2025, "group": "Coleoptera",
        "finished": True, "locality": "Parque Estadual do Rio Doce", "sites": ["rio_doce"],
        "traits": "Comprimento corporal, Largura do pronoto, Largura elitral",
        "description": "Levantamento de besouros em quatro campanhas sazonais, com medidas morfométricas para comparar tamanho corporal entre famílias.",
        "zenodo": "0000101", "publication": "Manuscrito em preparação",
        "species": pick(COLEOPTERA, "Calosoma granulatum", "Pheropsophus aequinoctialis", "Odontochila nodicornis", "Cyclocephala melanocephala",
                             "Canthon virens", "Dichotomius bos", "Phanaeus splendidulus", "Diabrotica speciosa", "Cerotoma arcuata", "Coccinella septempunctata",
                             "Cycloneda sanguinea", "Trachyderes thoracicus"),
        "n": 150,
    },
    {
        "prefix": "JBH", "title": "Joaninhas urbanas de Belo Horizonte", "year": 2026, "group": "Coleoptera",
        "finished": False, "locality": "Belo Horizonte", "sites": ["pampulha", "mangabeiras"],
        "traits": "Comprimento corporal, Largura do pronoto, Largura elitral",
        "description": "Coleta contínua de Coccinellidae em áreas verdes urbanas para acompanhar a ocorrência de espécies nativas e exóticas.",
        "zenodo": "0000102", "publication": None,
        "species": pick(COLEOPTERA, "Coccinella septempunctata", "Harmonia axyridis", "Cycloneda sanguinea", "Hippodamia convergens", "Eriopis connexa", "Coleomegilla maculata"),
        "n": 80,
    },
    {
        "prefix": "SCP", "title": "Escarabeídeos e dinastíneos da Serra do Cipó", "year": 2024, "group": "Coleoptera",
        "finished": True, "locality": "Parque Nacional da Serra do Cipó", "sites": ["cipo"],
        "traits": "Comprimento corporal, Largura do pronoto, Tamanho do chifre",
        "description": "Scarabaeidae coletados em armadilhas de queda ao longo de um gradiente altitudinal, com registro do tamanho do chifre nos machos.",
        "zenodo": "0000103", "publication": "Resumo apresentado em congresso de entomologia",
        "species": pick(COLEOPTERA, "Dynastes hercules", "Megasoma actaeon", "Strategus aloeus", "Cyclocephala melanocephala", "Dichotomius bos",
                             "Deltochilum morbillosum", "Coprophanaeus ensifer", "Phanaeus splendidulus", "Canthon virens"),
        "n": 100,
    },
    {
        "prefix": "ITA", "title": "Borboletas frugívoras do Itacolomi", "year": 2025, "group": "Lepidoptera",
        "finished": True, "locality": "Parque Estadual do Itacolomi", "sites": ["itacolomi"],
        "traits": "Envergadura alar, Comprimento da asa anterior",
        "description": "Captura com armadilhas Van Someren-Rydon iscadas com banana fermentada, em transectos de borda e interior de mata.",
        "zenodo": "0000104", "publication": "Manuscrito em revisão",
        "species": pick(LEPIDOPTERA, "Morpho helenor", "Caligo brasiliensis", "Biblis hyperia", "Siproeta stelenes", "Hamadryas februa", "Junonia evarete",
                             "Dryas iulia", "Agraulis vanillae", "Battus polydamas", "Heraclides thoas", "Phoebis sennae", "Menander menander"),
        "n": 140,
    },
    {
        "prefix": "CAP", "title": "Heliconíneos da Mata Atlântica do Caparaó", "year": 2026, "group": "Lepidoptera",
        "finished": False, "locality": "Parque Nacional do Caparaó", "sites": ["caparao"],
        "traits": "Envergadura alar, Comprimento da asa anterior",
        "description": "Amostragem de Heliconiini em diferentes altitudes para estudar variação de tamanho e padrões de cor.",
        "zenodo": "0000105", "publication": None,
        "species": pick(LEPIDOPTERA, "Heliconius erato", "Heliconius melpomene", "Dryas iulia", "Agraulis vanillae", "Danaus plexippus", "Parides agavus"),
        "n": 70,
    },
    {
        "prefix": "BRI", "title": "Formigas de serapilheira da Serra do Brigadeiro", "year": 2025, "group": "Formicidae",
        "finished": True, "locality": "Parque Estadual da Serra do Brigadeiro", "sites": ["brigadeiro"],
        "traits": "Largura da cápsula cefálica, Comprimento do escapo, Comprimento de Weber",
        "description": "Formigas extraídas de serapilheira com Winkler, medidas para análise de traços funcionais ao longo da altitude.",
        "zenodo": "0000106", "publication": "Manuscrito em preparação",
        "species": list(ANTS.values()),
        "n": 150,
    },
    {
        "prefix": "CER", "title": "Abelhas e vespas de áreas de cerrado", "year": 2024, "group": "Hymenoptera",
        "finished": True, "locality": "Cerrado de Minas Gerais", "sites": ["pirapitinga", "paraopeba"],
        "traits": "Comprimento da asa, Distância intertegular",
        "description": "Himenópteros coletados com rede entomológica e pan traps em áreas de cerrado, com medidas usadas para estimar alcance de forrageio.",
        "zenodo": "0000107", "publication": "Dissertação de mestrado, em andamento",
        "species": list(BEES_AND_WASPS.values()),
        "n": 110,
    },
    {
        "prefix": "CHD", "title": "Polinizadores da Chapada Diamantina", "year": 2023, "group": "Hymenoptera",
        "finished": True, "locality": "Parque Nacional da Chapada Diamantina", "sites": ["chapada"],
        "traits": "Comprimento da asa, Distância intertegular",
        "description": "Inventário de abelhas em campos rupestres. Os dados ainda não foram depositados em um repositório.",
        "zenodo": None, "publication": None,
        "species": pick(BEES_AND_WASPS, "Apis mellifera", "Tetragonisca angustula", "Melipona quadrifasciata", "Trigona spinipes", "Euglossa cordata", "Xylocopa frontalis"),
        "n": 70,
        # shared with reviewers before publishing: open only by its link
        "visibility": "unlisted",
    },
    # the other demo laboratories. Some codes repeat those of the first laboratory (RDO-0001, BRI-0001...),
    # which is allowed between laboratories and lets the isolation be tried by hand
    {
        "lab": "borboletas", "prefix": "RDO", "title": "Borboletas do Parque Estadual do Rio Doce", "year": 2025, "group": "Lepidoptera",
        "finished": True, "locality": "Parque Estadual do Rio Doce", "sites": ["rio_doce"],
        "traits": "Envergadura alar, Comprimento da asa anterior",
        "description": "Borboletas amostradas nas mesmas trilhas do levantamento de besouros, para comparar a fauna das duas ordens.",
        "zenodo": "0000201", "publication": None,
        "species": pick(LEPIDOPTERA, "Morpho helenor", "Heliconius erato", "Dryas iulia", "Battus polydamas", "Phoebis sennae", "Junonia evarete", "Eurema albula"),
        "n": 60,
    },
    {
        "lab": "borboletas", "prefix": "SBR", "title": "Papilionídeos da Serra do Brigadeiro", "year": 2025, "group": "Lepidoptera",
        "finished": True, "locality": "Parque Estadual da Serra do Brigadeiro", "sites": ["brigadeiro"],
        "traits": "Envergadura alar, Comprimento da asa anterior",
        "description": "Dados enviados aos revisores de um artigo antes da publicação.",
        "zenodo": "0000202", "publication": "Manuscrito em revisão",
        "species": pick(LEPIDOPTERA, "Battus polydamas", "Heraclides thoas", "Parides agavus"),
        "n": 40, "visibility": "unlisted",
    },
    {
        "lab": "borboletas", "prefix": "PAM", "title": "Borboletas do campus Pampulha", "year": 2026, "group": "Lepidoptera",
        "finished": False, "locality": "Campus Pampulha, UFMG", "sites": ["pampulha"],
        "traits": "Envergadura alar",
        "description": "Coleta em andamento com alunos de graduação.",
        "zenodo": None, "publication": None,
        "species": pick(LEPIDOPTERA, "Ascia monuste", "Pyrisitia nise", "Agraulis vanillae", "Danaus plexippus"),
        "n": 30,
    },
    {
        "lab": "formigas", "prefix": "BRI", "title": "Formigas de áreas verdes de Belo Horizonte", "year": 2024, "group": "Formicidae",
        "finished": True, "locality": "Belo Horizonte", "sites": ["mangabeiras", "pampulha"],
        "traits": "Largura da cápsula cefálica, Comprimento de Weber",
        "description": "Iscas de sardinha e mel em praças e parques, para comparar a fauna de formigas urbanas.",
        "zenodo": "0000301", "publication": None,
        "species": pick(ANTS, "Atta sexdens", "Camponotus rufipes", "Pheidole megacephala", "Solenopsis invicta", "Paratrechina longicornis"),
        "n": 50,
    },
]

# the demo laboratories besides the first one; "formigas" is left out of the public list, so it opens only
# by its address
DEMO_LABORATORIES = [
    {"slug": "borboletas", "name": "Laboratório de Lepidoptera (demonstração)", "institution": "Universidade Fictícia",
     "collection_code": "LEPF", "listed": True,
     "about": "Laboratório fictício, criado para demonstrar o EntomoBase.\n\n"
              "Estudamos borboletas frugívoras e papilionídeos de unidades de conservação de Minas Gerais, "
              "com armadilhas de isca e busca ativa. Cada projeto publica os espécimes com fotos e medidas das asas.",
     "contact_email": "lepidoptera@entomobase.test",
     "team": [{"name": "Carla (demonstração)", "role": "Coordenadora"},
              {"name": "Davi (demonstração)", "role": "Mestrando em Ecologia"},
              {"name": "Elisa (demonstração)", "role": "Iniciação científica"}]},
    {"slug": "formigas", "name": "Grupo de Mirmecologia (demonstração)", "institution": "Instituto Fictício de Biologia",
     "collection_code": "MIRF", "listed": False,
     "about": "Grupo fictício, criado para demonstrar o EntomoBase. Ele fica fora da lista pública e só abre pelo endereço.",
     "contact_email": "formigas@entomobase.test",
     "team": [{"name": "Eva (demonstração)", "role": "Coordenadora"}]},
]

# one demo account for each kind of person; the e-mails use the .test domain, which never exists
FIRST = DEFAULT_LABORATORY["slug"]
DEMO_USERS = [
    {"email": "super@entomobase.test", "name": "Administração da plataforma", "superadmin": True, "roles": {}},
    {"email": "admin.ufmg@entomobase.test", "name": "Ana (administradora)", "roles": {FIRST: "admin"}},
    {"email": "pesquisa.ufmg@entomobase.test", "name": "Bruno (pesquisador)", "roles": {FIRST: "researcher"}},
    {"email": "admin.borboletas@entomobase.test", "name": "Carla (dois laboratórios)", "roles": {"borboletas": "admin", FIRST: "researcher"}},
    {"email": "pesquisa.borboletas@entomobase.test", "name": "Davi (pesquisador)", "roles": {"borboletas": "researcher"}},
    {"email": "admin.formigas@entomobase.test", "name": "Eva (administradora)", "roles": {"formigas": "admin"}},
    {"email": "sem.laboratorio@entomobase.test", "name": "Fábio (sem laboratório)", "roles": {}},
]


def measurements_for(rng, species, traits, sex):
    r = species["ranges"]
    result = []
    names = [t.strip() for t in traits.split(",")]
    if "body" in r:
        body = rng.uniform(*r["body"])
        pronotum_width, elytral_width = body * rng.uniform(0.30, 0.40), body * rng.uniform(0.42, 0.55)
        values = {"Comprimento corporal": body, "Largura do pronoto": pronotum_width, "Largura elitral": elytral_width}
        if r.get("horn") and sex == "macho":
            values["Tamanho do chifre"] = body * rng.uniform(0.18, 0.32)
    elif "wingspan" in r:
        span = rng.uniform(*r["wingspan"])
        values = {"Envergadura alar": span, "Comprimento da asa anterior": span * rng.uniform(0.38, 0.46)}
    elif "weber" in r:
        weber = rng.uniform(*r["weber"])
        values = {"Comprimento de Weber": weber, "Largura da cápsula cefálica": weber * rng.uniform(0.7, 1.05), "Comprimento do escapo": weber * rng.uniform(0.7, 1.1)}
    else:
        values = {"Comprimento da asa": rng.uniform(*r["wing"]), "Distância intertegular": rng.uniform(*r["intertegular"])}
    for name in names:
        if name in values:
            result.append(models.Measurement(trait=name, value=round(values[name], 2), unit="mm"))
    return result


# finished projects are public and the others private, unless the project says otherwise
def visibility_of(cfg):
    return cfg.get("visibility") or ("public" if cfg["finished"] else "private")


def laboratory_of(db, cfg):
    if "lab" not in cfg:
        return default_laboratory(db)
    return db.query(models.Laboratory).filter(models.Laboratory.slug == cfg["lab"]).one()


def create_laboratories(db):
    default_laboratory(db)
    for data in DEMO_LABORATORIES:
        if db.query(models.Laboratory).filter(models.Laboratory.slug == data["slug"]).first():
            print(f"already exists: laboratory {data['slug']}")
            continue
        db.add(models.Laboratory(**data, license=DEFAULT_LABORATORY["license"]))
    db.flush()


# the accounts are created confirmed, with a random password shown only now; an account that already
# exists keeps its password and roles
def create_users(db):
    created = []
    for data in DEMO_USERS:
        if db.query(models.User).filter(models.User.email == data["email"]).first():
            print(f"already exists: {data['email']} (password unchanged)")
            continue
        password = secrets.token_urlsafe(9)
        user = models.User(email=data["email"], name=data["name"], password_hash=hash_password(password),
                           is_superadmin=data.get("superadmin", False), email_verified_at=datetime.now(timezone.utc).replace(tzinfo=None))
        for slug, role in data["roles"].items():
            lab = db.query(models.Laboratory).filter(models.Laboratory.slug == slug).one()
            user.memberships.append(models.Membership(laboratory_id=lab.id, role=role))
        db.add(user)
        created.append((data, password))
    db.flush()
    if created:
        print("\nDemo accounts (the passwords are shown only now):")
        for data, password in created:
            roles = ", ".join(f"{role} of {slug}" for slug, role in data["roles"].items())
            kind = "platform administrator" if data.get("superadmin") else roles or "no laboratory"
            print(f"  {data['email']:<38} {password:<14} {kind}")
        print()


def create_project(db, cfg, rng):
    if db.query(models.Project).filter(models.Project.title == cfg["title"]).first():
        print(f"already exists: {cfg['title']}")
        return 0
    laboratory = laboratory_of(db, cfg)
    visibility = visibility_of(cfg)
    project = models.Project(
        laboratory_id=laboratory.id, visibility=visibility,
        # the same kind of link the API makes (authorization.new_share_token), which the seed does not import
        # so that it runs without SECRET_KEY
        share_token=secrets.token_urlsafe(24) if visibility == "unlisted" else None,
        title=cfg["title"], year=cfg["year"], insect_group=cfg["group"], measured_traits=cfg["traits"], locality=cfg["locality"],
        dataset_url=f"https://zenodo.org/records/{cfg['zenodo']}" if cfg["zenodo"] else None,
        finished=cfg["finished"], linked_publication=cfg["publication"], description=cfg["description"],
    )
    db.add(project)
    db.flush()

    # field campaigns: one date and one site per campaign
    campaigns = []
    for _ in range(rng.randint(4, 6)):
        site = SITES[rng.choice(cfg["sites"])]
        max_month = 12 if cfg["year"] < 2026 else 9
        campaigns.append((site, date(cfg["year"] - rng.choice([0, 0, 1]) if cfg["year"] < 2026 else 2026, rng.randint(1, max_month), rng.randint(1, 28))))

    species = cfg["species"]
    draw = [s for s in species for _ in range(3)]
    draw += rng.choices(species, weights=[rng.uniform(0.3, 3) for _ in species], k=max(cfg["n"] - len(draw), 0))
    rng.shuffle(draw)

    for i, s in enumerate(draw, start=1):
        number = f"{cfg['prefix']}-{i:04d}"
        (site_name, lat, lng, elevation), when = rng.choice(campaigns)
        has_coordinates = rng.random() > 0.05
        sex = rng.choice(["macho", "fêmea"]) if cfg["group"] in ("Coleoptera", "Lepidoptera") else "fêmea"
        if cfg["group"] == "Coleoptera" and rng.random() < 0.15:
            sex = "indeterminado"
        if "castes" in s["ranges"]:
            stage = rng.choice(s["ranges"]["castes"])
        else:
            stage = "adulto"
        extra = random.Random(number)
        on_loan = extra.random() < 0.04
        specimen = models.Specimen(
            laboratory_id=laboratory.id,
            identified_by=extra.choice(IDENTIFIERS), identification_date=when,
            sampling_method=extra.choice(METHODS), habitat=extra.choice(HABITATS),
            collector=extra.choice(COLLECTORS), field_number=f"C{extra.randint(100, 999)}",
            storage_location=f"Armário {extra.randint(1, 4)}, caixa {extra.randint(1, 30)}",
            loan_status="emprestado" if on_loan else "no acervo",
            loaned_to="Museu de Zoologia (fictício)" if on_loan else None,
            catalog_number=number, insect_order=s["order"], family=s["family"], species=s["species"],
            collection_date=when, locality=site_name,
            latitude=round(lat + rng.gauss(0, 0.035), 5) if has_coordinates else None,
            longitude=round(lng + rng.gauss(0, 0.035), 5) if has_coordinates else None,
            elevation_m=round(elevation + rng.gauss(0, 70)) if has_coordinates else None,
            sex=sex, life_stage=stage,
            image_file=f"{number}.svg" if rng.random() > 0.08 else None,
            project_id=project.id,
        )
        specimen.measurements = measurements_for(rng, s, cfg["traits"], sex)
        db.add(specimen)
    return len(draw)


def fill_missing_families(db):
    known = {}
    for table in (COLEOPTERA, LEPIDOPTERA, ANTS, BEES_AND_WASPS):
        for name, s in table.items():
            known[name] = s["family"]
    for specimen in db.query(models.Specimen).filter(models.Specimen.family.is_(None)).all():
        if specimen.species in known:
            specimen.family = known[specimen.species]


# removes what the seed created: its projects, its accounts and its extra laboratories. The first laboratory
# stays, and so does a demo laboratory that has data of its own
def remove_demo_data(db):
    titles = {p["title"] for p in PROJECTS}
    n = 0
    for p in db.query(models.Project).filter(models.Project.title.in_(titles)).all():
        db.delete(p)
        n += 1
    db.flush()
    print(f"{n} demo projects removed (with their specimens)")
    users = db.query(models.User).filter(models.User.email.in_([u["email"] for u in DEMO_USERS])).all()
    for user in users:
        db.delete(user)
    print(f"{len(users)} demo accounts removed")
    db.flush()
    for data in DEMO_LABORATORIES:
        lab = db.query(models.Laboratory).filter(models.Laboratory.slug == data["slug"]).first()
        if lab is None:
            continue
        in_use = db.query(models.Project).filter(models.Project.laboratory_id == lab.id).count() \
            + db.query(models.Specimen).filter(models.Specimen.laboratory_id == lab.id).count()
        if in_use:
            print(f"kept: laboratory {lab.slug}, which has data that the seed did not create")
            continue
        db.delete(lab)
        print(f"removed: laboratory {lab.slug}")
    db.commit()


def main():
    initialize_database()
    db = SessionLocal()
    if "--remove" in sys.argv:
        remove_demo_data(db)
        db.close()
        return
    create_laboratories(db)
    create_users(db)
    rng = random.Random(2026)
    total = 0
    for cfg in PROJECTS:
        total += create_project(db, cfg, rng)
    fill_missing_families(db)
    db.commit()
    db.close()
    print(f"{total} demo specimens created")


if __name__ == "__main__":
    main()
