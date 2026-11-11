import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

import models

URL_MATCH = "https://api.gbif.org/v1/species/match"
URL_TAXON = "https://api.gbif.org/v1/species/"
VALIDADE_CACHE = timedelta(days=30)
TEMPO_LIMITE = 6
# tempo total máximo por lote; o que sobrar fica como não conferido
ORCAMENTO_SEGUNDOS = 25

# situações possíveis: ok, aproximado, sinonimo, so_genero, nao_encontrado, indisponivel
SITUACOES_CACHEAVEIS = {"ok", "aproximado", "sinonimo", "so_genero", "nao_encontrado"}


def _get(url: str, params: dict | None = None) -> dict:
    if params:
        url = url + "?" + urllib.parse.urlencode(params)
    pedido = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "EntomoBase/0.4"})
    with urllib.request.urlopen(pedido, timeout=TEMPO_LIMITE) as resposta:
        return json.loads(resposta.read().decode("utf-8"))


def _canonico(texto: str) -> str:
    # compara só gênero e epíteto, ignorando autor, ano e maiúsculas
    partes = re.sub(r"[()]", " ", texto or "").split()
    return " ".join(partes[:2]).lower() if len(partes) >= 2 else " ".join(partes).lower()


# faz a consulta de verdade ao GBIF; separada para poder ser trocada nos testes
def buscar(nome: str) -> dict:
    dados = _get(URL_MATCH, {"name": nome, "kingdom": "Animalia", "class": "Insecta"})
    tipo = dados.get("matchType", "NONE")
    canonico = dados.get("canonicalName") or dados.get("scientificName")
    resultado = {
        "chave_gbif": dados.get("usageKey"),
        "familia": dados.get("family"),
        "ordem": dados.get("order"),
        "sugestao": None,
    }
    if tipo == "NONE" or not canonico:
        resultado["situacao"] = "nao_encontrado"
        return resultado
    if tipo == "HIGHERRANK":
        resultado["situacao"] = "so_genero"
        resultado["sugestao"] = canonico
        return resultado
    if dados.get("status") == "SYNONYM" or dados.get("synonym"):
        aceito = canonico
        chave = dados.get("acceptedUsageKey")
        if chave:
            try:
                detalhe = _get(URL_TAXON + str(chave))
                aceito = detalhe.get("canonicalName") or detalhe.get("scientificName") or canonico
                resultado["familia"] = detalhe.get("family") or resultado["familia"]
                resultado["ordem"] = detalhe.get("order") or resultado["ordem"]
            except (urllib.error.URLError, TimeoutError, ValueError):
                pass
        resultado["situacao"] = "sinonimo"
        resultado["sugestao"] = aceito
        return resultado
    if tipo in ("FUZZY", "VARIANT") or _canonico(canonico) != _canonico(nome):
        resultado["situacao"] = "aproximado"
        resultado["sugestao"] = canonico
        return resultado
    resultado["situacao"] = "ok"
    return resultado


def validar_nomes(nomes: list[str], db: Session) -> dict[str, dict]:
    saida = {}
    unicos = []
    for n in nomes:
        n = (n or "").strip()
        if n and n not in saida and n not in unicos:
            unicos.append(n)

    agora = datetime.utcnow()
    em_cache = {
        t.nome_informado: t
        for t in db.query(models.Taxon).filter(models.Taxon.nome_informado.in_(unicos)).all()
    } if unicos else {}

    gbif_fora = False
    inicio = time.monotonic()
    for nome in unicos:
        t = em_cache.get(nome)
        if t is not None and agora - t.consultado_em < VALIDADE_CACHE:
            saida[nome] = {"situacao": t.situacao, "sugestao": t.sugestao, "familia": t.familia, "ordem": t.ordem}
            continue
        if gbif_fora or time.monotonic() - inicio > ORCAMENTO_SEGUNDOS:
            saida[nome] = {"situacao": "indisponivel", "sugestao": None, "familia": None, "ordem": None}
            continue
        try:
            r = buscar(nome)
        except urllib.error.HTTPError as erro:
            # erro 4xx é problema deste nome; só falha de servidor interrompe o lote
            gbif_fora = erro.code >= 500
            saida[nome] = {"situacao": "indisponivel", "sugestao": None, "familia": None, "ordem": None}
            continue
        except (urllib.error.URLError, TimeoutError, ValueError, OSError):
            # se o GBIF não responde, o resto da lista nem é tentado
            gbif_fora = True
            saida[nome] = {"situacao": "indisponivel", "sugestao": None, "familia": None, "ordem": None}
            continue
        if t is None:
            t = models.Taxon(nome_informado=nome)
            db.add(t)
        t.situacao = r["situacao"]
        t.sugestao = r["sugestao"]
        t.chave_gbif = r["chave_gbif"]
        t.familia = r["familia"]
        t.ordem = r["ordem"]
        t.consultado_em = agora
        saida[nome] = {k: r[k] for k in ("situacao", "sugestao", "familia", "ordem")}
    db.commit()
    return saida