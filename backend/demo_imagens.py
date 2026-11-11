import hashlib
import html
import math
import random

# ilustrações geradas por código, só para os dados fictícios; não representam fotos reais

LARGURA, ALTURA = 400, 300


def _hash(texto):
    return int(hashlib.md5(texto.encode("utf-8")).hexdigest()[:8], 16)


def _hsl(h, s, l):
    return f"hsl({h % 360:.0f} {s:.0f}% {l:.0f}%)"


def _espelho(corpo):
    return f'<g>{corpo}</g><g transform="scale(-1 1)">{corpo}</g>'


# ---------------------------------------------------------------- besouros
def _besouro(rng, familia, especie, base_h):
    fam = familia.lower()
    chifre = any(g in especie for g in ("Dynastes", "Megasoma", "Strategus"))
    comp, razao = 190, 0.62
    cor_h, cor_s, cor_l = base_h, 55, 32
    pintas = 0
    antena_clava = False
    antena_longa = 1.0
    if fam == "coccinellidae":
        comp, razao = 110, 0.86
        cor_h, cor_s, cor_l = rng.choice([4, 12, 28, 48]), 85, 48
        pintas = rng.choice([2, 4, 6, 7])
    elif fam == "scarabaeidae":
        comp, razao = 175, 0.7
        cor_h, cor_s, cor_l = rng.choice([18, 24, 30, 160]), 45, 24
        antena_clava = True
    elif fam == "carabidae":
        comp, razao = 175, 0.5
        cor_h, cor_s, cor_l = rng.choice([210, 150, 270]), 55, 22
    elif fam == "chrysomelidae":
        comp, razao = 120, 0.78
        cor_h, cor_s, cor_l = rng.choice([100, 170, 200, 40]), 70, 40
    elif fam == "cerambycidae":
        comp, razao = 195, 0.38
        cor_h, cor_s, cor_l = rng.choice([25, 35, 50]), 45, 34
        antena_longa = 1.9
    elif fam == "curculionidae":
        comp, razao = 120, 0.62
        cor_h, cor_s, cor_l = 30, 30, 28
    L = comp * rng.uniform(0.92, 1.06)
    W = L * razao
    cor = _hsl(cor_h, cor_s, cor_l)
    cor_claro = _hsl(cor_h, cor_s, cor_l + 14)
    cor_escuro = _hsl(cor_h, cor_s, max(cor_l - 18, 8))
    perna = _hsl(cor_h, 30, 14)
    pronoto_cor = "#1d1b18" if fam == "coccinellidae" else cor_escuro

    partes = []
    for i, y in enumerate((-0.17, 0.02, 0.2)):
        yy = y * L
        saida = 0.72 + 0.12 * i
        partes.append(
            f'<path d="M {W*0.3:.1f} {yy:.1f} L {W*saida:.1f} {yy-L*0.05:.1f} L {W*(saida+0.2):.1f} {yy+L*(0.06+0.05*i):.1f}" '
            f'fill="none" stroke="{perna}" stroke-width="{4.2 if i < 2 else 4.8}" stroke-linecap="round" stroke-linejoin="round"/>'
        )
    pernas = _espelho("".join(partes))

    ax = W * 0.55 * antena_longa
    antena = (
        f'<path d="M {W*0.08:.1f} {-L*0.5:.1f} Q {W*0.25:.1f} {-L*0.58:.1f} {ax:.1f} {-L*0.55-W*0.1:.1f}" '
        f'fill="none" stroke="{perna}" stroke-width="2.4" stroke-linecap="round"/>'
    )
    if antena_clava:
        antena += f'<ellipse cx="{ax:.1f}" cy="{-L*0.55-W*0.1:.1f}" rx="6" ry="9" fill="{perna}" transform="rotate(30 {ax:.1f} {-L*0.55-W*0.1:.1f})"/>'
    antenas = _espelho(antena)

    cabeca = f'<ellipse cx="0" cy="{-L*0.455:.1f}" rx="{W*0.21:.1f}" ry="{L*0.075:.1f}" fill="{cor_escuro}"/>'
    if fam == "curculionidae":
        cabeca += f'<path d="M 0 {-L*0.5:.1f} L 0 {-L*0.64:.1f}" stroke="{perna}" stroke-width="7" stroke-linecap="round"/>'
    pronoto = (
        f'<path d="M {-W*0.26:.1f} {-L*0.4:.1f} Q {-W*0.46:.1f} {-L*0.34:.1f} {-W*0.44:.1f} {-L*0.21:.1f} '
        f'L {W*0.44:.1f} {-L*0.21:.1f} Q {W*0.46:.1f} {-L*0.34:.1f} {W*0.26:.1f} {-L*0.4:.1f} Z" fill="{pronoto_cor}"/>'
    )
    if fam == "coccinellidae":
        pronoto += (
            f'<ellipse cx="{-W*0.2:.1f}" cy="{-L*0.32:.1f}" rx="{W*0.07:.1f}" ry="{L*0.045:.1f}" fill="#f4efdf"/>'
            f'<ellipse cx="{W*0.2:.1f}" cy="{-L*0.32:.1f}" rx="{W*0.07:.1f}" ry="{L*0.045:.1f}" fill="#f4efdf"/>'
        )
    corno = ""
    if chifre:
        corno = (
            f'<path d="M {-W*0.07:.1f} {-L*0.36:.1f} Q {-W*0.05:.1f} {-L*0.7:.1f} {W*0.12:.1f} {-L*0.8:.1f} '
            f'Q {W*0.02:.1f} {-L*0.66:.1f} {W*0.07:.1f} {-L*0.36:.1f} Z" fill="{cor_escuro}"/>'
            f'<path d="M {-W*0.05:.1f} {-L*0.47:.1f} Q {-W*0.12:.1f} {-L*0.58:.1f} {-W*0.02:.1f} {-L*0.62:.1f}" '
            f'fill="none" stroke="{cor_escuro}" stroke-width="5" stroke-linecap="round"/>'
        )
    elitros = (
        f'<path d="M {-W*0.47:.1f} {-L*0.22:.1f} C {-W*0.62:.1f} {L*0.08:.1f} {-W*0.42:.1f} {L*0.46:.1f} 0 {L*0.5:.1f} '
        f'C {W*0.42:.1f} {L*0.46:.1f} {W*0.62:.1f} {L*0.08:.1f} {W*0.47:.1f} {-L*0.22:.1f} Z" fill="{cor}"/>'
        f'<path d="M 0 {-L*0.215:.1f} L 0 {L*0.5:.1f}" stroke="{cor_escuro}" stroke-width="2.2"/>'
        f'<ellipse cx="{-W*0.2:.1f}" cy="{-L*0.02:.1f}" rx="{W*0.1:.1f}" ry="{L*0.2:.1f}" fill="{cor_claro}" opacity="0.5"/>'
    )
    if fam == "coccinellidae":
        pts = []
        for _ in range(pintas // 2):
            pts.append((rng.uniform(0.1, 0.36), rng.uniform(-0.12, 0.38)))
        if pintas % 2 == 1:
            elitros += f'<circle cx="0" cy="{-L*0.08:.1f}" r="{W*0.06:.1f}" fill="#1d1b18"/>'
        for x, y in pts:
            r = W * rng.uniform(0.055, 0.085)
            elitros += f'<circle cx="{-W*x:.1f}" cy="{L*y:.1f}" r="{r:.1f}" fill="#1d1b18"/><circle cx="{W*x:.1f}" cy="{L*y:.1f}" r="{r:.1f}" fill="#1d1b18"/>'
    if fam == "cerambycidae":
        for k in range(5):
            y = -0.1 + k * 0.12
            elitros += f'<path d="M {-W*0.4:.1f} {L*y:.1f} Q 0 {L*(y+0.03):.1f} {W*0.4:.1f} {L*y:.1f}" stroke="{cor_claro}" stroke-width="3" fill="none" opacity="0.6"/>'
    return pernas + antenas + corno + cabeca + pronoto + elitros


# ------------------------------------------------------------ borboletas
def _borboleta(rng, familia, especie, base_h):
    fam = familia.lower()
    esp = especie.lower()
    cauda = fam == "papilionidae"
    base = _hsl(base_h, 75, 52)
    acento = _hsl(base_h + 40, 80, 60)
    borda = "#231c16"
    padrao = "pontos"
    if "danaus" in esp:
        base, acento, padrao = "#d9731f", "#f5e9d2", "pontos"
    elif "heliconius" in esp:
        base, acento, padrao = "#1f1b1a", rng.choice(["#d9362b", "#e8c43a"]), "faixa"
    elif fam == "papilionidae":
        base, acento = rng.choice([("#232220", "#d8c44a"), ("#1c2b3a", "#4fb0d8"), ("#2a2622", "#9fd0a0")])
        padrao = "pontos"
    elif fam == "pieridae":
        base, acento, padrao = rng.choice(["#f2efe2", "#f3d84a"]), "#2a2622", "pontos"
    elif fam == "lycaenidae" or fam == "riodinidae":
        base, acento, padrao = _hsl(205, 70, 52), "#f4efdf", "pontos"
    anterior = "M -5 -10 C -50 -78 -150 -88 -172 -34 C -170 8 -110 24 -5 12 Z"
    posterior = "M -5 8 C -86 14 -146 48 -122 98 C -92 126 -40 102 -5 44 Z"
    if cauda:
        posterior = "M -5 8 C -86 14 -146 44 -124 92 L -134 136 C -100 124 -86 112 -64 104 C -30 92 -12 70 -5 44 Z"
    clip = f'<clipPath id="ca"><path d="{anterior}"/></clipPath><clipPath id="cp"><path d="{posterior}"/></clipPath>'
    asas = (
        f'<path d="{anterior}" fill="{base}" stroke="{borda}" stroke-width="3"/>'
        f'<path d="{posterior}" fill="{base}" stroke="{borda}" stroke-width="3"/>'
    )
    detalhe = ""
    if padrao == "faixa":
        detalhe += (
            f'<g clip-path="url(#ca)"><path d="M -60 -70 L -100 20" stroke="{acento}" stroke-width="22" opacity="0.95"/>'
            f'<path d="M -128 -64 L -150 -8" stroke="#f4efdf" stroke-width="9"/></g>'
            f'<g clip-path="url(#cp)"><path d="M -40 40 L -100 70" stroke="{acento}" stroke-width="10" opacity="0.9"/></g>'
        )
    else:
        # nervuras e pontos marginais
        for ang in range(-60, 40, 18):
            r = math.radians(ang)
            detalhe += f'<path d="M -5 0 L {-170*math.cos(r):.1f} {-70*math.sin(r) - 20:.1f}" stroke="{borda}" stroke-width="1.6" opacity="0.5" fill="none"/>'
        for k in range(9):
            t = k / 8
            x = -165 + 110 * t
            y = -26 - 58 * math.sin(t * math.pi) * 0.9
            detalhe += f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{3 + 2*math.sin(t*math.pi):.1f}" fill="{acento}" opacity="0.95"/>'
        for k in range(6):
            t = k / 5
            detalhe += f'<circle cx="{-132 + 60*t:.1f}" cy="{86 + 28*math.sin(t*math.pi):.1f}" r="3.4" fill="{acento}" opacity="0.95"/>'
        detalhe += f'<g clip-path="url(#ca)"><path d="M -5 -10 C -60 -30 -110 -30 -172 -34" stroke="{borda}" stroke-width="12" opacity="0.35" fill="none"/></g>'
    asa = asas + detalhe
    corpo = (
        f'<ellipse cx="0" cy="40" rx="5.5" ry="30" fill="#1d1a16"/><ellipse cx="0" cy="-2" rx="7" ry="22" fill="#2a2520"/>'
        f'<circle cx="0" cy="-30" r="7" fill="#1d1a16"/>'
        + _espelho('<path d="M -3 -36 Q -16 -64 -34 -74" stroke="#1d1a16" stroke-width="2.2" fill="none"/><circle cx="-34" cy="-74" r="3.2" fill="#1d1a16"/>')
    )
    return f"<defs>{clip}</defs>" + _espelho(asa) + corpo


# ----------------------------------------------------------- himenópteros
def _perna_formiga(cor):
    saida = ""
    for y, dx, dy in ((-40, 52, -22), (-28, 60, 4), (-16, 50, 34)):
        saida += (
            f'<path d="M 9 {y} L {dx*0.55:.0f} {y+dy*0.2:.0f} L {dx} {y+dy}" fill="none" stroke="{cor}" '
            f'stroke-width="4.4" stroke-linecap="round" stroke-linejoin="round"/>'
        )
    return _espelho(saida)


def _formiga(rng, familia, especie, base_h):
    cor_h = rng.choice([22, 18, 8, 28, 0])
    escuro = "camponotus" in especie.lower() or rng.random() < 0.3
    cor = _hsl(cor_h, 55, 18) if escuro else _hsl(cor_h, 60, 34)
    claro = _hsl(cor_h, 55, 44 if not escuro else 28)
    perna = _hsl(cor_h, 40, 14)
    antena = _espelho(
        f'<path d="M -7 -86 L -18 -118 L -48 -126" fill="none" stroke="{perna}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>'
        f'<circle cx="-48" cy="-126" r="3.4" fill="{perna}"/>'
    )
    mand = _espelho(f'<path d="M -6 -86 L -14 -96 L -5 -92 Z" fill="{perna}"/>')
    corpo = (
        _perna_formiga(perna)
        + f'<ellipse cx="0" cy="-66" rx="18" ry="21" fill="{cor}"/>'
        + _espelho(f'<ellipse cx="-12" cy="-70" rx="4" ry="6" fill="#0d0c0a"/>')
        + f'<path d="M -9 -45 C -16 -38 -14 -20 -8 -10 L 8 -10 C 14 -20 16 -38 9 -45 Z" fill="{claro}"/>'
        + f'<ellipse cx="0" cy="-26" rx="10" ry="22" fill="{claro}"/>'
        + f'<ellipse cx="0" cy="1" rx="5" ry="7" fill="{cor}"/>'
        + f'<ellipse cx="0" cy="40" rx="25" ry="34" fill="{cor}"/>'
        + f'<ellipse cx="-8" cy="28" rx="6" ry="14" fill="#ffffff" opacity="0.14"/>'
    )
    return antena + mand + corpo


def _abelha(rng, familia, especie, base_h):
    vespa = familia.lower() == "vespidae"
    amarelo = "#e2b32a" if not vespa else "#f0c62e"
    escuro = "#2b2218"
    pelo = "#8a6a2c" if not vespa else "#2b2218"
    asas = _espelho(
        '<ellipse cx="-44" cy="-52" rx="22" ry="52" transform="rotate(-38 -44 -52)" fill="#cfe4ee" opacity="0.55" stroke="#8fb0c2" stroke-width="1.4"/>'
        '<ellipse cx="-30" cy="-26" rx="14" ry="36" transform="rotate(-62 -30 -26)" fill="#cfe4ee" opacity="0.5" stroke="#8fb0c2" stroke-width="1.2"/>'
    )
    pernas = _espelho(
        f'<path d="M -10 -34 L -38 -22 L -48 0" stroke="{escuro}" stroke-width="4.5" fill="none" stroke-linecap="round" stroke-linejoin="round"/>'
        f'<path d="M -10 -28 L -42 -6 L -44 26" stroke="{escuro}" stroke-width="4.5" fill="none" stroke-linecap="round" stroke-linejoin="round"/>'
        f'<path d="M -10 -22 L -34 10 L -32 46" stroke="{escuro}" stroke-width="4.5" fill="none" stroke-linecap="round" stroke-linejoin="round"/>'
    )
    larg = 22 if not vespa else 17
    comp = 42 if not vespa else 50
    cy = 28 if not vespa else 40
    listras = ""
    for k in range(4):
        y = cy - comp * 0.65 + k * comp * 0.42
        listras += f'<rect x="-40" y="{y:.1f}" width="80" height="{comp*0.2:.1f}" fill="{escuro if k % 2 == 0 else amarelo}"/>'
    clip = f'<clipPath id="ab"><ellipse cx="0" cy="{cy}" rx="{larg}" ry="{comp}"/></clipPath>'
    abdomen = f'<defs>{clip}</defs><ellipse cx="0" cy="{cy}" rx="{larg}" ry="{comp}" fill="{amarelo}"/><g clip-path="url(#ab)">{listras}</g>'
    cintura = f'<ellipse cx="0" cy="-6" rx="4" ry="6" fill="{escuro}"/>' if vespa else ""
    toraxr = 21 if not vespa else 15
    torax = f'<ellipse cx="0" cy="-32" rx="{toraxr}" ry="{toraxr}" fill="{pelo}"/><ellipse cx="0" cy="-32" rx="{toraxr-7}" ry="{toraxr-7}" fill="#ffffff" opacity="0.08"/>'
    cabeca = (
        f'<ellipse cx="0" cy="-66" rx="16" ry="14" fill="{escuro}"/>'
        + _espelho('<ellipse cx="-11" cy="-68" rx="5" ry="8" fill="#0d0c0a"/>')
    )
    antenas = _espelho(f'<path d="M -5 -78 L -14 -104 L -34 -112" fill="none" stroke="{escuro}" stroke-width="2.8" stroke-linecap="round" stroke-linejoin="round"/>')
    return asas + pernas + abdomen + cintura + torax + cabeca + antenas


# --------------------------------------------------------------- principal
def gerar_svg(ordem, familia, especie, id_especime, codigo, sexo=""):
    rng = random.Random(_hash(f"{id_especime}-{codigo}"))
    base_h = _hash(especie) % 360
    ordem_l = ordem.lower()
    if ordem_l == "lepidoptera":
        corpo, escala, desloca = _borboleta(rng, familia, especie, base_h), 0.95, (200, 138)
    elif ordem_l == "hymenoptera":
        if familia.lower() in ("apidae", "vespidae"):
            corpo, escala, desloca = _abelha(rng, familia, especie, base_h), 1.08, (200, 168)
        else:
            corpo, escala, desloca = _formiga(rng, familia, especie, base_h), 1.08, (200, 165)
    else:
        corpo, escala, desloca = _besouro(rng, familia, especie, base_h), 1.2 if familia.lower() == "coccinellidae" else 0.95, (200, 150)

    ang = rng.uniform(-14, 14) if ordem_l != "lepidoptera" else rng.uniform(-6, 6)
    esc = escala * rng.uniform(0.94, 1.04)
    fundo = rng.choice(["#ece6d2", "#e8e4d6", "#efe9d8", "#e4e6dc"])
    codigo_seguro = html.escape(codigo)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {LARGURA} {ALTURA}" width="{LARGURA}" height="{ALTURA}">'
        f'<defs><radialGradient id="g" cx="50%" cy="45%" r="75%"><stop offset="0" stop-color="#fbf9f0"/><stop offset="1" stop-color="{fundo}"/></radialGradient>'
        f'<filter id="s" x="-20%" y="-20%" width="140%" height="140%"><feDropShadow dx="3" dy="6" stdDeviation="5" flood-color="#3b3320" flood-opacity="0.28"/></filter></defs>'
        f'<rect width="{LARGURA}" height="{ALTURA}" fill="url(#g)"/>'
        f'<g transform="translate({desloca[0]} {desloca[1]}) rotate({ang:.1f}) scale({esc:.3f})" filter="url(#s)">{corpo}</g>'
        f'<g font-family="monospace" font-size="12" fill="#5b5640">'
        f'<rect x="14" y="268" width="{12 + 7.4*len(codigo):.0f}" height="20" rx="3" fill="#fbf9f0" stroke="#b9b290"/>'
        f'<text x="20" y="282">{codigo_seguro}</text>'
        f'<path d="M 316 276 H 380 M 316 270 V 282 M 380 270 V 282" stroke="#5b5640" stroke-width="2" fill="none"/>'
        f'<text x="332" y="266">5 mm</text></g></svg>'
    )