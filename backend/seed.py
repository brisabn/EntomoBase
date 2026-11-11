import random
import sys
from datetime import date

import models
from database import SessionLocal
from inicializacao import inicializar_banco

# lugares de coleta: nome, latitude, longitude, altitude em metros
LOCAIS = {
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

# ordem, família, espécie, medidas típicas (mínimo, máximo) em mm
DETERMINADORES = ["A. Ribeiro", "M. Costa", "J. Almeida", "L. Fernandes"]
METODOS = ["armadilha de queda", "armadilha luminosa", "rede entomológica", "busca ativa", "armadilha Malaise"]
HABITATS = ["Mata Atlântica", "Cerrado", "Campo rupestre", "Mata de galeria", "Borda de mata"]
COLETORES = ["Equipe de campo A", "Equipe de campo B", "N. Silva", "R. Souza"]


def esp(ordem, familia, especie, **medidas):
    return {"ordem": ordem, "familia": familia, "especie": especie, "medidas": medidas}


COLEOPTERA = {
    "Coccinella septempunctata": esp("Coleoptera", "Coccinellidae", "Coccinella septempunctata", c=(6, 8)),
    "Harmonia axyridis": esp("Coleoptera", "Coccinellidae", "Harmonia axyridis", c=(5.5, 8)),
    "Cycloneda sanguinea": esp("Coleoptera", "Coccinellidae", "Cycloneda sanguinea", c=(4, 6)),
    "Hippodamia convergens": esp("Coleoptera", "Coccinellidae", "Hippodamia convergens", c=(4, 6.5)),
    "Eriopis connexa": esp("Coleoptera", "Coccinellidae", "Eriopis connexa", c=(4, 5.5)),
    "Coleomegilla maculata": esp("Coleoptera", "Coccinellidae", "Coleomegilla maculata", c=(4.5, 6)),
    "Dynastes hercules": esp("Coleoptera", "Scarabaeidae", "Dynastes hercules", c=(45, 75), chifre=True),
    "Megasoma actaeon": esp("Coleoptera", "Scarabaeidae", "Megasoma actaeon", c=(50, 85), chifre=True),
    "Strategus aloeus": esp("Coleoptera", "Scarabaeidae", "Strategus aloeus", c=(30, 50), chifre=True),
    "Cyclocephala melanocephala": esp("Coleoptera", "Scarabaeidae", "Cyclocephala melanocephala", c=(11, 14)),
    "Canthon virens": esp("Coleoptera", "Scarabaeidae", "Canthon virens", c=(8, 11)),
    "Dichotomius bos": esp("Coleoptera", "Scarabaeidae", "Dichotomius bos", c=(17, 24)),
    "Phanaeus splendidulus": esp("Coleoptera", "Scarabaeidae", "Phanaeus splendidulus", c=(14, 20)),
    "Deltochilum morbillosum": esp("Coleoptera", "Scarabaeidae", "Deltochilum morbillosum", c=(22, 30)),
    "Coprophanaeus ensifer": esp("Coleoptera", "Scarabaeidae", "Coprophanaeus ensifer", c=(28, 38)),
    "Calosoma granulatum": esp("Coleoptera", "Carabidae", "Calosoma granulatum", c=(22, 28)),
    "Pheropsophus aequinoctialis": esp("Coleoptera", "Carabidae", "Pheropsophus aequinoctialis", c=(14, 18)),
    "Odontochila nodicornis": esp("Coleoptera", "Carabidae", "Odontochila nodicornis", c=(10, 13)),
    "Diabrotica speciosa": esp("Coleoptera", "Chrysomelidae", "Diabrotica speciosa", c=(5, 6.5)),
    "Cerotoma arcuata": esp("Coleoptera", "Chrysomelidae", "Cerotoma arcuata", c=(4.5, 6)),
    "Omophoita aequinoctialis": esp("Coleoptera", "Chrysomelidae", "Omophoita aequinoctialis", c=(5, 7)),
    "Acrocinus longimanus": esp("Coleoptera", "Cerambycidae", "Acrocinus longimanus", c=(40, 75)),
    "Trachyderes thoracicus": esp("Coleoptera", "Cerambycidae", "Trachyderes thoracicus", c=(24, 34)),
    "Rhynchophorus palmarum": esp("Coleoptera", "Curculionidae", "Rhynchophorus palmarum", c=(30, 45)),
    "Cosmopolites sordidus": esp("Coleoptera", "Curculionidae", "Cosmopolites sordidus", c=(10, 14)),
}

LEPIDOPTERA = {
    "Danaus plexippus": esp("Lepidoptera", "Nymphalidae", "Danaus plexippus", e=(90, 110)),
    "Heliconius erato": esp("Lepidoptera", "Nymphalidae", "Heliconius erato", e=(65, 80)),
    "Heliconius melpomene": esp("Lepidoptera", "Nymphalidae", "Heliconius melpomene", e=(60, 75)),
    "Dryas iulia": esp("Lepidoptera", "Nymphalidae", "Dryas iulia", e=(80, 90)),
    "Agraulis vanillae": esp("Lepidoptera", "Nymphalidae", "Agraulis vanillae", e=(62, 80)),
    "Morpho helenor": esp("Lepidoptera", "Nymphalidae", "Morpho helenor", e=(100, 130)),
    "Caligo brasiliensis": esp("Lepidoptera", "Nymphalidae", "Caligo brasiliensis", e=(110, 150)),
    "Biblis hyperia": esp("Lepidoptera", "Nymphalidae", "Biblis hyperia", e=(55, 65)),
    "Siproeta stelenes": esp("Lepidoptera", "Nymphalidae", "Siproeta stelenes", e=(70, 90)),
    "Hamadryas februa": esp("Lepidoptera", "Nymphalidae", "Hamadryas februa", e=(55, 65)),
    "Junonia evarete": esp("Lepidoptera", "Nymphalidae", "Junonia evarete", e=(45, 60)),
    "Battus polydamas": esp("Lepidoptera", "Papilionidae", "Battus polydamas", e=(70, 95)),
    "Heraclides thoas": esp("Lepidoptera", "Papilionidae", "Heraclides thoas", e=(90, 120)),
    "Parides agavus": esp("Lepidoptera", "Papilionidae", "Parides agavus", e=(65, 80)),
    "Phoebis sennae": esp("Lepidoptera", "Pieridae", "Phoebis sennae", e=(55, 70)),
    "Eurema albula": esp("Lepidoptera", "Pieridae", "Eurema albula", e=(35, 45)),
    "Ascia monuste": esp("Lepidoptera", "Pieridae", "Ascia monuste", e=(50, 65)),
    "Pyrisitia nise": esp("Lepidoptera", "Pieridae", "Pyrisitia nise", e=(28, 36)),
    "Menander menander": esp("Lepidoptera", "Riodinidae", "Menander menander", e=(30, 38)),
}

FORMIGAS = {
    "Atta sexdens": esp("Hymenoptera", "Formicidae", "Atta sexdens", w=(3.2, 4.6), casta=("operária", "soldado")),
    "Atta laevigata": esp("Hymenoptera", "Formicidae", "Atta laevigata", w=(3.5, 5.0), casta=("operária", "soldado")),
    "Camponotus rufipes": esp("Hymenoptera", "Formicidae", "Camponotus rufipes", w=(3.0, 4.0), casta=("operária", "soldado")),
    "Camponotus crassus": esp("Hymenoptera", "Formicidae", "Camponotus crassus", w=(2.4, 3.3), casta=("operária", "soldado")),
    "Pheidole megacephala": esp("Hymenoptera", "Formicidae", "Pheidole megacephala", w=(0.55, 0.75), casta=("operária", "soldado")),
    "Ectatomma tuberculatum": esp("Hymenoptera", "Formicidae", "Ectatomma tuberculatum", w=(3.0, 3.6), casta=("operária",)),
    "Solenopsis invicta": esp("Hymenoptera", "Formicidae", "Solenopsis invicta", w=(0.6, 1.5), casta=("operária",)),
    "Paratrechina longicornis": esp("Hymenoptera", "Formicidae", "Paratrechina longicornis", w=(0.6, 0.8), casta=("operária",)),
    "Acromyrmex subterraneus": esp("Hymenoptera", "Formicidae", "Acromyrmex subterraneus", w=(1.6, 2.4), casta=("operária",)),
    "Cephalotes atratus": esp("Hymenoptera", "Formicidae", "Cephalotes atratus", w=(3.5, 4.5), casta=("operária", "soldado")),
}

ABELHAS = {
    "Apis mellifera": esp("Hymenoptera", "Apidae", "Apis mellifera", a=(8.5, 9.5), it=(1.5, 1.8), casta=("operária",)),
    "Tetragonisca angustula": esp("Hymenoptera", "Apidae", "Tetragonisca angustula", a=(3.5, 4.2), it=(0.9, 1.1), casta=("operária",)),
    "Melipona quadrifasciata": esp("Hymenoptera", "Apidae", "Melipona quadrifasciata", a=(6, 7), it=(1.5, 1.7), casta=("operária",)),
    "Trigona spinipes": esp("Hymenoptera", "Apidae", "Trigona spinipes", a=(5.5, 6.5), it=(1.1, 1.4), casta=("operária",)),
    "Bombus pauloensis": esp("Hymenoptera", "Apidae", "Bombus pauloensis", a=(11, 14), it=(3.2, 4.2), casta=("operária", "rainha")),
    "Xylocopa frontalis": esp("Hymenoptera", "Apidae", "Xylocopa frontalis", a=(17, 21), it=(4.5, 5.8), casta=("adulto",)),
    "Euglossa cordata": esp("Hymenoptera", "Apidae", "Euglossa cordata", a=(9, 11), it=(2.4, 3.0), casta=("adulto",)),
    "Polybia paulista": esp("Hymenoptera", "Vespidae", "Polybia paulista", a=(9, 11), it=(1.8, 2.2), casta=("operária",)),
    "Synoeca cyanea": esp("Hymenoptera", "Vespidae", "Synoeca cyanea", a=(17, 20), it=(3.4, 4.0), casta=("operária",)),
    "Polistes versicolor": esp("Hymenoptera", "Vespidae", "Polistes versicolor", a=(14, 17), it=(2.6, 3.1), casta=("operária",)),
    "Brachygastra lecheguana": esp("Hymenoptera", "Vespidae", "Brachygastra lecheguana", a=(8, 10), it=(1.8, 2.2), casta=("operária",)),
}


def escolher(tabela, *nomes):
    return [tabela[n] for n in nomes]


# prefixo, título, ano, grupo, concluído, local principal, locais de campanha, traços, descrição, repositório, publicação, espécies, quantidade
PROJETOS = [
    {
        "prefixo": "RDO", "titulo": "Besouros de serapilheira do Parque Estadual do Rio Doce", "ano": 2025, "grupo": "Coleoptera",
        "finalizado": True, "local": "Parque Estadual do Rio Doce", "locais": ["rio_doce"],
        "tracos": "Comprimento corporal, Largura do pronoto, Largura elitral",
        "descricao": "Levantamento de besouros em quatro campanhas sazonais, com medidas morfométricas para comparar tamanho corporal entre famílias.",
        "zenodo": "0000101", "publicacao": "Manuscrito em preparação",
        "especies": escolher(COLEOPTERA, "Calosoma granulatum", "Pheropsophus aequinoctialis", "Odontochila nodicornis", "Cyclocephala melanocephala",
                             "Canthon virens", "Dichotomius bos", "Phanaeus splendidulus", "Diabrotica speciosa", "Cerotoma arcuata", "Coccinella septempunctata",
                             "Cycloneda sanguinea", "Trachyderes thoracicus"),
        "n": 150,
    },
    {
        "prefixo": "JBH", "titulo": "Joaninhas urbanas de Belo Horizonte", "ano": 2026, "grupo": "Coleoptera",
        "finalizado": False, "local": "Belo Horizonte", "locais": ["pampulha", "mangabeiras"],
        "tracos": "Comprimento corporal, Largura do pronoto, Largura elitral",
        "descricao": "Coleta contínua de Coccinellidae em áreas verdes urbanas para acompanhar a ocorrência de espécies nativas e exóticas.",
        "zenodo": "0000102", "publicacao": None,
        "especies": escolher(COLEOPTERA, "Coccinella septempunctata", "Harmonia axyridis", "Cycloneda sanguinea", "Hippodamia convergens", "Eriopis connexa", "Coleomegilla maculata"),
        "n": 80,
    },
    {
        "prefixo": "SCP", "titulo": "Escarabeídeos e dinastíneos da Serra do Cipó", "ano": 2024, "grupo": "Coleoptera",
        "finalizado": True, "local": "Parque Nacional da Serra do Cipó", "locais": ["cipo"],
        "tracos": "Comprimento corporal, Largura do pronoto, Tamanho do chifre",
        "descricao": "Scarabaeidae coletados em armadilhas de queda ao longo de um gradiente altitudinal, com registro do tamanho do chifre nos machos.",
        "zenodo": "0000103", "publicacao": "Resumo apresentado em congresso de entomologia",
        "especies": escolher(COLEOPTERA, "Dynastes hercules", "Megasoma actaeon", "Strategus aloeus", "Cyclocephala melanocephala", "Dichotomius bos",
                             "Deltochilum morbillosum", "Coprophanaeus ensifer", "Phanaeus splendidulus", "Canthon virens"),
        "n": 100,
    },
    {
        "prefixo": "ITA", "titulo": "Borboletas frugívoras do Itacolomi", "ano": 2025, "grupo": "Lepidoptera",
        "finalizado": True, "local": "Parque Estadual do Itacolomi", "locais": ["itacolomi"],
        "tracos": "Envergadura alar, Comprimento da asa anterior",
        "descricao": "Captura com armadilhas Van Someren-Rydon iscadas com banana fermentada, em transectos de borda e interior de mata.",
        "zenodo": "0000104", "publicacao": "Manuscrito em revisão",
        "especies": escolher(LEPIDOPTERA, "Morpho helenor", "Caligo brasiliensis", "Biblis hyperia", "Siproeta stelenes", "Hamadryas februa", "Junonia evarete",
                             "Dryas iulia", "Agraulis vanillae", "Battus polydamas", "Heraclides thoas", "Phoebis sennae", "Menander menander"),
        "n": 140,
    },
    {
        "prefixo": "CAP", "titulo": "Heliconíneos da Mata Atlântica do Caparaó", "ano": 2026, "grupo": "Lepidoptera",
        "finalizado": False, "local": "Parque Nacional do Caparaó", "locais": ["caparao"],
        "tracos": "Envergadura alar, Comprimento da asa anterior",
        "descricao": "Amostragem de Heliconiini em diferentes altitudes para estudar variação de tamanho e padrões de cor.",
        "zenodo": "0000105", "publicacao": None,
        "especies": escolher(LEPIDOPTERA, "Heliconius erato", "Heliconius melpomene", "Dryas iulia", "Agraulis vanillae", "Danaus plexippus", "Parides agavus"),
        "n": 70,
    },
    {
        "prefixo": "BRI", "titulo": "Formigas de serapilheira da Serra do Brigadeiro", "ano": 2025, "grupo": "Formicidae",
        "finalizado": True, "local": "Parque Estadual da Serra do Brigadeiro", "locais": ["brigadeiro"],
        "tracos": "Largura da cápsula cefálica, Comprimento do escapo, Comprimento de Weber",
        "descricao": "Formigas extraídas de serapilheira com Winkler, medidas para análise de traços funcionais ao longo da altitude.",
        "zenodo": "0000106", "publicacao": "Manuscrito em preparação",
        "especies": list(FORMIGAS.values()),
        "n": 150,
    },
    {
        "prefixo": "CER", "titulo": "Abelhas e vespas de áreas de cerrado", "ano": 2024, "grupo": "Hymenoptera",
        "finalizado": True, "local": "Cerrado de Minas Gerais", "locais": ["pirapitinga", "paraopeba"],
        "tracos": "Comprimento da asa, Distância intertegular",
        "descricao": "Himenópteros coletados com rede entomológica e pan traps em áreas de cerrado, com medidas usadas para estimar alcance de forrageio.",
        "zenodo": "0000107", "publicacao": "Dissertação de mestrado, em andamento",
        "especies": list(ABELHAS.values()),
        "n": 110,
    },
    {
        "prefixo": "CHD", "titulo": "Polinizadores da Chapada Diamantina", "ano": 2023, "grupo": "Hymenoptera",
        "finalizado": True, "local": "Parque Nacional da Chapada Diamantina", "locais": ["chapada"],
        "tracos": "Comprimento da asa, Distância intertegular",
        "descricao": "Inventário de abelhas em campos rupestres. Os dados ainda não foram depositados em um repositório.",
        "zenodo": None, "publicacao": None,
        "especies": escolher(ABELHAS, "Apis mellifera", "Tetragonisca angustula", "Melipona quadrifasciata", "Trigona spinipes", "Euglossa cordata", "Xylocopa frontalis"),
        "n": 70,
    },
]


def medidas_para(rng, especie, tracos, sexo):
    m = especie["medidas"]
    lista = []
    nomes = [t.strip() for t in tracos.split(",")]
    if "c" in m:
        c = rng.uniform(*m["c"])
        largura_pronoto, largura_elitral = c * rng.uniform(0.30, 0.40), c * rng.uniform(0.42, 0.55)
        valores = {"Comprimento corporal": c, "Largura do pronoto": largura_pronoto, "Largura elitral": largura_elitral}
        if m.get("chifre") and sexo == "macho":
            valores["Tamanho do chifre"] = c * rng.uniform(0.18, 0.32)
    elif "e" in m:
        e = rng.uniform(*m["e"])
        valores = {"Envergadura alar": e, "Comprimento da asa anterior": e * rng.uniform(0.38, 0.46)}
    elif "w" in m:
        w = rng.uniform(*m["w"])
        valores = {"Comprimento de Weber": w, "Largura da cápsula cefálica": w * rng.uniform(0.7, 1.05), "Comprimento do escapo": w * rng.uniform(0.7, 1.1)}
    else:
        valores = {"Comprimento da asa": rng.uniform(*m["a"]), "Distância intertegular": rng.uniform(*m["it"])}
    for nome in nomes:
        if nome in valores:
            lista.append(models.Medida(traco=nome, valor=round(valores[nome], 2), unidade="mm"))
    return lista


def criar_projeto(db, cfg, rng):
    if db.query(models.Projeto).filter(models.Projeto.titulo == cfg["titulo"]).first():
        print(f"já existe: {cfg['titulo']}")
        return 0
    projeto = models.Projeto(
        titulo=cfg["titulo"], ano=cfg["ano"], grupo_insetos=cfg["grupo"], tracos_medidos=cfg["tracos"], local_coleta=cfg["local"],
        dataset_externo_url=f"https://zenodo.org/records/{cfg['zenodo']}" if cfg["zenodo"] else None,
        finalizado=cfg["finalizado"], publicacao_vinculada=cfg["publicacao"], descricao=cfg["descricao"],
    )
    db.add(projeto)
    db.flush()

    # campanhas: uma data e um local por campanha
    campanhas = []
    for _ in range(rng.randint(4, 6)):
        local = LOCAIS[rng.choice(cfg["locais"])]
        mes_max = 12 if cfg["ano"] < 2026 else 9
        campanhas.append((local, date(cfg["ano"] - rng.choice([0, 0, 1]) if cfg["ano"] < 2026 else 2026, rng.randint(1, mes_max), rng.randint(1, 28))))

    especies = cfg["especies"]
    sorteio = [e for e in especies for _ in range(3)]
    sorteio += rng.choices(especies, weights=[rng.uniform(0.3, 3) for _ in especies], k=max(cfg["n"] - len(sorteio), 0))
    rng.shuffle(sorteio)

    for i, e in enumerate(sorteio, start=1):
        codigo = f"{cfg['prefixo']}-{i:04d}"
        (nome_local, lat, lng, alt), data = rng.choice(campanhas)
        com_coord = rng.random() > 0.05
        sexo = rng.choice(["macho", "fêmea"]) if cfg["grupo"] in ("Coleoptera", "Lepidoptera") else "fêmea"
        if cfg["grupo"] == "Coleoptera" and rng.random() < 0.15:
            sexo = "indeterminado"
        if "casta" in e["medidas"]:
            estagio = rng.choice(e["medidas"]["casta"])
        else:
            estagio = "adulto"
        extra = random.Random(codigo)
        emprestado = extra.random() < 0.04
        esp_obj = models.Especime(
            determinador=extra.choice(DETERMINADORES), data_determinacao=data,
            metodo_coleta=extra.choice(METODOS), habitat=extra.choice(HABITATS),
            coletor=extra.choice(COLETORES), numero_campo=f"C{extra.randint(100, 999)}",
            localizacao_fisica=f"Armário {extra.randint(1, 4)}, caixa {extra.randint(1, 30)}",
            emprestimo_situacao="emprestado" if emprestado else "no acervo",
            emprestimo_para="Museu de Zoologia (fictício)" if emprestado else None,
            codigo_etiqueta=codigo, grupo_insetos=e["ordem"], familia=e["familia"], especie=e["especie"],
            data_coleta=data, local_coleta=nome_local,
            latitude=round(lat + rng.gauss(0, 0.035), 5) if com_coord else None,
            longitude=round(lng + rng.gauss(0, 0.035), 5) if com_coord else None,
            altitude_m=round(alt + rng.gauss(0, 70)) if com_coord else None,
            sexo=sexo, estagio=estagio,
            imagem_arquivo=f"{codigo}.svg" if rng.random() > 0.08 else None,
            projeto_id=projeto.id,
        )
        esp_obj.medidas = medidas_para(rng, e, cfg["tracos"], sexo)
        db.add(esp_obj)
    return len(sorteio)


def completar_familias(db):
    conhecidas = {}
    for tabela in (COLEOPTERA, LEPIDOPTERA, FORMIGAS, ABELHAS):
        for nome, e in tabela.items():
            conhecidas[nome] = e["familia"]
    for esp_obj in db.query(models.Especime).filter(models.Especime.familia.is_(None)).all():
        if esp_obj.especie in conhecidas:
            esp_obj.familia = conhecidas[esp_obj.especie]


def limpar(db):
    titulos = {p["titulo"] for p in PROJETOS}
    n = 0
    for p in db.query(models.Projeto).filter(models.Projeto.titulo.in_(titulos)).all():
        db.delete(p)
        n += 1
    db.commit()
    print(f"{n} projetos de exemplo removidos (com seus espécimes)")


def main_seed():
    inicializar_banco()
    db = SessionLocal()
    if "--limpar" in sys.argv:
        limpar(db)
        db.close()
        return
    rng = random.Random(2026)
    total = 0
    for cfg in PROJETOS:
        total += criar_projeto(db, cfg, rng)
    completar_familias(db)
    db.commit()
    db.close()
    print(f"{total} espécimes fictícios criados")


if __name__ == "__main__":
    main_seed()