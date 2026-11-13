# -*- coding: utf-8 -*-
"""
SISTEMA INTEGRAL DE GESTIÓN HOSPITALARIA VETERINARIA
Hospital de Equinos · FES Cuautitlán | UNAM

Frontend en Python (Streamlit). Esta versión NO incluye base de datos:
toda la información vive en memoria (st.session_state) a través de la clase
`Repo`. Para conectar la base de datos basta con reimplementar los métodos de
`Repo` (listar, buscar, crear, modificar) con SQLAlchemy / psycopg / etc.

Ejecutar:
    pip install streamlit pandas openpyxl reportlab
    streamlit run app.py

Acceso: la primera cuenta que se registra queda como Administrador. Las cuentas
se guardan en usuarios.json (contraseñas cifradas con PBKDF2-SHA256).

Escudo: copie el archivo oficial en  assets/escudo_unam.png  (o .svg) junto a
este app.py y se usará en todo el sistema. Si no existe, se muestra un emblema
ilustrativo. Recomendado: Streamlit 1.39 o superior.

Nota: es un prototipo de interfaz. No está aprobado, certificado ni
implementado oficialmente por la UNAM.
"""
from __future__ import annotations

import base64
import copy
import hashlib
import html
import inspect
import io
import hmac
import json
import os
import re
import secrets
import time as _time
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="Hospital de Equinos · FES Cuautitlán | UNAM",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ───────────────────────────── Compatibilidad de versiones ─────────────────────
if "width" in inspect.signature(st.button).parameters:
    STRETCH = {"width": "stretch"}
else:  # versiones anteriores de Streamlit
    STRETCH = {"use_container_width": True}


def tabla(df: pd.DataFrame, **kw):
    st.dataframe(df, hide_index=True, **STRETCH, **kw)


def h(x) -> str:
    return html.escape(str(x))


# ───────────────────────────── Identidad visual ────────────────────────────────
AZUL, AZUL2, DORADO, TEAL, GRIS = "#0A1F44", "#14407F", "#C9A24B", "#2F7F70", "#F2F4F8"

HOSPITAL_SEDE = "FES Cuautitlán | UNAM"
BASE_DIR = Path(__file__).resolve().parent

DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def fecha_larga(d=None) -> str:
    d = d or datetime.now()
    return f"{DIAS[d.weekday()]} {d.day} de {MESES[d.month - 1]} de {d.year}"


def html_min(s: str) -> str:
    """Aplana HTML en una sola línea (Markdown corta los bloques HTML con líneas vacías)."""
    return " ".join(ln.strip() for ln in s.splitlines() if ln.strip())


def contenedor(key: str):
    """st.container con clave (Streamlit >= 1.39) y alternativa para versiones anteriores."""
    try:
        return st.container(key=key)
    except TypeError:
        return st.container()


# ── Gráficos vectoriales propios ──────────────────────────────────────────────
# Emblema ILUSTRATIVO (escudo, volcanes, sol). No es el escudo oficial de la UNAM.
# Para usar el escudo oficial, copie el archivo en  assets/escudo_unam.png  (o .svg)
# junto a este app.py y se mostrará automáticamente en todo el sistema.
ESCUDO_SVG = (
    '<svg viewBox="0 0 100 120" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Escudo ilustrativo">'
    '<path d="M8 8 H92 V66 C92 98 70 112 50 118 C30 112 8 98 8 66 Z" fill="#D9B25A"/>'
    '<path d="M14 14 H86 V66 C86 93 67 106 50 111 C33 106 14 93 14 66 Z" fill="#0A1F44"/>'
    '<circle cx="50" cy="38" r="11" fill="#E9C46A"/>'
    '<path d="M16 78 L36 48 L56 78 Z" fill="#2C5AA0"/><path d="M31 56 L36 48 L41 56 L38.5 54.5 L36 57 L33.5 54.5 Z" fill="#fff"/>'
    '<path d="M42 78 L66 50 L84 78 Z" fill="#1E4A8C"/><path d="M61 56 L66 50 L71 56 L68.5 54.5 L66 57 L63.5 54.5 Z" fill="#fff"/>'
    '<text x="50" y="98" text-anchor="middle" font-family="Georgia,serif" font-weight="700" font-size="13" fill="#E9C46A" letter-spacing="1.6">UNAM</text>'
    '</svg>'
)

HORSE_SVG = (
    '<svg viewBox="0 0 300 340" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">'
    '<g fill="#0A1F44">'
    '<path d="M44 340 C 58 246, 80 140, 104 66 C 118 58, 128 62, 138 74 C 170 112, 206 170, 238 222 C 252 238, 256 256, 246 270 '
    'C 238 282, 218 282, 204 274 C 184 264, 164 266, 146 252 C 130 240, 114 242, 112 262 C 108 292, 104 312, 104 340 Z"/>'
    '<path d="M110 70 C 104 44, 110 24, 124 4 C 136 24, 142 48, 138 76 Z"/></g>'
    '<g fill="none" stroke="#0A1F44" stroke-width="5" stroke-linecap="round">'
    '<path class="mane m1" d="M104 66 C 68 96, 50 156, 42 236"/>'
    '<path class="mane m2" d="M110 92 C 78 124, 64 176, 60 254"/>'
    '<path class="mane m3" d="M112 52 C 82 62, 64 92, 54 124"/></g>'
    '<circle cx="160" cy="128" r="6.5" fill="#E9B95F"/>'
    '<path d="M232 246 C 238 246, 243 250, 243 256" stroke="#E9B95F" stroke-width="3" fill="none" stroke-linecap="round"/>'
    '<path d="M210 270 C 222 274, 236 272, 242 266" stroke="#E9B95F" stroke-width="2" fill="none" stroke-linecap="round"/>'
    '</svg>'
)

HERRADURA_SVG = (
    '<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">'
    '<path d="M26 10 C 10 40, 12 86, 50 90 C 88 86, 90 40, 74 10" fill="none" stroke="#fff" stroke-width="13" stroke-linecap="round"/>'
    '<g fill="#0A1F44"><circle cx="20" cy="40" r="2.2"/><circle cx="23" cy="62" r="2.2"/><circle cx="36" cy="80" r="2.2"/>'
    '<circle cx="80" cy="40" r="2.2"/><circle cx="77" cy="62" r="2.2"/><circle cx="64" cy="80" r="2.2"/></g></svg>'
)


def _leer_escudo_archivo():
    """Busca el escudo oficial en assets/ o junto a app.py. Devuelve (mime, base64) o None."""
    mimes = {".png": "image/png", ".svg": "image/svg+xml", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}
    for carpeta in (BASE_DIR / "assets", BASE_DIR):
        for ext, mime in mimes.items():
            f = carpeta / f"escudo_unam{ext}"
            if f.is_file():
                try:
                    return mime, base64.b64encode(f.read_bytes()).decode()
                except OSError:
                    pass
    return None


def escudo_html() -> str:
    """Prioridad: recurso cargado en Administración > archivo en assets/ > emblema ilustrativo."""
    logo = st.session_state.get("logo")
    if logo:
        return f'<img src="data:{logo["mime"]};base64,{base64.b64encode(logo["bytes"]).decode()}" alt="Escudo"/>'
    arch = _leer_escudo_archivo()
    if arch:
        return f'<img src="data:{arch[0]};base64,{arch[1]}" alt="Escudo UNAM"/>'
    return ESCUDO_SVG


FUENTES = "@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,700&family=DM+Sans:wght@400;500;600;700&display=swap');"

CSS = """
<style>
""" + FUENTES + """
html, body, [class*="css"] { font-family:'DM Sans',sans-serif; }
h1, h2, h3, h4 { font-family:'Fraunces',serif; }
.stApp { background: radial-gradient(900px 420px at 100% -8%, #DCE6F5 0%, transparent 62%), radial-gradient(760px 420px at -8% 108%, #E3EEE8 0%, transparent 60%), #F2F4F8; }
[data-testid="stHeader"] { background: transparent; }
.block-container { padding-top: 1.1rem; max-width: 1450px; }

/* Barra lateral */
[data-testid="stSidebar"] { background: linear-gradient(190deg,#071634 0%,#0A1F44 50%,#123F52 100%); border-right: 3px solid #C9A24B; }
[data-testid="stSidebar"] * { color: #E9EFF9 !important; }
[data-testid="stSidebar"] input, [data-testid="stSidebar"] [data-baseweb="select"] * { color: #0A1F44 !important; }
[data-testid="stSidebar"] .stButton > button { justify-content:flex-start; text-align:left; border:none; background:transparent;
    padding:.5rem .8rem; border-radius:10px; font-weight:500; transition: background .15s, transform .15s; }
[data-testid="stSidebar"] .stButton > button:hover { background: rgba(255,255,255,.10); transform: translateX(3px); }
[data-testid="stSidebar"] .stButton > button[kind="primary"], [data-testid="stSidebar"] [data-testid="stBaseButton-primary"] {
    background: linear-gradient(90deg, rgba(201,162,75,.38), rgba(201,162,75,.06)); border-left:4px solid #C9A24B; border-radius:4px 10px 10px 4px; font-weight:700; }
.sb-brand { display:flex; gap:.7rem; align-items:center; padding:.2rem 0 .9rem; border-bottom:1px solid rgba(255,255,255,.14); margin-bottom:.8rem; }
.sb-crest { width:46px; height:54px; flex:none; }
.sb-crest img, .sb-crest svg, .crest img, .crest svg { width:100%; height:100%; object-fit:contain; display:block; }
.sb-t { font-family:'Fraunces',serif; font-size:1.18rem; font-weight:700; line-height:1.1; }
.sb-s { font-size:.72rem; color:#E9C46A !important; }
.ucard { display:flex; gap:.7rem; align-items:center; background:rgba(255,255,255,.07); border:1px solid rgba(255,255,255,.12); border-radius:14px; padding:.6rem .7rem; margin-bottom:.8rem; }
.ucard .av { width:38px; height:38px; border-radius:50%; background:linear-gradient(135deg,#E9C46A,#B8893A); color:#0A1F44 !important; font-weight:700; display:flex; align-items:center; justify-content:center; flex:none; }
.ucard b { font-size:.9rem; } .ucard span { font-size:.72rem; opacity:.85; }

/* Encabezado institucional */
.hero { background: linear-gradient(120deg,#071634 0%,#0A1F44 48%,#14507A 100%); border-radius:20px; padding:1.1rem 1.6rem;
    display:flex; align-items:center; justify-content:space-between; gap:1rem; border-bottom:4px solid #C9A24B;
    box-shadow:0 12px 32px rgba(10,31,68,.24); position:relative; overflow:hidden; }
.hero .shoe { position:absolute; right:-14px; top:-34px; width:200px; opacity:.08; transform:rotate(18deg); }
.hero-left { display:flex; align-items:center; gap:1.1rem; position:relative; z-index:1; }
.hero .crest { width:56px; height:66px; flex:none; filter:drop-shadow(0 4px 8px rgba(0,0,0,.35)); }
.hero-top { color:#E9C46A; letter-spacing:.12em; font-size:.66rem; font-weight:600; }
.hero-title { font-family:'Fraunces',serif; color:#fff; font-size:2rem; font-weight:700; line-height:1.05; margin:.1rem 0; }
.hero-sub { color:#BFD3EE; font-size:.86rem; font-weight:500; }
.hero-right { text-align:right; color:#CFE0F5; font-size:.78rem; position:relative; z-index:1; max-width:340px; }
.hero-right b { color:#fff; font-family:'Fraunces',serif; font-size:1.02rem; font-weight:500; }

.pt { margin: 1.1rem 0 .6rem; }
.pt h2 { font-family:'Fraunces',serif; color:#0A1F44; margin:0; font-size:1.75rem; }
.pt p { color:#5E6A82; margin:.15rem 0 0; font-size:.94rem; }
.pt .bar { width:54px; height:4px; background:#C9A24B; border-radius:4px; margin-top:.45rem; }

/* Tarjetas */
.kpi { background:#fff; border-radius:16px; padding:1rem 1.1rem; border:1px solid #E1E6EF; box-shadow:0 3px 12px rgba(10,31,68,.06); border-top:4px solid #2F7F70; }
.kpi.gold { border-top-color:#C9A24B; } .kpi.blue { border-top-color:#14407F; } .kpi.red { border-top-color:#B5473E; }
.kpi .n { font-family:'Fraunces',serif; font-size:2.1rem; font-weight:700; color:#0A1F44; line-height:1; }
.kpi .l { color:#5E6A82; font-size:.78rem; font-weight:600; margin-top:.4rem; }
@property --num { syntax:'<integer>'; initial-value:0; inherits:false; }
.kpi .n.cnt { counter-reset: num var(--num); animation: contar 1s ease-out forwards; }
.kpi .n.cnt::after { content: counter(num); }
@keyframes contar { from { --num:0; } to { --num:var(--t); } }
.card { background:#fff; border-radius:16px; padding:1rem 1.2rem; border:1px solid #E1E6EF; box-shadow:0 3px 12px rgba(10,31,68,.05); margin-bottom:.7rem; }
.card h4 { margin:0 0 .3rem; color:#0A1F44; font-family:'Fraunces',serif; }
.empty { text-align:center; color:#7C879D; padding:2rem 1rem; border:2px dashed #CBD3E2; border-radius:16px; background:#FAFBFD; }
.pill { display:inline-block; padding:.12rem .6rem; border-radius:999px; font-size:.72rem; font-weight:700; margin-right:.3rem; }
.p-ok { background:#DDF3EC; color:#13674F; } .p-pen { background:#FFF1D1; color:#8A6410; }
.p-dev { background:#FBE0DD; color:#9A2F26; } .p-na { background:#E8ECF3; color:#40506B; } .p-est { background:#DCE8FA; color:#14407F; }
.tl { border-left:4px solid #2F7F70; padding:.2rem .8rem; margin:.1rem 0 .3rem; color:#40506B; font-size:.82rem; }
.disc { color:#8A93A6; font-size:.72rem; text-align:center; margin-top:2rem; }

/* Mapa de caballerizas */
.boxes { display:grid; grid-template-columns:repeat(auto-fill,minmax(118px,1fr)); gap:.75rem; margin:.4rem 0 .3rem; }
.bx { position:relative; border-radius:16px 16px 6px 6px; padding:.7rem .65rem .6rem; min-height:96px; border:2px solid #D8CBA8;
    background:repeating-linear-gradient(0deg,#F6ECD0 0 6px,#F0E3BE 6px 7px); transition:transform .18s, box-shadow .18s; }
.bx:hover { transform:translateY(-4px) rotate(-.6deg); box-shadow:0 12px 22px rgba(10,31,68,.18); }
.bx .n { font-weight:700; font-size:.76rem; color:#7A6530; }
.bx .st { font-size:.7rem; margin-top:.2rem; color:#8A7A4A; }
.bx .who { font-family:'Fraunces',serif; font-size:1.05rem; font-weight:700; color:#fff; margin-top:.25rem; line-height:1.1; }
.bx .hs { position:absolute; right:8px; bottom:6px; font-size:1.25rem; opacity:.9; }
.bx.occ { background:linear-gradient(160deg,#14407F,#0A1F44); border-color:#C9A24B; }
.bx.occ .n, .bx.occ .st { color:#E9C46A; }
.bx.urg { background:linear-gradient(160deg,#B5473E,#7C241D); border-color:#F0B9B3; animation:pulso 1.8s ease-in-out infinite; }
.bx.urg .n, .bx.urg .st { color:#FFE3DF; }
@keyframes pulso { 50% { box-shadow:0 0 0 7px rgba(181,71,62,.18); } }
.leg { display:flex; gap:1.1rem; font-size:.76rem; color:#5E6A82; margin:.2rem 0 1rem; }
.leg i { display:inline-block; width:11px; height:11px; border-radius:3px; margin-right:.35rem; vertical-align:-1px; }
.leg .free { background:#EBDDB2; } .leg .occ { background:#14407F; } .leg .urg { background:#B5473E; }
.st-key-box_map [class*="st-key-box_pick_"] button {
    min-height:96px; height:auto; white-space:pre-line; text-align:left; justify-content:flex-start;
    align-items:flex-start; border:2px solid #D8CBA8; border-radius:16px 16px 6px 6px;
    background:repeating-linear-gradient(0deg,#F6ECD0 0 6px,#F0E3BE 6px 7px);
    color:#7A6530; font-weight:700; transition:transform .18s, box-shadow .18s;
}
.st-key-box_map [class*="st-key-box_pick_"] button:hover {
    transform:translateY(-3px); box-shadow:0 10px 20px rgba(10,31,68,.16);
}
.st-key-box_map [class*="st-key-box_pick_occupied_"] button {
    background:linear-gradient(160deg,#14407F,#0A1F44); border-color:#C9A24B; color:#E9C46A;
}
.st-key-box_map [class*="st-key-box_pick_urgent_"] button {
    background:linear-gradient(160deg,#B5473E,#7C241D); border-color:#F0B9B3; color:#FFE3DF;
}
.st-key-box_map [class*="st-key-box_pick_conflict_"] button {
    background:linear-gradient(160deg,#9A6410,#67420B); border-color:#E9C46A; color:#FFF1D1;
}

/* Herramientas clínicas */
.weight { background:linear-gradient(135deg,#0A1F44,#14407F); color:#fff; border-radius:20px; padding:1.4rem 1.6rem; border-bottom:4px solid #C9A24B; }
.weight .wn { font-family:'Fraunces',serif; font-size:3.4rem; font-weight:700; line-height:1; }
.weight .wl { color:#BFD3EE; font-size:.86rem; margin-top:.4rem; }
.gauge { background:#fff; border:1px solid #E1E6EF; border-radius:16px; padding:1rem 1.1rem; box-shadow:0 3px 12px rgba(10,31,68,.05); }
.gauge .gt { display:flex; justify-content:space-between; align-items:baseline; gap:.5rem; }
.gauge .gv { font-family:'Fraunces',serif; font-size:1.9rem; color:#0A1F44; font-weight:700; }
.gauge .track { position:relative; height:12px; border-radius:8px; background:#E6EBF3; margin:.9rem 0 .45rem; }
.gauge .zone { position:absolute; top:0; bottom:0; border-radius:8px; background:#BFE3D6; }
.gauge .mk { position:absolute; top:-5px; width:6px; height:22px; border-radius:4px; background:#0A1F44; transform:translateX(-50%); }
.gauge .rf { font-size:.74rem; color:#6B7690; }

/* Accesos */
.st-key-accesos button { height:84px; border-radius:16px; background:#fff; border:1px solid #DDE3EE; color:#0A1F44; font-weight:600; font-size:.98rem;
    box-shadow:0 3px 10px rgba(10,31,68,.06); transition: transform .18s, box-shadow .18s, border-color .18s; }
.st-key-accesos button:hover { transform:translateY(-4px); border-color:#C9A24B; color:#0A1F44; box-shadow:0 12px 24px rgba(10,31,68,.14); }

/* Botones y pestañas */
[data-testid="stMain"] [data-testid="stBaseButton-primary"], [data-testid="stMain"] [data-testid="stBaseButton-primaryFormSubmit"],
[data-testid="stMain"] button[kind="primary"], [data-testid="stMain"] button[kind="primaryFormSubmit"] {
    background: linear-gradient(135deg,#14407F,#0A1F44); border:none; color:#fff; border-radius:10px; font-weight:600; }
[data-testid="stMain"] button[kind="primary"]:hover { box-shadow:0 4px 14px rgba(10,31,68,.35); }
.stTabs [data-baseweb="tab-list"] { gap:.25rem; border-bottom:2px solid #E1E6EF; }
.stTabs [data-baseweb="tab"] { border-radius:10px 10px 0 0; padding:.5rem 1rem; font-weight:600; color:#5A6479; }
.stTabs [aria-selected="true"] { color:#0A1F44; background:#fff; }
[data-testid="stForm"] { background:#fff; border:1px solid #E1E6EF; border-radius:16px; padding:1.2rem; }
@media (prefers-reduced-motion: reduce) { * { animation:none !important; transition:none !important; } }
</style>
"""

HILLS_FAR = "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 700 170' preserveAspectRatio='none'%3E%3Cpath d='M0 90 Q175 10 350 90 T700 90 V170 H0Z' fill='%2316356B'/%3E%3C/svg%3E\")"
HILLS_NEAR = "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 700 170' preserveAspectRatio='none'%3E%3Cpath d='M0 70 Q175 0 350 70 T700 70 V170 H0Z' fill='%230D3A3A'/%3E%3C/svg%3E\")"

LOGIN_CSS = """
<style>
""" + FUENTES + """
[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"], [data-testid="collapsedControl"], [data-testid="stHeader"], [data-testid="stToolbar"], footer { display:none !important; }
.stApp { background:#F2F4F8; font-family:'DM Sans',sans-serif; }
.block-container { padding:0 !important; max-width:100% !important; }
[data-testid="stHorizontalBlock"] { gap:0 !important; align-items:stretch; }

.scene { position:relative; overflow:hidden; min-height:100vh; color:#fff; font-family:'DM Sans',sans-serif;
    background:linear-gradient(180deg,#071634 0%,#0F2D63 36%,#2B5089 60%,#D9A857 92%); }
.scene .stars { position:absolute; inset:0; }
.scene .stars i { position:absolute; width:3px; height:3px; border-radius:50%; background:#fff; opacity:.6; animation:tw 3.6s ease-in-out infinite; }
@keyframes tw { 50% { opacity:.12; } }
.scene .copy { position:absolute; left:clamp(1.5rem,5vw,4rem); top:clamp(1.5rem,6vh,4rem); max-width:30rem; z-index:5; animation:rise .9s ease both; }
@keyframes rise { from { opacity:0; transform:translateY(18px); } to { opacity:1; transform:none; } }
.scene .crest { width:84px; height:100px; margin-bottom:1.1rem; filter:drop-shadow(0 8px 16px rgba(0,0,0,.4)); }
.scene .crest img, .scene .crest svg { width:100%; height:100%; object-fit:contain; display:block; }
.scene .uni { color:#E9C46A; font-size:.8rem; letter-spacing:.12em; font-weight:600; }
.scene h1 { font-family:'Fraunces',serif; font-weight:700; font-size:clamp(2.4rem,5vw,3.8rem); line-height:1.02; color:#fff; margin:.35rem 0 .8rem; padding:0; }
.scene p { color:#C8D8F0; font-size:1.02rem; line-height:1.55; max-width:26rem; margin:0; }
.scene .art { position:absolute; right:clamp(1rem,6%,5rem); bottom:20%; width:min(46vw,360px); aspect-ratio:1; z-index:2; }
.scene .sun { position:absolute; inset:0; border-radius:50%; background:radial-gradient(circle at 50% 45%,#F7D58A 0%,#E9B95F 62%,#D9A04A 100%);
    box-shadow:0 0 90px 30px rgba(233,185,95,.45); animation:glow 6s ease-in-out infinite; }
@keyframes glow { 50% { box-shadow:0 0 120px 46px rgba(233,185,95,.6); } }
.scene .art svg { position:absolute; left:8%; top:6%; width:84%; height:auto; overflow:visible; }
.mane { transform-box:fill-box; transform-origin:100% 0; animation:sway 4.5s ease-in-out infinite; }
.m2 { animation-delay:-1.5s; } .m3 { animation-delay:-3s; }
@keyframes sway { 50% { transform:rotate(-3.5deg); } }
.hills { position:absolute; left:0; right:0; background-repeat:repeat-x; background-size:700px 100%; }
.hills.far { bottom:15%; height:170px; z-index:3; background-image:""" + HILLS_FAR + """; animation:pan 90s linear infinite; }
.hills.near { bottom:0; height:24%; min-height:130px; z-index:4; background-image:""" + HILLS_NEAR + """; animation:pan 50s linear infinite; }
@keyframes pan { to { background-position-x:-700px; } }
.scene .foot { position:absolute; left:clamp(1.5rem,5vw,4rem); bottom:1rem; font-size:.72rem; color:#9FB6D8; z-index:6; }

.st-key-acceso { max-width:470px; margin:0 auto; padding:clamp(1.5rem,7vh,4.5rem) 1.6rem 2rem; }
.a-head h2 { font-family:'Fraunces',serif; font-size:2.1rem; color:#0A1F44; margin:0; }
.a-head p { color:#5E6A82; margin:.35rem 0 1rem; }
.st-key-acceso [data-testid="stForm"] { border:none; padding:0; background:transparent; }
.st-key-acceso .stTabs [data-baseweb="tab-list"] { gap:.25rem; border-bottom:2px solid #E1E6EF; }
.st-key-acceso .stTabs [data-baseweb="tab"] { font-weight:600; padding:.5rem 1rem; color:#5A6479; }
.st-key-acceso .stTabs [aria-selected="true"] { color:#0A1F44; }
.st-key-acceso .stTabs [data-baseweb="tab-highlight"] { background:#C9A24B; }
.st-key-acceso button[kind^="primary"], .st-key-acceso [data-testid^="stBaseButton-primary"] { width:100%; background:linear-gradient(135deg,#14407F,#0A1F44);
    border:none; color:#fff; border-radius:12px; font-weight:700; padding:.65rem 1rem; transition:transform .15s, box-shadow .15s; }
.st-key-acceso button[kind^="primary"]:hover, .st-key-acceso [data-testid^="stBaseButton-primary"]:hover { transform:translateY(-2px); box-shadow:0 10px 22px rgba(10,31,68,.3); color:#fff; }
.meter { height:6px; border-radius:6px; background:#E3E8F1; overflow:hidden; margin:.15rem 0 .2rem; }
.meter i { display:block; height:100%; border-radius:6px; transition:width .3s; }
.meter-l { font-size:.76rem; color:#5E6A82; margin-bottom:.6rem; }
.a-note { font-size:.72rem; color:#8A93A6; margin-top:1.2rem; text-align:center; }
@media (max-width: 900px) { .scene { min-height:62vh; } .scene .art { width:44vw; bottom:14%; } .scene h1 { font-size:2.2rem; } }
@media (prefers-reduced-motion: reduce) { * { animation:none !important; transition:none !important; } }
</style>
"""

# ───────────────────────────── Catálogos configurables ─────────────────────────
AREAS_BASE = [
    "Medicina interna equina", "Urgencias y cólico", "Cirugía", "Anestesia", "Ortopedia y claudicaciones",
    "Podología y herraje", "Reproducción y obstetricia", "Neonatología (potros)", "Odontología equina",
    "Oftalmología", "Neurología", "Dermatología", "Rehabilitación y fisioterapia", "Laboratorio clínico",
    "Imagenología", "Radiología", "Ultrasonido", "Endoscopia", "Farmacia", "Consultas generales",
    "Aislamiento (enfermedades infecciosas)", "Hospitalización y caballerizas",
]

DEFAULT_CATALOGS = {
    "prioridades": ["Nivel 1 (definir criterio)", "Nivel 2 (definir criterio)", "Nivel 3 (definir criterio)", "Nivel 4 (definir criterio)"],
    "tipos_ingreso": ["Cita programada", "Consulta sin cita", "Urgencia", "Revisión", "Referencia de otra área"],
    "estados_atencion": ["Registrado", "En espera", "En valoración", "En consulta", "En estudios", "En tratamiento", "Finalizado"],
    "especies": ["Caballo", "Burro / asno", "Mula / macho", "Otro équido (especificar en raza)"],
    "sexos": ["Semental", "Caballo castrado (capón)", "Yegua", "Sin determinar"],
    "metodos_pago": ["Efectivo", "Tarjeta", "Transferencia", "Otro"],
    "modalidades": ["Servicio social", "Prácticas profesionales", "Estancias clínicas", "Rotaciones", "Actividades académicas", "Otros programas autorizados"],
    "tipos_estudio_lab": ["Biometría hemática", "Química sanguínea", "Fibrinógeno y proteínas", "Urianálisis", "Coproparasitoscópico (HPG)", "Prueba de Coggins (anemia infecciosa equina)", "Líquido peritoneal", "Líquido sinovial", "Otro (configurable)"],
    "tipos_muestra": ["Sangre", "Orina", "Heces", "Líquido peritoneal", "Líquido sinovial", "Líquido cefalorraquídeo", "Otra"],
    "estados_lab": ["Solicitado", "Pendiente de muestra", "Muestra recibida", "En proceso", "Resultado disponible", "Validado"],
    "tipos_imagen": ["Radiografía", "Ultrasonido", "Endoscopia", "Otro estudio (configurable)"],
    "estados_imagen": ["Solicitado", "Programado", "Realizado", "Interpretado", "Entregado"],
    "estados_inter": ["Solicitada", "En revisión", "Respondida", "Cerrada"],
    "estados_cirugia": ["Programada", "En preoperatorio", "En quirófano", "En recuperación", "Finalizada", "Cancelada"],
    "estados_cargo": ["Vigente", "Cancelado"],
    "tipos_mov": ["Entrada", "Salida", "Baja por caducidad / merma"],
    "categorias_servicio": ["Consultas", "Urgencias", "Laboratorio", "Imagenología", "Cirugía", "Hospitalización (box)", "Herraje y podología", "Medicamentos", "Procedimientos", "Otros servicios"],
    "tipos_registro": ["Consulta", "Exploración física", "Diagnóstico presuntivo", "Diagnóstico definitivo", "Evolución",
                       "Tratamiento", "Procedimiento", "Hospitalización", "Receta", "Alta médica", "Seguimiento"],
}
CAT_ETIQUETAS = {
    "prioridades": "Categorías de prioridad (triage)", "tipos_ingreso": "Tipos de ingreso", "estados_atencion": "Estados de atención",
    "especies": "Especies", "sexos": "Sexo", "metodos_pago": "Métodos de pago", "modalidades": "Modalidades académicas",
    "tipos_estudio_lab": "Estudios de laboratorio", "tipos_muestra": "Tipos de muestra", "estados_lab": "Estados de laboratorio",
    "tipos_imagen": "Estudios de imagenología", "estados_imagen": "Estados de imagenología", "estados_inter": "Estados de interconsulta",
    "estados_cirugia": "Estados de cirugía", "estados_cargo": "Estados de cargos/abonos", "tipos_mov": "Movimientos de farmacia",
    "categorias_servicio": "Categorías de servicio (tarifario)", "tipos_registro": "Tipos de registro clínico",
}
DEFAULT_CATALOGS["boxes"] = [f"Box {i}" for i in range(1, 21)] + ["Corral exterior 1", "Corral exterior 2", "Aislamiento 1", "Aislamiento 2"]
DEFAULT_CATALOGS["usos"] = ["Salto", "Charrería", "Doma", "Carreras", "Polo", "Trabajo de campo", "Recreación", "Reproductor / cría", "Terapia asistida", "Otro"]
CAT_ETIQUETAS["boxes"] = "Boxes y caballerizas"
CAT_ETIQUETAS["usos"] = "Uso o disciplina del equino"
RESTRINGIDOS = {"Diagnóstico definitivo", "Receta", "Alta médica"}

# ───────────────────────────── Roles y permisos ────────────────────────────────
R_ADMIN = "Administrador del sistema"
R_JEFE = "Jefe o responsable del hospital"
R_MVZ = "Médico veterinario responsable"
R_ESP = "Médico especialista"
R_REC = "Personal administrativo y recepción"
R_FAR = "Personal de farmacia"
R_LAB = "Personal de laboratorio e imagenología"
R_EST = "Estudiante de Medicina Veterinaria y Zootecnia"
R_PROF = "Profesor o médico supervisor"

ROLES = {
    R_ADMIN: dict(ver=["inicio", "pacientes", "finanzas", "estadisticas", "admin"], esc=["staff", "tarifa", "pac", "prop", "adm"], val=["cargo", "abono"]),
    R_JEFE: dict(ver=["inicio", "expediente", "interconsultas", "laboratorio", "imagen", "cirugia", "farmacia", "academico", "finanzas", "estadisticas"], esc=[], val=[]),
    R_MVZ: dict(ver=["inicio", "recepcion", "triage", "pacientes", "expediente", "interconsultas", "laboratorio", "imagen", "cirugia", "farmacia", "estadisticas"],
                esc=["adm", "triage", "clin", "inter", "lab", "img", "cir", "pac", "prop"], val=["triage", "clin", "inter", "lab", "img", "cir"]),
    R_ESP: dict(ver=["inicio", "triage", "pacientes", "expediente", "interconsultas", "laboratorio", "imagen", "cirugia"],
                esc=["clin", "inter", "lab", "img", "cir", "triage"], val=["clin", "inter", "img", "cir"]),
    R_REC: dict(ver=["inicio", "recepcion", "pacientes", "finanzas"], esc=["adm", "pac", "prop", "cargo", "abono"], val=[]),
    R_FAR: dict(ver=["inicio", "farmacia"], esc=["farm_med", "farm_mov", "farm_disp", "farm_prov"], val=["farm_disp"]),
    R_LAB: dict(ver=["inicio", "laboratorio", "imagen"], esc=["lab", "img"], val=["lab", "img"]),
    R_EST: dict(ver=["inicio", "triage", "expediente", "academico"], esc=["clin", "triage", "acad"], val=[]),
    R_PROF: dict(ver=["inicio", "triage", "expediente", "interconsultas", "laboratorio", "imagen", "cirugia", "academico"],
                 esc=["clin", "acad"], val=["clin", "triage", "inter", "cir", "acad"]),
}
EXPORTA = {R_ADMIN, R_JEFE, R_MVZ}
for _r in (R_MVZ, R_ESP, R_EST, R_PROF, R_JEFE):
    ROLES[_r]["ver"].append("herramientas")

MODULOS = {
    "inicio": "Panel principal", "recepcion": "Recepción y admisión", "triage": "Triage veterinario",
    "pacientes": "Propietarios y pacientes", "expediente": "Expediente clínico", "interconsultas": "Interconsultas",
    "laboratorio": "Laboratorio clínico", "imagen": "Imagenología", "cirugia": "Cirugías y anestesia",
    "farmacia": "Farmacia hospitalaria", "academico": "Control académico", "finanzas": "Administración financiera",
    "estadisticas": "Estadísticas", "herramientas": "Herramientas clínicas", "admin": "Administración del sistema",
}


def yo() -> str:
    return st.session_state.get("user_name", "").strip() or "Usuario sin nombre"


def rol() -> str:
    return st.session_state.rol


def puede_esc(col): return col in ROLES[rol()]["esc"]
def puede_val(col): return col in ROLES[rol()]["val"]


# ───────────────────────────── Definición de colecciones ───────────────────────
def F(k, l, t="text", o=None, req=False, **kw):
    return dict(k=k, l=l, t=t, o=o, req=req, **kw)


def _tipos_clin():
    return [t for t in st.session_state.cat["tipos_registro"] if t not in RESTRINGIDOS or puede_val("clin")]


FLT_RECETA = lambda r: r["d"].get("tipo_registro") == "Receta" and r["val"] == "Validado"

COL = {
    "prop": dict(t="Propietario", pref="PRP", valida=False, estado=None, lbl=["nombre"], campos=[
        F("nombre", "Nombre completo", req=True), F("telefono", "Teléfono"), F("correo", "Correo electrónico"),
        F("identificacion", "Identificación (opcional)"), F("direccion", "Domicilio", "area", h=70), F("obs", "Observaciones", "area", h=70)]),
    "pac": dict(t="Paciente", pref="PAC", valida=False, estado=None, lbl=["nombre", "especie"], campos=[
        F("nombre", "Nombre del equino", req=True), F("especie", "Especie", "select", "@especies", req=True), F("raza", "Raza"),
        F("sexo", "Sexo", "select", "@sexos"), F("edad", "Edad aproximada"), F("peso", "Peso inicial (kg)", "number", step=1.0),
        F("capa", "Capa y señas particulares"), F("alzada", "Alzada a la cruz (cm)", "number", step=1.0), F("uso", "Uso o disciplina", "select", "@usos"),
        F("microchip", "Microchip / pasaporte / hierro"), F("propietario", "Propietario", "ref", "prop", req=True),
        F("alergias", "Alergias conocidas", "area", h=70), F("antecedentes", "Antecedentes relevantes", "area", h=70)]),
    "adm": dict(t="Admisión", pref="ADM", valida=False, estado="estados_atencion", lbl=["paciente"], campos=[
        F("paciente", "Paciente", "ref", "pac", req=True), F("tipo_ingreso", "Tipo de ingreso", "select", "@tipos_ingreso", req=True),
        F("area", "Área solicitada", "select", "@areas", req=True), F("medico", "Médico asignado", "staff"), F("box", "Box / caballeriza", "select", "@boxes"),
        F("motivo", "Motivo de atención", "area", req=True, h=80), F("participantes", "Participantes autorizados (separados por coma)"),
        F("obs", "Observaciones", "area", h=60)]),
    "triage": dict(t="Triage", pref="TRI", valida=True, estado=None, lbl=["paciente", "prioridad"], campos=[
        F("paciente", "Paciente", "ref", "pac", req=True), F("hora", "Hora de ingreso", "time"),
        F("motivo", "Motivo de urgencia", "area", req=True, h=70), F("estado_general", "Estado general", "area", h=70),
        F("temp", "Temperatura (°C)", "number"), F("fc", "Frecuencia cardiaca (lpm)", "number"), F("fr", "Frecuencia respiratoria (rpm)", "number"),
        F("peso", "Peso (kg)", "number", step=1.0), F("mucosas", "Mucosas / TLLC"), F("dolor", "Escala de dolor (0–10)", "int"),
        F("motilidad", "Motilidad intestinal", "select", ["Normal", "Disminuida", "Ausente", "Aumentada"]),
        F("prioridad", "Nivel de prioridad (propuesto)", "select", "@prioridades", req=True),
        F("area_destino", "Área de destino", "select", "@areas", req=True), F("obs", "Observaciones", "area", h=60)]),
    "clin": dict(t="Registro clínico", pref="CLI", valida=True, estado=None, lbl=["paciente", "tipo_registro"], campos=[
        F("paciente", "Paciente", "ref", "pac", req=True), F("tipo_registro", "Tipo de registro", "select", _tipos_clin, req=True),
        F("area", "Área hospitalaria", "select", "@areas", req=True), F("participantes", "Participantes autorizados (separados por coma)"),
        F("motivo", "Motivo / contexto", "area", h=70), F("hallazgos", "Exploración / hallazgos / evolución", "area", h=110),
        F("diagnostico", "Diagnóstico / impresión", "area", h=80), F("plan", "Plan, tratamiento o prescripción", "area", h=110),
        F("peso", "Peso (kg)", "number", step=1.0), F("temp", "Temperatura (°C)", "number"), F("fc", "FC (lpm)", "number"), F("fr", "FR (rpm)", "number"),
        F("claudicacion", "Grado de claudicación (AAEP 0–5)", "select", ["0", "1", "2", "3", "4", "5"]),
        F("condicion", "Condición corporal (Henneke 1–9)", "select", [str(i) for i in range(1, 10)])]),
    "inter": dict(t="Interconsulta", pref="INT", valida=True, estado="estados_inter", lbl=["paciente", "area_destino"], campos=[
        F("paciente", "Paciente", "ref", "pac", req=True), F("area_origen", "Área solicitante", "select", "@areas"),
        F("area_destino", "Área de destino", "select", "@areas", req=True), F("especialista", "Especialista solicitado", "staff"),
        F("motivo", "Motivo de referencia", "area", req=True, h=80),
        F("expediente", "Registros del expediente que se adjuntan", "refmulti", "clin"), F("adjuntos", "Archivos adjuntos", "file"),
        F("obs", "Observaciones", "area", h=60), F("respuesta", "Respuesta del especialista", "area", h=100)]),
    "lab": dict(t="Estudio de laboratorio", pref="LAB", valida=True, estado="estados_lab", lbl=["paciente", "tipo_estudio"], campos=[
        F("paciente", "Paciente", "ref", "pac", req=True), F("solicitante", "Médico solicitante", "staff"),
        F("consulta", "Consulta que originó la solicitud", "ref", "clin"), F("tipo_estudio", "Tipo de estudio", "select", "@tipos_estudio_lab", req=True),
        F("tipo_muestra", "Tipo de muestra", "select", "@tipos_muestra"), F("fecha_toma", "Fecha de toma", "date", opt=True),
        F("resp_toma", "Responsable de toma", "staff"), F("fecha_proc", "Fecha de procesamiento", "date", opt=True),
        F("resultado", "Resultado", "area", h=110), F("obs", "Observaciones", "area", h=60), F("archivos", "Archivo adjunto (PDF)", "file", ft=["pdf"])]),
    "img": dict(t="Estudio de imagenología", pref="IMG", valida=True, estado="estados_imagen", lbl=["paciente", "tipo_estudio"], campos=[
        F("paciente", "Paciente", "ref", "pac", req=True), F("solicitante", "Médico solicitante", "staff"),
        F("motivo", "Motivo del estudio", "area", req=True, h=70), F("fecha", "Fecha del estudio", "date"),
        F("tipo_estudio", "Tipo de estudio", "select", "@tipos_imagen", req=True), F("area_resp", "Área responsable", "select", "@areas"),
        F("interpreta", "Médico que interpreta", "staff"), F("previo", "Estudio anterior para comparar", "ref", "img"),
        F("informe", "Informe diagnóstico", "area", h=110), F("archivos", "Imágenes / archivos", "file", ft=["png", "jpg", "jpeg", "pdf", "dcm"])]),
    "cir": dict(t="Cirugía / anestesia", pref="CIR", valida=True, estado="estados_cirugia", lbl=["paciente", "tipo_cirugia"], campos=[
        F("paciente", "Paciente", "ref", "pac", req=True), F("cirujano", "Médico cirujano responsable", "staff"), F("equipo", "Equipo participante", "area", h=60),
        F("tipo_cirugia", "Tipo de cirugía", req=True), F("diagnostico", "Diagnóstico", "area", h=60), F("fecha", "Fecha", "date"), F("hora", "Hora", "time"),
        F("area_quir", "Área quirúrgica", "select", "@areas"), F("preop", "Evaluación preoperatoria", "area", h=80),
        F("anest_eval", "Evaluación anestésica", "area", h=80), F("anestesiologo", "Anestesiólogo responsable", "staff"),
        F("transop", "Registro transoperatorio", "area", h=100), F("incidentes", "Incidentes", "area", h=60), F("recuperacion", "Recuperación", "area", h=70),
        F("postop", "Indicaciones posoperatorias", "area", h=80), F("verificacion", "Verificación prequirúrgica completada", "bool"),
        F("autorizacion", "Autorización del responsable del paciente registrada", "bool"), F("archivos", "Documentación quirúrgica / anestésica", "file")]),
    "farm_prov": dict(t="Proveedor", pref="PRV", valida=False, estado=None, lbl=["nombre"], campos=[
        F("nombre", "Proveedor", req=True), F("contacto", "Contacto"), F("telefono", "Teléfono"), F("correo", "Correo"), F("obs", "Observaciones", "area", h=60)]),
    "farm_med": dict(t="Medicamento / lote", pref="MED", valida=False, estado=None, lbl=["principio", "concentracion", "lote"], campos=[
        F("principio", "Principio activo", req=True), F("comercial", "Nombre comercial"), F("concentracion", "Concentración"),
        F("presentacion", "Presentación"), F("lote", "Lote", req=True), F("caducidad", "Caducidad", "date", req=True),
        F("inicial", "Existencia inicial (unidades)", "int"), F("proveedor", "Proveedor", "ref", "farm_prov"), F("obs", "Observaciones", "area", h=60)]),
    "farm_mov": dict(t="Movimiento de farmacia", pref="MOV", valida=False, estado=None, lbl=["lote", "tipo"], campos=[
        F("lote", "Medicamento / lote", "ref", "farm_med", req=True), F("tipo", "Tipo de movimiento", "select", "@tipos_mov", req=True),
        F("cantidad", "Cantidad", "int", req=True), F("documento", "Documento / referencia"), F("motivo", "Motivo", "area", h=60)]),
    "farm_disp": dict(t="Dispensación", pref="DIS", valida=True, estado=None, lbl=["receta", "lote"], campos=[
        F("receta", "Receta validada", "ref", "clin", req=True, flt=FLT_RECETA), F("lote", "Medicamento / lote", "ref", "farm_med", req=True),
        F("cantidad", "Cantidad", "int", req=True),
        F("resultado", "Situación", "select", ["Entregado al propietario", "Administrado en el hospital", "No entregado"], req=True),
        F("obs", "Observaciones", "area", h=60)]),
    "tarifa": dict(t="Tarifa", pref="TAR", valida=False, estado=None, lbl=["concepto"], campos=[
        F("categoria", "Categoría de servicio", "select", "@categorias_servicio", req=True), F("concepto", "Concepto", req=True),
        F("precio", "Precio (MXN) — definido por el hospital", "number", step=1.0), F("vigente", "Vigente", "bool")]),
    "cargo": dict(t="Cargo", pref="CAR", valida=False, estado="estados_cargo", lbl=["propietario", "concepto"], campos=[
        F("propietario", "Propietario", "ref", "prop", req=True), F("paciente", "Paciente", "ref", "pac"),
        F("tarifa", "Concepto del tarifario", "ref", "tarifa"), F("concepto", "Concepto libre (si no hay tarifa)"),
        F("cantidad", "Cantidad", "int", req=True), F("precio", "Precio unitario (0 = tomar del tarifario)", "number", step=1.0)]),
    "abono": dict(t="Abono", pref="ABO", valida=False, estado="estados_cargo", lbl=["propietario", "monto"], campos=[
        F("propietario", "Propietario", "ref", "prop", req=True), F("monto", "Monto (MXN)", "number", req=True, step=1.0),
        F("metodo", "Método de pago", "select", "@metodos_pago", req=True), F("referencia", "Referencia / folio de pago")]),
    "acad": dict(t="Actividad académica", pref="ACA", valida=True, estado=None, lbl=["estudiante", "modalidad"], campos=[
        F("estudiante", "Estudiante", req=True), F("identificador", "Número de cuenta / identificador (si está autorizado)"),
        F("programa", "Programa académico"), F("modalidad", "Modalidad de participación", "select", "@modalidades", req=True),
        F("area", "Área asignada", "select", "@areas", req=True), F("supervisor", "Médico o profesor supervisor", "staff"),
        F("fecha", "Fecha", "date"), F("h_ini", "Hora de inicio", "time"), F("h_fin", "Hora de término", "time"),
        F("actividades", "Actividades realizadas", "area", req=True, h=100),
        F("casos", "Casos clínicos en los que participó (solo folio)", "refmulti", "pac", anon=True), F("obs", "Observaciones", "area", h=60)]),
    "staff": dict(t="Personal", pref="PER", valida=False, estado=None, lbl=["nombre", "rol"], campos=[
        F("nombre", "Nombre completo", req=True), F("rol", "Perfil en el sistema", "select", list(ROLES), req=True),
        F("areas", "Áreas", "multi", "@areas"), F("correo", "Correo institucional"), F("cedula", "Cédula profesional (captura manual)"),
        F("horario", "Horario (definido por el área)"), F("activo", "Activo", "bool")]),
}
VAL_PEND, VAL_OK, VAL_ENM, VAL_DEV, VAL_NA = "Pendiente de validación", "Validado", "Enmendado – pendiente de revalidación", "Devuelto para corrección", "No aplica"


# ───────────────────────────── Capa de datos (sustituible por BD) ──────────────
class Repo:
    """Capa de persistencia en memoria. Reemplazar por acceso a base de datos."""

    @staticmethod
    def listar(col): return st.session_state.db[col]

    @staticmethod
    def buscar(col, folio):
        return next((r for r in st.session_state.db[col] if r["folio"] == folio), None)

    @staticmethod
    def hist(rec, accion, detalle=""):
        e = dict(ts=datetime.now().isoformat(timespec="seconds"), por=yo(), rol=rol(), accion=accion, detalle=detalle)
        rec["hist"].append(e)
        st.session_state.audit.append(dict(e, folio=rec["folio"]))

    @staticmethod
    def crear(col, d, files, validado=False):
        spec = COL[col]
        n = len(st.session_state.db[col]) + 1
        ahora = datetime.now()
        rec = dict(folio=f"{spec['pref']}-{ahora.year}-{n:04d}", ts=ahora.isoformat(timespec="seconds"), fecha=ahora.date().isoformat(),
                   por=yo(), rol=rol(), d=d, files=files, hist=[], versiones=[], fin=None,
                   val=VAL_PEND if spec["valida"] else VAL_NA)
        st.session_state.db[col].append(rec)
        Repo.hist(rec, "Creación", spec["t"])
        if validado and spec["valida"]:
            Repo.validar(col, rec)
        return rec

    @staticmethod
    def modificar(col, rec, nuevo, files, enmienda="", ):
        cambios = [k for k in nuevo if nuevo[k] != rec["d"].get(k)]
        rec["versiones"].append(dict(ts=datetime.now().isoformat(timespec="seconds"), por=yo(), rol=rol(), d=copy.deepcopy(rec["d"]), motivo=enmienda))
        rec["d"].update(nuevo)
        rec["files"].extend(files)
        if enmienda:
            rec["val"] = VAL_ENM
            Repo.hist(rec, "Enmienda de registro validado", f"Motivo: {enmienda}. Campos: {', '.join(cambios) or '—'}")
        else:
            if rec["val"] == VAL_DEV:
                rec["val"] = VAL_PEND
            Repo.hist(rec, "Edición", f"Campos: {', '.join(cambios) or '—'}")

    @staticmethod
    def validar(col, rec):
        rec["val"] = VAL_OK
        base = json.dumps(rec["d"], sort_keys=True, default=str) + rec["folio"] + yo() + datetime.now().isoformat()
        rec["sello"] = hashlib.sha256(base.encode()).hexdigest()[:16].upper()
        rec["validado_por"] = f"{yo()} ({rol()})"
        Repo.hist(rec, "Validación / firma electrónica interna", f"Sello {rec['sello']}")


def etiqueta(col, rec, corto=False, anon=False):
    if anon and col == "pac":
        return f"{rec['folio']} · {rec['d'].get('especie', '')}"
    partes = []
    for k in COL[col]["lbl"]:
        v = rec["d"].get(k, "")
        fd = next((f for f in COL[col]["campos"] if f["k"] == k), None)
        if fd and fd["t"] == "ref" and v:
            r2 = Repo.buscar(fd["o"], v)
            v = etiqueta(fd["o"], r2, corto=True) if r2 else v
        if isinstance(v, float):
            v = f"${v:,.2f}"
        if v:
            partes.append(str(v))
    if corto:
        return " · ".join(partes) or rec["folio"]
    return f"{rec['folio']} — " + " · ".join(partes) if partes else rec["folio"]


def legible(f, v):
    if v in (None, "", [], 0.0) and f["t"] != "bool":
        return ""
    if f["t"] == "ref":
        r = Repo.buscar(f["o"], v)
        return etiqueta(f["o"], r, corto=True) if r else str(v)
    if f["t"] == "refmulti":
        return ", ".join(etiqueta(f["o"], Repo.buscar(f["o"], x), corto=True, anon=f.get("anon", False)) if Repo.buscar(f["o"], x) else x for x in v)
    if f["t"] == "bool":
        return "Sí" if v else "No"
    if isinstance(v, list):
        return ", ".join(map(str, v))
    if f["t"] in ("number",):
        return f"{v:g}"
    return str(v)


# ───────────────────────────── Reglas de visibilidad ───────────────────────────
def pacientes_visibles() -> set:
    todos = {r["folio"] for r in Repo.listar("pac")}
    if rol() != R_EST:
        return todos
    me = yo().lower()
    vis = set()
    for r in Repo.listar("adm"):
        if me in [p.strip().lower() for p in r["d"].get("participantes", "").split(",") if p.strip()]:
            vis.add(r["d"]["paciente"])
    for c in ("clin", "triage"):
        for r in Repo.listar(c):
            if r["por"] == yo():
                vis.add(r["d"]["paciente"])
    return vis & todos


def visibles(col) -> list:
    recs = Repo.listar(col)
    if rol() == R_EST:
        if col == "acad":
            return [r for r in recs if r["d"].get("estudiante", "").strip().lower() == yo().lower() or r["por"] == yo()]
        if any(f["k"] == "paciente" for f in COL[col]["campos"]):
            pv = pacientes_visibles()
            return [r for r in recs if r["d"].get("paciente") in pv or r["por"] == yo()]
        if col == "pac":
            pv = pacientes_visibles()
            return [r for r in recs if r["folio"] in pv]
    return recs


# ───────────────────────────── Formularios genéricos ───────────────────────────
def opciones(f):
    o = f.get("o")
    if callable(o):
        return o()
    if isinstance(o, str) and o.startswith("@"):
        k = o[1:]
        if k == "areas":
            return [a["Área"] for a in st.session_state.areas if a["Activa"] and a["Área"]]
        return list(st.session_state.cat.get(k, []))
    return list(o or [])


def _fecha(v):
    try:
        return date.fromisoformat(v) if v else None
    except Exception:
        return None


def _hora(v):
    try:
        return time.fromisoformat(v) if v else None
    except Exception:
        return None


def campo(f, kp, dv=None):
    k, t = f["k"], f.get("t", "text")
    lab = f["l"] + (" *" if f.get("req") else "")
    key = f"{kp}_{k}"
    if t == "text":
        return st.text_input(lab, value=dv or "", key=key)
    if t == "area":
        return st.text_area(lab, value=dv or "", key=key, height=max(68, f.get("h", 90)))
    if t == "select":
        op = opciones(f)
        if not op:
            st.warning(f"No hay opciones configuradas para «{f['l']}». Configúrelas en Administración.")
            return ""
        if not f.get("req"):
            op = [""] + op
        idx = op.index(dv) if dv in op else 0
        return st.selectbox(lab, op, index=idx, key=key, format_func=lambda x: x or "—")
    if t == "multi":
        op = opciones(f)
        return st.multiselect(lab, op, default=[x for x in (dv or []) if x in op], key=key)
    if t == "date":
        ini = _fecha(dv) or (None if f.get("opt") else date.today())
        v = st.date_input(lab, value=ini, key=key, format="DD/MM/YYYY")
        return v.isoformat() if v else ""
    if t == "time":
        v = st.time_input(lab, value=_hora(dv) or datetime.now().time().replace(second=0, microsecond=0), key=key)
        return v.strftime("%H:%M")
    if t == "number":
        return float(st.number_input(lab, min_value=0.0, value=float(dv or 0.0), step=float(f.get("step", 0.1)), key=key))
    if t == "int":
        return int(st.number_input(lab, min_value=0, value=int(dv or 0), step=1, key=key))
    if t == "bool":
        return st.checkbox(lab, value=bool(dv) if dv is not None else (k == "activo" or k == "vigente"), key=key)
    if t == "staff":
        nombres = [s["d"]["nombre"] for s in Repo.listar("staff") if s["d"].get("activo", True)]
        if nombres:
            op = [""] + nombres
            return st.selectbox(lab, op, index=op.index(dv) if dv in op else 0, key=key, format_func=lambda x: x or "—")
        return st.text_input(lab, value=dv or "", key=key, help="Registre al personal en Administración para elegirlo de una lista.")
    if t in ("ref", "refmulti"):
        recs = Repo.listar(f["o"])
        if f["o"] == "pac" and rol() == R_EST:
            pv = pacientes_visibles()
            recs = [r for r in recs if r["folio"] in pv]
        if f.get("flt"):
            recs = [r for r in recs if f["flt"](r)]
        mapa = {r["folio"]: etiqueta(f["o"], r, anon=f.get("anon", False)) for r in recs}
        if not mapa:
            st.caption(f"{f['l']}: aún no hay registros disponibles.")
        if t == "refmulti":
            return st.multiselect(lab, list(mapa), default=[x for x in (dv or []) if x in mapa], key=key, format_func=lambda x: mapa.get(x, x))
        op = [""] + list(mapa)
        return st.selectbox(lab, op, index=op.index(dv) if dv in op else 0, key=key, format_func=lambda x: mapa.get(x, "—"))
    if t == "file":
        fs = st.file_uploader(lab, accept_multiple_files=True, type=f.get("ft"), key=key)
        return [dict(campo=k, nombre=x.name, bytes=x.getvalue()) for x in (fs or [])]
    return None


def formulario(col, modo="nuevo", rec=None, defaults=None):
    spec, ss = COL[col], st.session_state
    kp = f"{col}_{modo}_{rec['folio'] if rec else ''}_{ss.ver[col]}"
    dv = rec["d"] if rec else (defaults or {})
    vals, files = {}, []
    with st.form(kp):
        toggle, pair = 0, None
        for f in spec["campos"]:
            full = f["t"] in ("area", "file", "refmulti", "multi")
            if full:
                toggle = 0
                ctx = st.container()
            else:
                if toggle == 0:
                    pair = st.columns(2)
                ctx = pair[toggle]
                toggle = 1 - toggle
            with ctx:
                v = campo(f, kp, dv.get(f["k"]))
            if f["t"] == "file":
                files.extend(v)
            else:
                vals[f["k"]] = v
        if spec["estado"]:
            ops = list(ss.cat[spec["estado"]])
            actual = dv.get("estado")
            vals["estado"] = st.selectbox("Estado", ops, index=ops.index(actual) if actual in ops else 0, key=f"{kp}_estado")
        motivo, auto = "", False
        if modo == "enmendar":
            motivo = st.text_input("Motivo de la enmienda * (queda como evidencia)", key=f"{kp}_mot")
        if modo == "nuevo" and spec["valida"] and puede_val(col):
            auto = st.checkbox("Autorizar con firma electrónica interna al guardar", key=f"{kp}_auto")
        etiqueta_btn = {"nuevo": "Guardar registro", "editar": "Guardar cambios", "enmendar": "Registrar enmienda"}[modo]
        ok = st.form_submit_button(etiqueta_btn, type="primary")
    if not ok:
        return
    errores = []
    for f in spec["campos"]:
        if f.get("req"):
            v = vals.get(f["k"])
            if v in ("", None, [], 0, 0.0):
                errores.append(f["l"])
    if modo == "enmendar" and not motivo.strip():
        errores.append("Motivo de la enmienda")
    if errores:
        st.error("Complete los campos obligatorios: " + ", ".join(errores))
        return
    vals, err = PRE.get(col, lambda d, r: (d, None))(vals, rec)
    if err:
        st.error(err)
        return
    if modo == "nuevo":
        r = Repo.crear(col, vals, files, validado=auto)
        ss.flash = f"{spec['t']} registrado con folio {r['folio']}."
        if col == "adm":
            ss.pop("box_preseleccionado", None)
    else:
        Repo.modificar(col, rec, vals, files, enmienda=motivo.strip() if modo == "enmendar" else "")
        ss.flash = f"{spec['t']} {rec['folio']} actualizado y registrado en la bitácora."
    ss.ver[col] += 1
    st.rerun()


# ───────────────────────────── Reglas específicas ──────────────────────────────
def stock_lote(folio) -> int:
    m = Repo.buscar("farm_med", folio)
    if not m:
        return 0
    s = int(m["d"].get("inicial", 0))
    for r in Repo.listar("farm_mov"):
        if r["d"]["lote"] == folio:
            s += r["d"]["cantidad"] if r["d"]["tipo"] == "Entrada" else -r["d"]["cantidad"]
    for r in Repo.listar("farm_disp"):
        if r["d"]["lote"] == folio and r["d"]["resultado"] != "No entregado":
            s -= r["d"]["cantidad"]
    return s


def _pre_salida(d, rec):
    if d["tipo"] != "Entrada" and d["cantidad"] > stock_lote(d["lote"]):
        return d, f"Existencia insuficiente (disponible: {stock_lote(d['lote'])})."
    return d, None


def _pre_disp(d, rec):
    if d["resultado"] != "No entregado":
        disp = stock_lote(d["lote"])
        if rec and rec["d"].get("resultado") != "No entregado" and rec["d"]["lote"] == d["lote"]:
            disp += rec["d"]["cantidad"]
        if d["cantidad"] > disp:
            return d, f"Existencia insuficiente (disponible: {disp})."
    return d, None


def _pre_cargo(d, rec):
    t = Repo.buscar("tarifa", d.get("tarifa", "")) if d.get("tarifa") else None
    if not d.get("precio") and t:
        d["precio"] = float(t["d"].get("precio", 0))
    if not d.get("concepto") and t:
        d["concepto"] = t["d"]["concepto"]
    if not d.get("concepto"):
        return d, "Indique un concepto del tarifario o un concepto libre."
    if not d.get("precio"):
        return d, "No hay precio: configure el tarifario o capture el precio unitario."
    return d, None


PRE = {"farm_mov": _pre_salida, "farm_disp": _pre_disp, "cargo": _pre_cargo}


# ───────────────────────────── Componentes de interfaz ─────────────────────────
def pill_val(v):
    c = {VAL_OK: "p-ok", VAL_PEND: "p-pen", VAL_ENM: "p-pen", VAL_DEV: "p-dev", VAL_NA: "p-na"}.get(v, "p-na")
    return f'<span class="pill {c}">{h(v)}</span>'


def hero():
    st.markdown(html_min(f"""
    <div class="hero"><div class="shoe">{HERRADURA_SVG}</div>
      <div class="hero-left"><div class="crest">{escudo_html()}</div><div>
        <div class="hero-top">UNIVERSIDAD NACIONAL AUTÓNOMA DE MÉXICO</div>
        <div class="hero-title">Hospital de Equinos</div>
        <div class="hero-sub">{h(HOSPITAL_SEDE)}</div></div></div>
      <div class="hero-right"><b>Sistema integral de gestión hospitalaria veterinaria</b><br>{h(fecha_larga())}</div></div>"""),
        unsafe_allow_html=True)


def titulo(mod, sub=""):
    nombre = MODULOS[mod]
    st.markdown(f'<div class="pt"><h2>{h(nombre)}</h2><p>{h(sub)}</p><div class="bar"></div></div>', unsafe_allow_html=True)


def vacio(msg):
    st.markdown(f'<div class="empty">{h(msg)}</div>', unsafe_allow_html=True)


def kpi(n, l, cls=""):
    if isinstance(n, int) and not isinstance(n, bool):
        val = f'<div class="n cnt" style="--t:{n}"></div>'
    else:
        val = f'<div class="n">{h(n)}</div>'
    st.markdown(f'<div class="kpi {cls}">{val}<div class="l">{h(l)}</div></div>', unsafe_allow_html=True)


def detalle(col, rec):
    spec = COL[col]
    est = rec["d"].get("estado")
    st.markdown(f"**{h(rec['folio'])}** &nbsp; {pill_val(rec['val'])}" + (f'<span class="pill p-est">{h(est)}</span>' if est else ""), unsafe_allow_html=True)
    st.caption(f"Registrado el {rec['ts'].replace('T', ' ')} por {rec['por']} ({rec['rol']})"
               + (f" · Validado por {rec['validado_por']} · Sello {rec['sello']}" if rec["val"] == VAL_OK else ""))
    a, b = st.columns(2)
    n = 0
    for f in spec["campos"]:
        if f["t"] == "file":
            continue
        v = legible(f, rec["d"].get(f["k"]))
        if v == "" and f["t"] != "bool":
            continue
        (a if n % 2 == 0 else b).markdown(f"**{f['l']}**  \n{v}")
        n += 1
    if rec["files"]:
        st.markdown("**Archivos**")
        for i, fl in enumerate(rec["files"]):
            st.download_button(f"{fl['nombre']}", fl["bytes"], file_name=fl["nombre"], key=f"dl_{rec['folio']}_{i}")
        imgs = [fl for fl in rec["files"] if fl["nombre"].lower().endswith((".png", ".jpg", ".jpeg"))]
        if imgs:
            cols = st.columns(min(3, len(imgs)))
            for c, fl in zip(cols, imgs):
                c.image(fl["bytes"], caption=fl["nombre"])
        if col == "img" and rec["d"].get("previo"):
            prev = Repo.buscar("img", rec["d"]["previo"])
            pi = [fl for fl in (prev["files"] if prev else []) if fl["nombre"].lower().endswith((".png", ".jpg", ".jpeg"))]
            if pi and imgs:
                st.markdown("**Comparación con estudio anterior**")
                c1, c2 = st.columns(2)
                c1.image(imgs[0]["bytes"], caption=f"Actual · {rec['folio']}")
                c2.image(pi[0]["bytes"], caption=f"Anterior · {prev['folio']}")
    with st.expander("Bitácora de cambios y versiones"):
        tabla(pd.DataFrame(rec["hist"]).rename(columns=dict(ts="Fecha y hora", por="Usuario", rol="Rol", accion="Acción", detalle="Detalle")))
        if rec["versiones"]:
            st.caption(f"{len(rec['versiones'])} versión(es) anterior(es) conservada(s) como evidencia.")


def df_registros(col, recs):
    spec, rows = COL[col], []
    for r in recs:
        row = {"Folio": r["folio"], "Fecha": r["ts"].replace("T", " ")[:16], "Registró": r["por"], "Validación": r["val"]}
        for f in spec["campos"]:
            if f["t"] == "file":
                continue
            v = legible(f, r["d"].get(f["k"]))
            row[f["l"].replace(" *", "")] = v[:90]
        if spec["estado"]:
            row["Estado"] = r["d"].get("estado", "")
        rows.append(row)
    return pd.DataFrame(rows)


def pagina_col(col, extras_nuevo=None):
    spec, ss = COL[col], st.session_state
    esc, val = puede_esc(col), puede_val(col)
    nombres = []
    if esc: nombres.append("Nuevo")
    nombres.append("Registros")
    if esc: nombres.append("Actualizar")
    if val and spec["valida"]: nombres.append("Validación")
    if val and not spec["valida"]: nombres.append("Cancelaciones")
    tabs = dict(zip(nombres, st.tabs(nombres)))
    recs = visibles(col)

    if "Nuevo" in tabs:
        with tabs["Nuevo"]:
            if rol() == R_EST and spec["valida"]:
                st.info("Como estudiante, sus registros quedan **pendientes de validación** por el médico responsable o supervisor.")
            formulario(col, "nuevo", defaults=extras_nuevo)

    with tabs["Registros"]:
        if not recs:
            vacio(f"Aún no hay {spec['t'].lower()}s registrados.")
        else:
            c1, c2 = st.columns([3, 1.4])
            q = c1.text_input("Buscar", key=f"q_{col}", placeholder="Folio, nombre, texto…")
            fv = c2.selectbox("Validación", ["Todas", VAL_PEND, VAL_OK, VAL_ENM, VAL_DEV], key=f"fv_{col}") if spec["valida"] else "Todas"
            df = df_registros(col, recs)
            if q:
                df = df[df.apply(lambda r: q.lower() in " ".join(map(str, r.values)).lower(), axis=1)]
            if fv != "Todas":
                df = df[df["Validación"] == fv]
            tabla(df)
            if col in ("farm_med",):
                st.caption("Existencias calculadas = existencia inicial + entradas − salidas − dispensaciones.")
            fol = st.selectbox("Ver detalle", [""] + list(df["Folio"]), key=f"det_{col}", format_func=lambda x: etiqueta(col, Repo.buscar(col, x)) if x else "Seleccione un registro…")
            if fol:
                detalle(col, Repo.buscar(col, fol))

    if "Actualizar" in tabs:
        with tabs["Actualizar"]:
            edit = [r for r in recs if r["val"] != VAL_OK and (rol() != R_EST or r["por"] == yo())]
            if not edit:
                vacio("No hay registros editables. Los registros validados solo pueden enmendarse con evidencia por personal autorizado.")
            else:
                fol = st.selectbox("Registro a actualizar", [r["folio"] for r in edit], key=f"ed_{col}", format_func=lambda x: etiqueta(col, Repo.buscar(col, x)))
                rec = Repo.buscar(col, fol)
                if spec["estado"]:
                    with st.form(f"estado_{col}_{fol}_{ss.ver[col]}"):
                        e1, e2 = st.columns([1, 2])
                        ops = list(ss.cat[spec["estado"]])
                        cur = rec["d"].get("estado")
                        nuevo = e1.selectbox("Nuevo estado", ops, index=ops.index(cur) if cur in ops else 0)
                        mot = e2.text_input("Motivo (obligatorio para cancelaciones)")
                        if st.form_submit_button("Actualizar estado", type="primary"):
                            if nuevo == "Cancelado" and not (puede_val(col) and mot.strip()):
                                st.error("La cancelación requiere autorización del personal facultado y un motivo.")
                            else:
                                rec["d"]["estado"] = nuevo
                                if nuevo == "Finalizado":
                                    rec["fin"] = datetime.now().isoformat(timespec="seconds")
                                Repo.hist(rec, "Cambio de estado", f"{cur} → {nuevo}. {mot}")
                                ss.ver[col] += 1
                                ss.flash = f"Estado de {fol}: {nuevo}"
                                st.rerun()
                st.markdown("**Editar información**")
                formulario(col, "editar", rec)

    if "Validación" in tabs:
        with tabs["Validación"]:
            pend = [r for r in recs if r["val"] in (VAL_PEND, VAL_ENM)]
            st.markdown("##### Pendientes de revisión")
            if not pend:
                vacio("No hay registros pendientes de validación.")
            else:
                fol = st.selectbox("Registro", [r["folio"] for r in pend], key=f"vp_{col}", format_func=lambda x: etiqueta(col, Repo.buscar(col, x)))
                rec = Repo.buscar(col, fol)
                detalle(col, rec)
                ok = st.checkbox("Confirmo que revisé el registro y lo autorizo con mi firma electrónica interna.", key=f"ck_{col}_{fol}")
                c1, c2 = st.columns(2)
                if c1.button("Validar registro", key=f"vb_{col}_{fol}", type="primary", disabled=not ok, **STRETCH):
                    Repo.validar(col, rec)
                    ss.flash = f"{fol} validado."
                    st.rerun()
                com = c2.text_input("Comentario para devolver", key=f"cm_{col}_{fol}")
                if c2.button("Devolver para corrección", key=f"db_{col}_{fol}", **STRETCH):
                    if not com.strip():
                        st.error("Escriba el comentario de corrección.")
                    else:
                        rec["val"] = VAL_DEV
                        Repo.hist(rec, "Devuelto para corrección", com)
                        st.rerun()
            st.divider()
            st.markdown("##### Enmendar un registro ya validado (deja evidencia)")
            okr = [r for r in recs if r["val"] == VAL_OK]
            if okr:
                fol2 = st.selectbox("Registro validado", [r["folio"] for r in okr], key=f"en_{col}", format_func=lambda x: etiqueta(col, Repo.buscar(col, x)))
                formulario(col, "enmendar", Repo.buscar(col, fol2))
            else:
                st.caption("Sin registros validados.")

    if "Cancelaciones" in tabs:
        with tabs["Cancelaciones"]:
            st.info("Las cancelaciones se realizan desde **Actualizar → Nuevo estado = Cancelado**, con motivo, y quedan en la bitácora.")


# ───────────────────────────── Páginas ─────────────────────────────────────────
def saludo() -> str:
    hh = datetime.now().hour
    return "Buenos días" if hh < 12 else ("Buenas tardes" if hh < 19 else "Buenas noches")


def formulario_admision_box(box):
    ss = st.session_state
    pacientes = Repo.listar("pac")
    propietarios = Repo.listar("prop")
    espacios = ss.cat.get("boxes", [])
    tipos = opciones(next(f for f in COL["adm"]["campos"] if f["k"] == "tipo_ingreso"))
    areas = opciones(next(f for f in COL["adm"]["campos"] if f["k"] == "area"))
    estados = ss.cat.get("estados_atencion", [])
    if not tipos or not areas or not estados:
        st.error("Configure tipos de ingreso, áreas y estados de atención antes de registrar la admisión.")
        return

    paciente_modos = ["Paciente nuevo"] + (["Paciente registrado"] if pacientes else [])
    if ss.get("box_patient_mode") not in paciente_modos:
        ss.box_patient_mode = paciente_modos[0]
    modo_paciente = st.segmented_control(
        "Paciente", paciente_modos, key="box_patient_mode", label_visibility="visible"
    )

    modos_propietario = ["Propietario nuevo"] + (["Propietario registrado"] if propietarios else [])
    if modo_paciente == "Paciente nuevo":
        if ss.get("box_owner_mode") not in modos_propietario:
            ss.box_owner_mode = modos_propietario[0]
        modo_propietario = st.segmented_control(
            "Propietario", modos_propietario, key="box_owner_mode"
        )
    else:
        modo_propietario = None

    indice = espacios.index(box)
    form_key = f"admision_box_{indice}_{ss.ver['adm']}_{ss.ver['pac']}_{ss.ver['prop']}"
    with st.container(border=True):
        st.markdown(f"#### Nueva admisión · {h(box)}")
        with st.form(form_key):
            datos = {}
            propietario_existente = ""
            if modo_paciente == "Paciente nuevo":
                c1, c2 = st.columns(2)
                datos["nombre"] = c1.text_input("Nombre del caballo *")
                especies = ss.cat.get("especies", [])
                datos["especie"] = c2.selectbox("Especie *", especies) if especies else ""
                c1, c2 = st.columns(2)
                datos["raza"] = c1.text_input("Raza")
                sexos = [""] + ss.cat.get("sexos", [])
                datos["sexo"] = c2.selectbox("Sexo", sexos, format_func=lambda x: x or "—")

                if modo_propietario == "Propietario registrado":
                    propietarios_opciones = {
                        etiqueta("prop", r): r["folio"] for r in propietarios
                    }
                    propietario_etiqueta = st.selectbox(
                        "Propietario *",
                        list(propietarios_opciones),
                    )
                    propietario_existente = propietarios_opciones[propietario_etiqueta]
                else:
                    c1, c2 = st.columns(2)
                    datos["propietario_nombre"] = c1.text_input("Nombre del propietario *")
                    datos["propietario_telefono"] = c2.text_input("Teléfono del propietario")
                    datos["propietario_correo"] = st.text_input("Correo del propietario")
            elif modo_paciente == "Paciente registrado":
                pacientes_opciones = {etiqueta("pac", r): r["folio"] for r in pacientes}
                paciente_etiqueta = st.selectbox("Paciente *", list(pacientes_opciones))
                paciente_folio = pacientes_opciones[paciente_etiqueta]
            else:
                paciente_folio = ""

            c1, c2 = st.columns(2)
            tipo_ingreso = c1.selectbox("Tipo de ingreso *", tipos)
            area = c2.selectbox("Área solicitada *", areas)
            personal = [r["d"]["nombre"] for r in Repo.listar("staff") if r["d"].get("activo", True)]
            if personal:
                medico = st.selectbox("Médico asignado", [""] + personal, format_func=lambda x: x or "Sin asignar")
            else:
                medico = st.text_input("Médico asignado")
            motivo = st.text_area("Motivo de atención *", height=80)
            participantes = st.text_input("Participantes autorizados (separados por coma)")
            observaciones = st.text_area("Observaciones", height=60)
            estado_inicial = "En espera" if "En espera" in estados else estados[0]
            estado = st.selectbox(
                "Estado inicial", estados, index=estados.index(estado_inicial)
            )
            guardar = st.form_submit_button(
                "Registrar admisión y ocupar este espacio", type="primary"
            )

        if not guardar:
            return

        errores = []
        if modo_paciente == "Paciente nuevo":
            if not datos.get("nombre", "").strip():
                errores.append("nombre del caballo")
            if not datos.get("especie"):
                errores.append("especie")
            if modo_propietario == "Propietario registrado":
                if not propietario_existente:
                    errores.append("propietario")
            elif not datos.get("propietario_nombre", "").strip():
                errores.append("nombre del propietario")
        elif modo_paciente == "Paciente registrado":
            if not paciente_folio:
                errores.append("paciente")
        else:
            errores.append("tipo de paciente")
        if not tipo_ingreso or not area or not motivo.strip():
            errores.append("tipo de ingreso, área y motivo de atención")
        if box not in ss.cat.get("boxes", []):
            errores.append("espacio configurado")
        if errores:
            st.error("Complete los datos obligatorios: " + ", ".join(errores) + ".")
            return

        if modo_paciente == "Paciente nuevo":
            propietario_folio = propietario_existente
            if modo_propietario == "Propietario nuevo":
                propietario = Repo.crear("prop", dict(
                    nombre=datos["propietario_nombre"].strip(),
                    telefono=datos["propietario_telefono"].strip(),
                    correo=datos["propietario_correo"].strip(),
                    identificacion="", direccion="", obs="",
                ), [])
                propietario_folio = propietario["folio"]
            paciente = Repo.crear("pac", dict(
                nombre=datos["nombre"].strip(),
                especie=datos["especie"],
                raza=datos["raza"].strip(),
                sexo=datos["sexo"],
                edad="", peso=0.0, capa="", alzada=0.0, uso="", microchip="",
                propietario=propietario_folio, alergias="", antecedentes="",
            ), [])
            paciente_folio = paciente["folio"]
        elif not Repo.buscar("pac", paciente_folio):
            st.error("No se encontró el paciente seleccionado. Vuelva a elegirlo.")
            return

        admision = Repo.crear("adm", dict(
            paciente=paciente_folio, tipo_ingreso=tipo_ingreso, area=area,
            medico=medico.strip(), box=box, motivo=motivo.strip(),
            participantes=participantes.strip(), obs=observaciones.strip(), estado=estado,
        ), [])
        ss.ver["adm"] += 1
        if modo_paciente == "Paciente nuevo":
            ss.ver["pac"] += 1
            if modo_propietario == "Propietario nuevo":
                ss.ver["prop"] += 1
        ss.flash = f"Admisión {admision['folio']} registrada en {box}."
        ss.pop("box_preseleccionado", None)
        st.rerun()


def mapa_boxes(activos, nombres=True):
    """Mapa interactivo de espacios y ocupación actual."""
    boxes = st.session_state.cat.get("boxes", [])
    if not boxes:
        vacio("No hay boxes configurados. Agréguelos en Administración → Catálogos → Boxes y caballerizas.")
        return
    ocupado = {}
    for r in activos:
        b = r["d"].get("box")
        if b:
            ocupado.setdefault(b, []).append(r)

    ss = st.session_state
    seleccionado = ss.get("box_seleccionado")
    if seleccionado not in boxes:
        seleccionado = None
        ss.box_seleccionado = None

    st.caption("Pulsa un espacio para ver quién lo ocupa o, si está libre, registrar una admisión ahí mismo.")
    with st.container(key="box_map"):
        for inicio in range(0, len(boxes), 6):
            columnas = st.columns(6)
            for indice, box in enumerate(boxes[inicio:inicio + 6], start=inicio):
                admisiones = ocupado.get(box, [])
                if not admisiones:
                    estado, clase = "Disponible", "free"
                elif len(admisiones) > 1:
                    estado, clase = f"Conflicto: {len(admisiones)}", "conflict"
                elif admisiones[0]["d"].get("tipo_ingreso") == "Urgencia":
                    estado, clase = "Urgencia", "urgent"
                else:
                    estado, clase = "Ocupado", "occupied"

                if columnas[indice - inicio].button(
                    f"{box}\n{estado}",
                    key=f"box_pick_{clase}_{indice}",
                    type="primary" if box == seleccionado else "secondary",
                    **STRETCH,
                ):
                    ss.box_seleccionado = box
                    st.rerun()

    st.caption("Beige: disponible · Azul: ocupado · Rojo: urgencia · Ámbar: espacio con conflicto")
    if not seleccionado:
        return

    admisiones = ocupado.get(seleccionado, [])
    with st.container(border=True):
        encabezado, cerrar = st.columns([5, 1], vertical_alignment="center")
        encabezado.markdown(f"### {h(seleccionado)}")
        if cerrar.button("Cerrar", key="box_close", **STRETCH):
            ss.box_seleccionado = None
            st.rerun()

        if not admisiones:
            if puede_esc("adm") and puede_esc("pac") and puede_esc("prop"):
                formulario_admision_box(seleccionado)
            else:
                st.info("Este espacio está disponible. Su perfil no puede registrar pacientes y admisiones desde aquí.")
            return

        if len(admisiones) > 1:
            st.warning("Este espacio tiene más de una admisión activa. Revise los registros asignados.")
        if not nombres:
            st.info("Este espacio está ocupado.")
            return

        for admision in admisiones:
            paciente = Repo.buscar("pac", admision["d"].get("paciente", ""))
            nombre = paciente["d"].get("nombre", "") if paciente else "Paciente no disponible"
            st.markdown(
                f'<div class="card"><h4>{h(nombre)} <small style="color:#5E6A82">· {h(seleccionado)}</small></h4>'
                f'<span class="pill p-est">{h(admision["d"].get("estado", ""))}</span>'
                f'<span class="pill p-na">{h(admision["d"].get("tipo_ingreso", ""))}</span>'
                f'{h(admision["d"].get("area", ""))} · Médico: {h(admision["d"].get("medico") or "—")}<br>'
                f'<small>Folio: {h(admision["folio"])} · {h(admision["d"].get("motivo", ""))}</small></div>',
                unsafe_allow_html=True,
            )


def pagina_inicio():
    titulo("inicio", f"{saludo()}, {yo()} · {rol()}")
    adm = Repo.listar("adm")
    activos = [r for r in adm if r["d"].get("estado") != "Finalizado"]
    boxes = st.session_state.cat.get("boxes", [])
    usados = {r["d"].get("box") for r in activos if r["d"].get("box")}
    libres = len([b for b in boxes if b not in usados])
    c = st.columns(6)
    with c[0]: kpi(len(activos), "Equinos presentes")
    with c[1]: kpi(sum(r["d"].get("estado") == "En espera" for r in adm), "En espera", "gold")
    with c[2]: kpi(sum(r["d"].get("tipo_ingreso") == "Urgencia" for r in activos), "Urgencias activas", "red")
    with c[3]: kpi(libres, "Boxes disponibles")
    with c[4]: kpi(sum(r["d"].get("estado") not in ("Resultado disponible", "Validado") for r in Repo.listar("lab")), "Laboratorio pendiente", "blue")
    pend = sum(len([x for x in Repo.listar(k) if x["val"] in (VAL_PEND, VAL_ENM)]) for k in ROLES[rol()]["val"] if COL[k]["valida"])
    with c[5]: kpi(pend, "Por validar (mi perfil)", "gold")

    completo = "recepcion" in ROLES[rol()]["ver"] or rol() in (R_JEFE, R_ADMIN)
    st.markdown("#### Corrales, boxes y espacios de aislamiento")
    mapa_boxes(activos, nombres=completo)
    if not completo:
        st.caption("Su perfil ve la ocupación general sin datos de los pacientes.")

    st.markdown("#### Equinos presentes en el hospital")
    vistos = activos if completo else [r for r in activos if r["d"].get("paciente") in pacientes_visibles()]
    if not vistos:
        vacio("No hay equinos presentes. Registre una admisión en Recepción.")
    else:
        rows = []
        for r in vistos:
            mins = int((datetime.now() - datetime.fromisoformat(r["ts"])).total_seconds() / 60)
            p = Repo.buscar("pac", r["d"]["paciente"])
            rows.append({"Folio": r["folio"], "Paciente": etiqueta("pac", p, corto=True) if p else "", "Llegada": r["ts"][11:16], "Tipo": r["d"].get("tipo_ingreso"),
                         "Box": r["d"].get("box"), "Área": r["d"].get("area"), "Médico": r["d"].get("medico"), "Estado": r["d"].get("estado"), "Minutos en hospital": mins})
        tabla(pd.DataFrame(rows))

    st.markdown("#### Accesos")
    mods = [m for m in ROLES[rol()]["ver"] if m != "inicio"]
    with contenedor("accesos"):
        cols = st.columns(4)
        for i, m in enumerate(mods):
            nom = MODULOS[m]
            with cols[i % 4]:
                if st.button(nom, key=f"go_{m}", **STRETCH):
                    st.session_state.mod = m
                    st.rerun()


def pagina_recepcion():
    titulo("recepcion", "Registro de llegada, panel de presentes y seguimiento de estados")
    vista = st.radio("Vista", ["Presentes", "Admisiones"], horizontal=True, key="recepcion_vista")
    if vista == "Presentes":
        adm = [r for r in Repo.listar("adm") if r["d"].get("estado") != "Finalizado"]
        if not adm:
            vacio("Sin pacientes presentes.")
        for est in st.session_state.cat["estados_atencion"][:-1]:
            grupo = [r for r in adm if r["d"].get("estado") == est]
            if grupo:
                st.markdown(f"**{est}** · {len(grupo)}")
                for r in grupo:
                    p = Repo.buscar("pac", r["d"]["paciente"])
                    st.markdown(f'<div class="card"><h4>{h(etiqueta("pac", p, corto=True) if p else "")}</h4>'
                                f'<span class="pill p-est">{h(r["d"].get("tipo_ingreso", ""))}</span> {h(r["d"].get("area", ""))} · llegó {r["ts"][11:16]} · {h(r["folio"])}<br>'
                                f'<small>{h(r["d"].get("motivo", ""))}</small></div>', unsafe_allow_html=True)
    else:
        st.session_state.pop("box_preseleccionado", None)
        pagina_col("adm")


def pagina_triage():
    titulo("triage", "Valoración inicial de pacientes de urgencias. La clasificación definitiva es responsabilidad del personal veterinario autorizado.")
    st.caption("Las categorías de prioridad se configuran en Administración y deben ser aprobadas por el hospital.")
    pagina_col("triage")


def pagina_pacientes():
    titulo("pacientes", "Registro inicial de propietarios y pacientes")
    t = st.tabs(["Pacientes", "Propietarios"])
    with t[0]: pagina_col("pac")
    with t[1]: pagina_col("prop")


def pagina_expediente():
    titulo("expediente", "Recorrido completo del paciente por el hospital")
    ss = st.session_state
    pv = pacientes_visibles()
    pacs = [r for r in Repo.listar("pac") if r["folio"] in pv]
    if not pacs:
        vacio("No hay pacientes disponibles para su perfil." + (" Los estudiantes ven únicamente casos asignados (su nombre debe figurar como participante)." if rol() == R_EST else ""))
        return
    fol = st.selectbox("Paciente", [p["folio"] for p in pacs], format_func=lambda x: etiqueta("pac", Repo.buscar("pac", x)))
    p = Repo.buscar("pac", fol)
    d = p["d"]
    prop = Repo.buscar("prop", d.get("propietario", ""))
    dueno = "" if rol() == R_EST else f"<br>Propietario: {h(prop['d']['nombre'] if prop else '—')}"
    st.markdown(f'<div class="card"><h4>{h(d.get("nombre"))} <small style="color:#6B6558">· {h(d.get("especie"))} · {h(d.get("raza", ""))}</small></h4>'
                f'Sexo: {h(d.get("sexo") or "—")} · Edad: {h(d.get("edad") or "—")} · Peso inicial: {d.get("peso") or "—"} kg · Capa: {h(d.get("capa") or "—")} · Uso: {h(d.get("uso") or "—")}{dueno}<br>'
                f'<small>Alergias: {h(d.get("alergias") or "—")}</small></div>', unsafe_allow_html=True)
    t = st.tabs(["Línea de tiempo", "Nuevo registro clínico"])
    with t[0]:
        orden = ["adm", "triage", "clin", "inter", "lab", "img", "cir", "farm_disp"]
        ev = []
        for col in orden:
            for r in Repo.listar(col):
                rp = r["d"].get("paciente")
                if col == "farm_disp":
                    rc = Repo.buscar("clin", r["d"].get("receta", ""))
                    rp = rc["d"]["paciente"] if rc else None
                if rp == fol:
                    ev.append((r["ts"], col, r))
        if not ev:
            vacio("Este paciente aún no tiene registros en el recorrido hospitalario.")
        for ts, col, r in sorted(ev, key=lambda e: (e[0], e[2]["folio"]), reverse=True):
            area = r["d"].get("area") or r["d"].get("area_destino") or r["d"].get("area_resp") or r["d"].get("area_quir") or ""
            tipo = r["d"].get("tipo_registro") or COL[col]["t"]
            with st.expander(f"{ts.replace('T', ' ')[:16]} · {tipo} · {r['folio']}"):
                st.markdown(f'<div class="tl">Área: <b>{h(area or "—")}</b> · Responsable: <b>{h(r["por"])}</b> ({h(r["rol"])})'
                            f'{" · Participantes: " + h(r["d"].get("participantes")) if r["d"].get("participantes") else ""}</div>', unsafe_allow_html=True)
                detalle(col, r)
        if ev and rol() in EXPORTA:
            df = pd.DataFrame([dict(Fecha=t_.replace("T", " "), Registro=COL[c_]["t"], Folio=r_["folio"], Responsable=r_["por"], Validación=r_["val"]) for t_, c_, r_ in sorted(ev, key=lambda e: (e[0], e[2]["folio"]), reverse=True)])
            st.download_button("Exportar línea de tiempo (Excel)", excel_bytes({"Expediente": df}), file_name=f"expediente_{fol}.xlsx")
    with t[1]:
        if puede_esc("clin"):
            st.caption("Los diagnósticos definitivos, recetas y altas médicas solo pueden ser capturados por personal facultado para autorizarlos.")
            formulario("clin", "nuevo", defaults=dict(paciente=fol))
        else:
            st.info("Su perfil no puede capturar registros clínicos.")


def pagina_interconsultas():
    titulo("interconsultas", "Solicitud de valoración a especialistas, vinculada al expediente principal")
    pagina_col("inter")


def pagina_laboratorio():
    titulo("laboratorio", "Solicitudes, muestras, resultados y archivos PDF")
    pagina_col("lab")


def pagina_imagen():
    titulo("imagen", "Radiografías, ultrasonidos y otros estudios con comparación de estudios anteriores")
    pagina_col("img")


def pagina_cirugia():
    titulo("cirugia", "Registro quirúrgico y anestésico con verificación y autorización")
    pagina_col("cir")


def pagina_farmacia():
    titulo("farmacia", "Inventario, lotes, caducidades y dispensación vinculada a prescripciones")
    st.caption("Una prescripción no es una dispensación: aquí se registra lo efectivamente entregado o administrado.")
    meds = Repo.listar("farm_med")
    hoy = date.today()
    rows = []
    for m in meds:
        cad = _fecha(m["d"].get("caducidad"))
        dias = (cad - hoy).days if cad else None
        rows.append({"Lote": m["folio"], "Principio activo": m["d"]["principio"], "Concentración": m["d"].get("concentracion"), "Presentación": m["d"].get("presentacion"),
                     "Lote fabricante": m["d"]["lote"], "Caducidad": m["d"].get("caducidad"), "Existencia": stock_lote(m["folio"]),
                     "Alerta": "Caducado" if dias is not None and dias < 0 else ("Caduca en ≤ 60 días" if dias is not None and dias <= 60 else "")})
    c = st.columns(3)
    with c[0]: kpi(len(meds), "Lotes registrados")
    with c[1]: kpi(sum(1 for r in rows if r["Alerta"]), "Alertas de caducidad", "red")
    with c[2]: kpi(len([r for r in Repo.listar("clin") if FLT_RECETA(r)]) - len({d["d"]["receta"] for d in Repo.listar("farm_disp")}), "Recetas sin dispensación", "gold")
    t = st.tabs(["Existencias", "Lotes y medicamentos", "Movimientos", "Dispensaciones", "Proveedores"])
    with t[0]:
        if rows: tabla(pd.DataFrame(rows))
        else: vacio("Sin medicamentos registrados.")
    with t[1]: pagina_col("farm_med")
    with t[2]: pagina_col("farm_mov")
    with t[3]: pagina_col("farm_disp")
    with t[4]: pagina_col("farm_prov")


def pagina_academico():
    titulo("academico", "Participación académica supervisada. El expediente académico es independiente del expediente clínico.")
    t = st.tabs(["Participación", "Reportes anonimizados"])
    with t[0]: pagina_col("acad")
    with t[1]:
        recs = [r for r in visibles("acad")]
        if not recs:
            vacio("Sin actividades registradas.")
            return
        rows = []
        for r in recs:
            d = r["d"]
            hi, hf = _hora(d.get("h_ini")), _hora(d.get("h_fin"))
            horas = round(max(0, (datetime.combine(date.today(), hf) - datetime.combine(date.today(), hi)).total_seconds() / 3600), 2) if hi and hf else 0
            esp = [Repo.buscar("pac", x)["d"].get("especie", "") for x in d.get("casos", []) if Repo.buscar("pac", x)]
            rows.append(dict(Modalidad=d.get("modalidad"), Área=d.get("area"), Fecha=d.get("fecha"), Horas=horas, Casos=len(d.get("casos", [])), Especies=", ".join(sorted(set(esp))), Validación=r["val"]))
        df = pd.DataFrame(rows)
        st.caption("Reporte sin nombres de estudiantes, pacientes ni propietarios.")
        a, b = st.columns(2)
        a.bar_chart(df.groupby("Modalidad")["Horas"].sum(), color=TEAL)
        b.bar_chart(df.groupby("Área")["Casos"].sum(), color=AZUL)
        tabla(df)
        if rol() in EXPORTA | {R_PROF}:
            st.download_button("Exportar (Excel)", excel_bytes({"Actividad académica": df}), file_name="reporte_academico_anonimo.xlsx")


def _cuenta(prop_folio):
    cargos = [r for r in Repo.listar("cargo") if r["d"]["propietario"] == prop_folio and r["d"].get("estado") != "Cancelado"]
    abonos = [r for r in Repo.listar("abono") if r["d"]["propietario"] == prop_folio and r["d"].get("estado") != "Cancelado"]
    tc = sum(r["d"]["cantidad"] * r["d"]["precio"] for r in cargos)
    ta = sum(r["d"]["monto"] for r in abonos)
    return cargos, abonos, tc, ta


def pagina_finanzas():
    titulo("finanzas", "Cuentas de propietarios, cargos, abonos y comprobantes internos. Los precios los define el hospital.")
    t = st.tabs(["Cuentas", "Cargos", "Abonos", "Tarifario"])
    with t[0]:
        props = Repo.listar("prop")
        if not props:
            vacio("Registre propietarios para abrir cuentas.")
        else:
            fol = st.selectbox("Propietario", [p["folio"] for p in props], format_func=lambda x: etiqueta("prop", Repo.buscar("prop", x)))
            cargos, abonos, tc, ta = _cuenta(fol)
            c = st.columns(3)
            with c[0]: kpi(f"${tc:,.2f}", "Total cargos")
            with c[1]: kpi(f"${ta:,.2f}", "Total abonos", "blue")
            with c[2]: kpi(f"${tc - ta:,.2f}", "Saldo", "gold")
            rows = [dict(Fecha=r["ts"][:16].replace("T", " "), Concepto=r["d"]["concepto"], Cantidad=r["d"]["cantidad"], Precio=r["d"]["precio"], Importe=r["d"]["cantidad"] * r["d"]["precio"]) for r in cargos]
            rows += [dict(Fecha=r["ts"][:16].replace("T", " "), Concepto=f"Abono ({r['d']['metodo']})", Cantidad=1, Precio=-r["d"]["monto"], Importe=-r["d"]["monto"]) for r in abonos]
            if rows:
                df = pd.DataFrame(rows).sort_values("Fecha")
                tabla(df)
                prop = Repo.buscar("prop", fol)
                lineas = [f"Propietario: {prop['d']['nombre']}", f"Folio de cuenta: {fol}", f"Emitido: {datetime.now():%d/%m/%Y %H:%M} por {yo()}", ""]
                lineas += [f"{r['Fecha']}  {r['Concepto']}  x{r['Cantidad']}  ${r['Importe']:,.2f}" for r in rows]
                lineas += ["", f"Total cargos: ${tc:,.2f}", f"Total abonos: ${ta:,.2f}", f"SALDO: ${tc - ta:,.2f}", "", "COMPROBANTE INTERNO · No es un comprobante fiscal."]
                pdf = pdf_texto("Comprobante interno de cuenta", lineas)
                if pdf:
                    st.download_button("Descargar comprobante interno (PDF)", pdf, file_name=f"comprobante_{fol}.pdf")
                else:
                    st.download_button("Descargar comprobante interno (TXT)", "\n".join(lineas), file_name=f"comprobante_{fol}.txt")
            else:
                st.caption("Sin movimientos en la cuenta.")
    with t[1]: pagina_col("cargo")
    with t[2]: pagina_col("abono")
    with t[3]:
        if not Repo.listar("tarifa"):
            st.info("El tarifario está vacío. El personal autorizado debe capturar los precios oficiales del hospital.")
        pagina_col("tarifa")


# ───────────────────────────── Exportaciones ───────────────────────────────────
def excel_bytes(hojas: dict) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        for nombre, df in hojas.items():
            (df if len(df) else pd.DataFrame({"Sin datos": []})).to_excel(w, sheet_name=nombre[:31], index=False)
    return buf.getvalue()


def pdf_texto(titulo_, lineas):
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas
    except ImportError:
        return None
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    y = 750
    c.setFont("Helvetica-Bold", 14); c.drawString(50, y, "Hospital de Equinos · FES Cuautitlán | UNAM"); y -= 20
    c.setFont("Helvetica-Bold", 12); c.drawString(50, y, titulo_); y -= 26
    c.setFont("Helvetica", 9)
    for ln in lineas:
        if y < 60:
            c.showPage(); y = 750; c.setFont("Helvetica", 9)
        c.drawString(50, y, str(ln)[:110]); y -= 14
    c.save()
    return buf.getvalue()


# ───────────────────────────── Estadísticas ────────────────────────────────────
def construir_eventos() -> pd.DataFrame:
    sp = {r["folio"]: r["d"].get("especie", "") for r in Repo.listar("pac")}
    rows = []

    def add(col, r, area="", medico="", servicio="", tipo=""):
        pf = r["d"].get("paciente", "")
        mins = None
        if r.get("fin"):
            mins = (datetime.fromisoformat(r["fin"]) - datetime.fromisoformat(r["ts"])).total_seconds() / 60
        rows.append(dict(col=col, folio=r["folio"], fecha=date.fromisoformat(r["fecha"]), area=area or "", medico=medico or r["por"], servicio=servicio or "",
                         especie=sp.get(pf, ""), paciente=pf, tipo=tipo, minutos=mins))

    for r in Repo.listar("adm"): add("adm", r, r["d"].get("area"), r["d"].get("medico"), r["d"].get("tipo_ingreso"), r["d"].get("tipo_ingreso"))
    for r in Repo.listar("triage"): add("triage", r, r["d"].get("area_destino"))
    for r in Repo.listar("clin"): add("clin", r, r["d"].get("area"), tipo=r["d"].get("tipo_registro"), servicio=r["d"].get("tipo_registro"))
    for r in Repo.listar("inter"): add("inter", r, r["d"].get("area_destino"), r["d"].get("especialista"))
    for r in Repo.listar("lab"): add("lab", r, "Laboratorio clínico", r["d"].get("solicitante"), r["d"].get("tipo_estudio"))
    for r in Repo.listar("img"): add("img", r, r["d"].get("area_resp"), r["d"].get("solicitante"), r["d"].get("tipo_estudio"))
    for r in Repo.listar("cir"): add("cir", r, r["d"].get("area_quir"), r["d"].get("cirujano"), r["d"].get("tipo_cirugia"))
    for r in Repo.listar("farm_mov"): add("farm_mov", r, "Farmacia", servicio=r["d"].get("tipo"))
    for r in Repo.listar("farm_disp"): add("farm_disp", r, "Farmacia", servicio="Dispensación")
    for r in Repo.listar("acad"): add("acad", r, r["d"].get("area"), r["d"].get("supervisor"), r["d"].get("modalidad"))
    return pd.DataFrame(rows, columns=["col", "folio", "fecha", "area", "medico", "servicio", "especie", "paciente", "tipo", "minutos"])


def pagina_estadisticas():
    titulo("estadisticas", "Actividad hospitalaria con filtros y exportación")
    ev = construir_eventos()
    if ev.empty:
        vacio("Aún no hay actividad registrada para generar estadísticas.")
        return
    c = st.columns([1.4, 1, 1, 1, 1])
    hoy = date.today()
    rango = c[0].date_input("Periodo", value=(min(ev.fecha.min(), hoy - timedelta(days=30)), hoy), format="DD/MM/YYYY")
    area = c[1].multiselect("Área", sorted(x for x in ev.area.unique() if x))
    med = c[2].multiselect("Médico", sorted(x for x in ev.medico.unique() if x))
    srv = c[3].multiselect("Servicio", sorted(x for x in ev.servicio.unique() if x))
    esp = c[4].multiselect("Especie", sorted(x for x in ev.especie.unique() if x))
    if isinstance(rango, tuple) and len(rango) == 2:
        ev = ev[(ev.fecha >= rango[0]) & (ev.fecha <= rango[1])]
    if area: ev = ev[ev.area.isin(area)]
    if med: ev = ev[ev.medico.isin(med)]
    if srv: ev = ev[ev.servicio.isin(srv)]
    if esp: ev = ev[ev.especie.isin(esp)]

    adm, cl = ev[ev.col == "adm"], ev[(ev.col == "clin")]
    resumen = [
        ("Pacientes atendidos", adm.paciente.nunique()), ("Consultas", int((cl.tipo == "Consulta").sum())),
        ("Interconsultas", int((ev.col == "inter").sum())), ("Procedimientos quirúrgicos", int((ev.col == "cir").sum())),
        ("Estudios de laboratorio", int((ev.col == "lab").sum())), ("Estudios de imagenología", int((ev.col == "img").sum())),
        ("Ingresos hospitalarios", int((cl.tipo == "Hospitalización").sum())), ("Egresos / altas", int((cl.tipo == "Alta médica").sum())),
        ("Urgencias atendidas", int((adm.tipo == "Urgencia").sum())), ("Movimientos de farmacia", int(ev.col.isin(["farm_mov", "farm_disp"]).sum())),
        ("Actividades académicas", int((ev.col == "acad").sum())),
    ]
    mm = adm.minutos.dropna()
    resumen.append(("Tiempo promedio de atención (min)", round(mm.mean(), 1) if len(mm) else "—"))
    k = st.columns(4)
    for i, (l, v) in enumerate(resumen):
        with k[i % 4]:
            kpi(v, l, ["", "gold", "blue", "red"][i % 4])
            st.write("")
    t1 = adm.drop_duplicates("paciente").groupby("especie").size().rename("Pacientes").reset_index()
    t2 = cl[cl.tipo == "Consulta"].groupby("area").size().rename("Consultas").reset_index()
    t3 = cl[cl.tipo == "Consulta"].groupby("medico").size().rename("Consultas").reset_index()
    t4 = ev[ev.col.isin(["lab", "img", "cir"]) & (ev.servicio != "")].groupby("servicio").size().rename("Solicitudes").sort_values(ascending=False).reset_index()
    g = st.columns(2)
    with g[0]:
        st.markdown("**Pacientes por especie**")
        tabla(t1) if len(t1) else st.caption("Sin datos")
        st.markdown("**Consultas por área**")
        (st.bar_chart(t2.set_index("area"), color=TEAL) if len(t2) else st.caption("Sin datos"))
    with g[1]:
        st.markdown("**Consultas por médico**")
        (st.bar_chart(t3.set_index("medico"), color=AZUL) if len(t3) else st.caption("Sin datos"))
        st.markdown("**Servicios más solicitados**")
        tabla(t4) if len(t4) else st.caption("Sin datos")
    if rol() in EXPORTA:
        df_res = pd.DataFrame(resumen, columns=["Indicador", "Valor"]).astype({"Valor": str})
        e = st.columns(2)
        e[0].download_button("Exportar a Excel", excel_bytes({"Resumen": df_res, "Especies": t1, "Consultas por área": t2, "Consultas por médico": t3, "Servicios": t4, "Detalle": ev.drop(columns=["paciente"])}), file_name="estadisticas_hospital.xlsx", **STRETCH)
        pdf = pdf_texto("Estadísticas de actividad hospitalaria", [f"{a}: {b}" for a, b in resumen])
        if pdf:
            e[1].download_button("Exportar a PDF", pdf, file_name="estadisticas_hospital.pdf", **STRETCH)
    else:
        st.caption("La exportación está disponible para perfiles autorizados.")


# ───────────────────────────── Administración ──────────────────────────────────
def cargar_demo():
    """Datos FICTICIOS para revisar la interfaz. No representan información real."""
    ss = st.session_state
    ss.audit.append(dict(ts=datetime.now().isoformat(timespec="seconds"), por=yo(), rol=rol(), accion="Carga de datos ficticios de demostración", detalle="", folio="—"))
    st_ = [Repo.crear("staff", dict(nombre=f"Personal Demo {i + 1}", rol=r, areas=[], correo="", cedula="", horario="", activo=True), []) for i, r in enumerate([R_MVZ, R_ESP, R_PROF])]
    pr = [Repo.crear("prop", dict(nombre=f"Propietario Demo {c}", telefono="", correo="", identificacion="", direccion="", obs=""), []) for c in "ABC"]
    pa = [Repo.crear("pac", dict(nombre=f"Paciente Demo {i + 1}", especie=["Caballo", "Burro / asno"][i % 2], raza="", sexo="Sin determinar", edad="", peso=450.0 + 20 * i, capa="", alzada=0.0, uso="", microchip="", propietario=pr[i % 3]["folio"], alergias="", antecedentes=""), []) for i in range(4)]
    ests = ["En espera", "En consulta", "En estudios", "Finalizado"]
    for i, p in enumerate(pa):
        a = Repo.crear("adm", dict(paciente=p["folio"], tipo_ingreso=["Cita programada", "Urgencia"][i % 2], area=["Consultas generales", "Urgencias y cólico"][i % 2], medico="Personal Demo 1", box=f"Box {i + 1}", motivo="Motivo de atención (demo)", participantes="", obs="", estado=ests[i]), [])
        if ests[i] == "Finalizado":
            a["fin"] = (datetime.fromisoformat(a["ts"]) + timedelta(minutes=47)).isoformat(timespec="seconds")
    Repo.crear("triage", dict(paciente=pa[1]["folio"], hora="10:30", motivo="Urgencia (demo)", estado_general="", temp=38.9, fc=64.0, fr=28.0, peso=480.0, prioridad=ss.cat["prioridades"][1], area_destino="Urgencias y cólico", obs=""), [])
    Repo.crear("clin", dict(paciente=pa[0]["folio"], tipo_registro="Consulta", area="Consultas generales", participantes="", motivo="Revisión (demo)", hallazgos="Hallazgos de ejemplo.", diagnostico="", plan="", peso=470.0, temp=37.9, fc=38.0, fr=14.0), [], validado=True)
    Repo.crear("clin", dict(paciente=pa[0]["folio"], tipo_registro="Receta", area="Consultas generales", participantes="", motivo="", hallazgos="", diagnostico="", plan="Prescripción de ejemplo.", peso=0.0, temp=0.0, fc=0.0, fr=0.0), [], validado=True)
    Repo.crear("inter", dict(paciente=pa[0]["folio"], area_origen="Consultas generales", area_destino="Oftalmología", especialista="Personal Demo 2", motivo="Valoración (demo)", expediente=[], obs="", respuesta="", estado="Solicitada"), [])
    Repo.crear("lab", dict(paciente=pa[0]["folio"], solicitante="Personal Demo 1", consulta="", tipo_estudio="Biometría hemática", tipo_muestra="Sangre", fecha_toma="", resp_toma="", fecha_proc="", resultado="", obs="", estado="Muestra recibida"), [])
    Repo.crear("img", dict(paciente=pa[2]["folio"], solicitante="Personal Demo 1", motivo="Estudio (demo)", fecha=date.today().isoformat(), tipo_estudio="Radiografía", area_resp="Radiología", interpreta="", previo="", informe="", estado="Solicitado"), [])
    Repo.crear("cir", dict(paciente=pa[3]["folio"], cirujano="Personal Demo 1", equipo="", tipo_cirugia="Procedimiento de ejemplo", diagnostico="", fecha=date.today().isoformat(), hora="09:00", area_quir="Cirugía", preop="", anest_eval="", anestesiologo="", transop="", incidentes="", recuperacion="", postop="", verificacion=False, autorizacion=False, estado="Programada"), [])
    pv = Repo.crear("farm_prov", dict(nombre="Proveedor Demo", contacto="", telefono="", correo="", obs=""), [])
    m = Repo.crear("farm_med", dict(principio="Principio activo demo", comercial="", concentracion="10 mg", presentacion="Tabletas", lote="L-DEMO-1", caducidad=(date.today() + timedelta(days=40)).isoformat(), inicial=50, proveedor=pv["folio"], obs=""), [])
    Repo.crear("farm_mov", dict(lote=m["folio"], tipo="Entrada", cantidad=20, documento="", motivo="Demo"), [])
    rc = next(r for r in Repo.listar("clin") if r["d"]["tipo_registro"] == "Receta")
    Repo.crear("farm_disp", dict(receta=rc["folio"], lote=m["folio"], cantidad=5, resultado="Entregado al propietario", obs=""), [], validado=True)
    Repo.crear("tarifa", dict(categoria="Consultas", concepto="Servicio demo (precio ficticio)", precio=100.0, vigente=True), [])
    t = Repo.listar("tarifa")[-1]
    Repo.crear("cargo", dict(propietario=pr[0]["folio"], paciente=pa[0]["folio"], tarifa=t["folio"], concepto="Servicio demo (precio ficticio)", cantidad=1, precio=100.0, estado="Vigente"), [])
    Repo.crear("abono", dict(propietario=pr[0]["folio"], monto=40.0, metodo="Efectivo", referencia="", estado="Vigente"), [])
    Repo.crear("acad", dict(estudiante="Estudiante Demo", identificador="", programa="MVZ", modalidad="Rotaciones", area="Consultas generales", supervisor="Personal Demo 3", fecha=date.today().isoformat(), h_ini="08:00", h_fin="12:00", actividades="Actividades de ejemplo.", casos=[pa[0]["folio"]], obs=""), [])


def _admin_cuentas():
    ss = st.session_state
    st.caption("Cuentas con acceso al sistema. Un cambio de perfil se aplica la próxima vez que la persona inicie sesión.")
    usuarios = cargar_usuarios()
    if not usuarios:
        vacio("Aún no hay cuentas registradas.")
        return
    df = pd.DataFrame([dict(Correo=k, Nombre=v["nombre"], Perfil=v["rol"], Activa=bool(v.get("activo", True)),
                            Creada=v.get("creado", "")[:16].replace("T", " ")) for k, v in usuarios.items()])
    ed = st.data_editor(df, hide_index=True, key="ed_cuentas", disabled=["Correo", "Creada"], **STRETCH,
                        column_config={"Perfil": st.column_config.SelectboxColumn("Perfil", options=list(ROLES), required=True),
                                       "Activa": st.column_config.CheckboxColumn("Activa")})
    if st.button("Guardar cuentas", type="primary", key="save_cuentas"):
        filas = ed.to_dict("records")
        if not any(r["Perfil"] == R_ADMIN and r["Activa"] for r in filas):
            st.error("Debe quedar al menos un administrador activo.")
        else:
            for r in filas:
                usuarios[r["Correo"]].update(nombre=(r["Nombre"] or "").strip() or usuarios[r["Correo"]]["nombre"], rol=r["Perfil"], activo=bool(r["Activa"]))
            try:
                guardar_usuarios(usuarios)
                ss.flash = "Cuentas actualizadas."
                st.rerun()
            except OSError:
                st.error("No se pudo escribir usuarios.json. Revise los permisos de la carpeta de la aplicación.")
    with st.expander("Restablecer contraseña de una cuenta"):
        sel = st.selectbox("Cuenta", list(usuarios), key="rp_sel")
        nueva = st.text_input("Nueva contraseña temporal (mínimo 8 caracteres)", type="password", key="rp_pw")
        if st.button("Restablecer contraseña", key="rp_btn"):
            if len(nueva) < 8:
                st.error("La contraseña debe tener al menos 8 caracteres.")
            else:
                salt = secrets.token_hex(16)
                usuarios[sel].update(salt=salt, hash=_hash_pw(nueva, salt))
                try:
                    guardar_usuarios(usuarios)
                    st.success(f"Contraseña de {sel} restablecida. Compártala por un medio seguro.")
                except OSError:
                    st.error("No se pudo escribir usuarios.json.")


def pagina_admin():
    titulo("admin", "Configuración institucional, personal, catálogos y bitácora")
    ss = st.session_state
    t = st.tabs(["Áreas", "Personal", "Catálogos", "Identidad visual", "Bitácora", "Demostración", "Cuentas"])
    with t[0]:
        st.caption("Cada área se configura de forma independiente: personal, horario y disponibilidad no se presuponen.")
        ed = st.data_editor(pd.DataFrame(ss.areas), num_rows="dynamic", key="ed_areas", **STRETCH,
                            column_config={"Activa": st.column_config.CheckboxColumn("Activa")})
        if st.button("Guardar áreas", type="primary"):
            ss.areas = [dict(Área=r["Área"], Activa=bool(r["Activa"]), Responsable=r["Responsable"] or "", Horario=r["Horario"] or "", Personal=r["Personal"] or "", Notas=r["Notas"] or "")
                        for r in ed.to_dict("records") if r.get("Área")]
            ss.flash = "Áreas actualizadas."
            st.rerun()
    with t[1]:
        pagina_col("staff")
    with t[2]:
        st.caption("Las tarifas se capturan en Administración financiera → Tarifario.")
        k = st.selectbox("Catálogo", list(CAT_ETIQUETAS), format_func=CAT_ETIQUETAS.get)
        ed = st.data_editor(pd.DataFrame({"Valor": ss.cat[k]}), num_rows="dynamic", key=f"cat_{k}", **STRETCH)
        if st.button("Guardar catálogo", type="primary"):
            ss.cat[k] = [str(x).strip() for x in ed["Valor"].tolist() if x and str(x).strip()]
            ss.flash = f"Catálogo «{CAT_ETIQUETAS[k]}» actualizado."
            st.rerun()
    with t[3]:
        st.caption("El sistema usa el archivo assets/escudo_unam.png (o .svg) si existe; si no, muestra un emblema ilustrativo. Aquí puede cargar otro recurso autorizado solo para esta sesión.")
        up = st.file_uploader("Escudo / logotipo institucional autorizado", type=["png", "jpg", "jpeg", "svg"])
        if up and st.button("Usar este recurso gráfico", type="primary"):
            ss.logo = dict(bytes=up.getvalue(), mime=up.type or "image/png")
            st.rerun()
        if ss.logo and st.button("Quitar recurso gráfico"):
            ss.logo = None
            st.rerun()
    with t[4]:
        if ss.audit:
            df = pd.DataFrame(ss.audit).rename(columns=dict(ts="Fecha y hora", por="Usuario", rol="Rol", accion="Acción", detalle="Detalle", folio="Folio"))
            tabla(df.iloc[::-1])
            st.download_button("Exportar bitácora (Excel)", excel_bytes({"Bitácora": df}), file_name="bitacora.xlsx")
        else:
            vacio("La bitácora aún no tiene eventos.")
    with t[6]:
        _admin_cuentas()
    with t[5]:
        st.warning("Carga registros 100 % ficticios (Paciente Demo, Propietario Demo, etc.) únicamente para revisar el diseño. No usar con datos reales.")
        if st.button("Cargar datos ficticios de demostración"):
            cargar_demo()
            ss.flash = "Datos ficticios cargados."
            st.rerun()
        if st.button("Borrar todos los datos de esta sesión"):
            for k in ("db", "audit", "ver"):
                ss.pop(k, None)
            init_state(reset=True)
            st.rerun()


def medidor(nombre, val, ref, rango, unidad):
    lo, hi = ref
    a, b = rango
    pos = min(100.0, max(0.0, (val - a) / (b - a) * 100))
    zl, zw = (lo - a) / (b - a) * 100, (hi - lo) / (b - a) * 100
    if val < lo:
        est, cls = "Por debajo de la referencia", "p-dev"
    elif val > hi:
        est, cls = "Por arriba de la referencia", "p-dev"
    else:
        est, cls = "Dentro de la referencia", "p-ok"
    return html_min(f"""
    <div class="gauge"><div class="gt"><span>{h(nombre)}</span><span class="pill {cls}">{est}</span></div>
    <div class="gv">{val:g} <small style="font-size:.9rem;color:#6B7690">{h(unidad)}</small></div>
    <div class="track"><div class="zone" style="left:{zl:.1f}%;width:{zw:.1f}%"></div><div class="mk" style="left:{pos:.1f}%"></div></div>
    <div class="rf">Referencia general adulto en reposo: {lo:g} – {hi:g} {h(unidad)}</div></div>""")


def pagina_herramientas():
    titulo("herramientas", "Apoyos de consulta rápida. No sustituyen el criterio del médico veterinario.")
    t = st.tabs(["Peso con cinta", "Signos vitales"])
    with t[0]:
        st.caption("Estimación aproximada: perímetro torácico² × longitud corporal ÷ 11,880 (en cm). Confirme con báscula cuando sea posible, sobre todo para dosificar.")
        a, b = st.columns(2)
        pt = a.slider("Perímetro torácico (cm)", 80, 240, 180, help="Con la cinta alrededor del tórax, justo detrás de la cruz y los codos.")
        lg = b.slider("Longitud corporal (cm)", 80, 220, 150, help="De la punta del hombro a la punta de la nalga.")
        kg = pt * pt * lg / 11880
        st.markdown(html_min(f'<div class="weight"><div class="wn">{kg:,.0f} kg</div><div class="wl">Peso estimado · {kg * 2.2046:,.0f} lb</div></div>'), unsafe_allow_html=True)
    with t[1]:
        st.caption("Valores de referencia generales para caballos adultos en reposo. En potros, con ejercicio, dolor o calor ambiental cambian; el hospital debe definir sus propios rangos.")
        c = st.columns(3)
        tc = c[0].number_input("Temperatura (°C)", 30.0, 45.0, 37.8, 0.1)
        fc = c[1].number_input("Frecuencia cardiaca (lpm)", 10, 200, 36, 1)
        fr = c[2].number_input("Frecuencia respiratoria (rpm)", 2, 100, 12, 1)
        g = st.columns(3)
        g[0].markdown(medidor("Temperatura", float(tc), (37.2, 38.3), (35.0, 42.0), "°C"), unsafe_allow_html=True)
        g[1].markdown(medidor("Frecuencia cardiaca", float(fc), (28, 44), (10, 120), "lpm"), unsafe_allow_html=True)
        g[2].markdown(medidor("Frecuencia respiratoria", float(fr), (8, 16), (2, 60), "rpm"), unsafe_allow_html=True)


PAGINAS = dict(inicio=pagina_inicio, recepcion=pagina_recepcion, triage=pagina_triage, pacientes=pagina_pacientes, expediente=pagina_expediente,
               interconsultas=pagina_interconsultas, laboratorio=pagina_laboratorio, imagen=pagina_imagen, cirugia=pagina_cirugia,
               farmacia=pagina_farmacia, academico=pagina_academico, finanzas=pagina_finanzas, estadisticas=pagina_estadisticas, admin=pagina_admin, herramientas=pagina_herramientas)


# ───────────────────────────── Cuentas y autenticación ─────────────────────────
# Las cuentas se guardan en usuarios.json (junto a app.py) con contraseñas protegidas
# mediante PBKDF2-SHA256 y sal aleatoria. Nunca se guarda la contraseña en claro.
USERS_FILE = BASE_DIR / "usuarios.json"
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def cargar_usuarios() -> dict:
    try:
        return json.loads(USERS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def guardar_usuarios(u: dict) -> None:
    tmp = USERS_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(u, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, USERS_FILE)


def _hash_pw(pw: str, salt_hex: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", pw.encode("utf-8"), bytes.fromhex(salt_hex), 200_000).hex()


def registrar_usuario(nombre: str, correo: str, pw: str, perfil: str):
    """Devuelve None si se creó la cuenta, o un texto con el motivo del error."""
    correo = correo.strip().lower()
    usuarios = cargar_usuarios()
    if correo in usuarios:
        return "Ya existe una cuenta con ese correo. Use la pestaña «Iniciar sesión»."
    salt = secrets.token_hex(16)
    usuarios[correo] = dict(nombre=nombre.strip(), rol=R_ADMIN if not usuarios else perfil, salt=salt, hash=_hash_pw(pw, salt),
                            activo=True, creado=datetime.now().isoformat(timespec="seconds"))
    try:
        guardar_usuarios(usuarios)
    except OSError:
        return "No se pudo guardar la cuenta: la carpeta de la aplicación no permite escribir usuarios.json."
    return None


def verificar_usuario(correo: str, pw: str):
    u = cargar_usuarios().get(correo.strip().lower())
    if not u:
        _hash_pw(pw, "00" * 16)  # tiempo de respuesta similar si la cuenta no existe
        return None
    return u if hmac.compare_digest(_hash_pw(pw, u["salt"]), u["hash"]) else None


def iniciar_sesion(correo: str, u: dict):
    ss = st.session_state
    perfil = u["rol"] if u["rol"] in ROLES else R_EST
    ss.auth, ss.user_name, ss.rol, ss.rol_real = correo, u["nombre"], perfil, perfil
    ss.mod, ss.bienvenida = "inicio", True


def cerrar_sesion():
    ss = st.session_state
    ss.auth, ss.user_name, ss.mod = None, "", "inicio"
    st.rerun()


def fuerza_pw(pw: str):
    pts = sum([len(pw) >= 8, len(pw) >= 12, any(c.islower() for c in pw) and any(c.isupper() for c in pw),
               any(c.isdigit() for c in pw), any(not c.isalnum() for c in pw)])
    niveles = [("Muy débil", "#B5473E"), ("Débil", "#D1773B"), ("Aceptable", "#C9A24B"), ("Buena", "#5E9F6A"), ("Muy buena", "#2F7F70"), ("Excelente", "#1F6F5E")]
    etq, color = niveles[pts]
    return pts, etq, color


# ───────────────────────────── Pantalla de acceso ──────────────────────────────
def escena_html() -> str:
    pos = [(8, 10, .4), (22, 22, 1.2), (35, 8, 2.1), (48, 28, .9), (60, 12, 2.8), (72, 30, 1.6), (85, 9, .2), (92, 24, 2.4), (14, 38, 3.1), (41, 44, 1.9), (66, 46, .6), (80, 40, 2.9)]
    estrellas = "".join(f'<i style="left:{x}%;top:{y}%;animation-delay:-{d}s"></i>' for x, y, d in pos)
    return html_min(f"""
    <div class="scene"><div class="stars">{estrellas}</div>
      <div class="copy"><div class="crest">{escudo_html()}</div>
        <div class="uni">UNIVERSIDAD NACIONAL AUTÓNOMA DE MÉXICO</div>
        <h1>Hospital de Equinos</h1>
        <p>{h(HOSPITAL_SEDE)} · Un expediente completo para cada caballo, del ingreso al alta.</p></div>
      <div class="art"><div class="sun"></div>{HORSE_SVG}</div>
      <div class="hills far"></div><div class="hills near"></div>
      <div class="foot">Prototipo de interfaz · No es un sistema oficialmente aprobado por la UNAM.</div></div>""")


def _form_login():
    ss = st.session_state
    with st.form("f_login", clear_on_submit=False):
        correo = st.text_input("Correo electrónico", placeholder="nombre@correo.com", key="lg_mail")
        pw = st.text_input("Contraseña", type="password", key="lg_pw")
        ok = st.form_submit_button("Entrar al hospital", type="primary")
    st.caption("¿Aún no tiene cuenta? Abra la pestaña «Crear cuenta».")
    if not ok:
        return
    ahora = _time.time()
    if ahora < ss.bloqueo_hasta:
        st.error(f"Demasiados intentos fallidos. Espere {int(ss.bloqueo_hasta - ahora) + 1} segundos e intente de nuevo.")
        return
    if not correo.strip() or not pw:
        st.error("Escriba su correo y su contraseña.")
        return
    u = verificar_usuario(correo, pw)
    if not u:
        ss.fallos += 1
        if ss.fallos >= 5:
            ss.fallos, ss.bloqueo_hasta = 0, ahora + 30
        st.error("Correo o contraseña incorrectos. Revise los datos o cree una cuenta.")
        return
    if not u.get("activo", True):
        st.error("Su cuenta está desactivada. Comuníquese con el administrador del sistema.")
        return
    ss.fallos = 0
    iniciar_sesion(correo.strip().lower(), u)
    st.rerun()


def _form_registro():
    primero = not cargar_usuarios()
    if primero:
        st.info("Todavía no hay cuentas: la primera persona que se registre quedará como **Administrador del sistema**.")
    nombre = st.text_input("Nombre completo", key="rg_nom", placeholder="Nombre y apellidos")
    correo = st.text_input("Correo electrónico", key="rg_mail", placeholder="nombre@correo.com")
    if primero:
        perfil = R_ADMIN
    else:
        perfil = st.selectbox("Perfil de trabajo", [r for r in ROLES if r != R_ADMIN], key="rg_rol",
                              help="Define qué módulos verá. El administrador puede cambiarlo después.")
    c1, c2 = st.columns(2)
    pw = c1.text_input("Contraseña", type="password", key="rg_pw", help="Mínimo 8 caracteres. Mezcle mayúsculas, números y símbolos.")
    pw2 = c2.text_input("Confirmar contraseña", type="password", key="rg_pw2")
    if pw:
        pts, etq, color = fuerza_pw(pw)
        st.markdown(f'<div class="meter"><i style="width:{max(8, pts * 20)}%;background:{color}"></i></div><div class="meter-l">Seguridad: {etq}</div>', unsafe_allow_html=True)
    acepto = st.checkbox("Me comprometo a resguardar la confidencialidad de la información clínica y de los propietarios.", key="rg_ok")
    if not st.button("Crear mi cuenta", type="primary", key="rg_btn"):
        return
    errores = []
    if len(nombre.split()) < 2:
        errores.append("Escriba su nombre y apellido.")
    if not EMAIL_RE.match(correo.strip()):
        errores.append("Escriba un correo electrónico válido.")
    if len(pw) < 8:
        errores.append("La contraseña debe tener al menos 8 caracteres.")
    elif pw != pw2:
        errores.append("Las contraseñas no coinciden.")
    if not acepto:
        errores.append("Debe aceptar el compromiso de confidencialidad.")
    if errores:
        st.error("  \n".join(errores))
        return
    err = registrar_usuario(nombre, correo, pw, perfil)
    if err:
        st.error(err)
        return
    iniciar_sesion(correo.strip().lower(), verificar_usuario(correo, pw))
    st.rerun()


def pantalla_acceso():
    st.markdown(LOGIN_CSS, unsafe_allow_html=True)
    izq, der = st.columns([1.35, 1], gap="small")
    with izq:
        st.markdown(escena_html(), unsafe_allow_html=True)
    with der:
        with contenedor("acceso"):
            st.markdown(html_min("""<div class="a-head"><h2>Bienvenido(a)</h2>
                <p>Inicie sesión para entrar al hospital o cree su cuenta si es la primera vez.</p></div>"""), unsafe_allow_html=True)
            t1, t2 = st.tabs(["Iniciar sesión", "Crear cuenta"])
            with t1:
                _form_login()
            with t2:
                _form_registro()
            st.markdown('<div class="a-note">Las cuentas se guardan en este equipo con la contraseña cifrada.</div>', unsafe_allow_html=True)


# ───────────────────────────── Estado y arranque ───────────────────────────────
def init_state(reset=False):
    ss = st.session_state
    if "db" not in ss:
        ss.db = {k: [] for k in COL}
        ss.audit, ss.ver = [], defaultdict(int)
    if "cat" not in ss:
        ss.cat = copy.deepcopy(DEFAULT_CATALOGS)
    if "areas" not in ss:
        ss.areas = [dict(Área=a, Activa=True, Responsable="", Horario="", Personal="", Notas="") for a in AREAS_BASE]
    for k, v in (("logo", None), ("flash", None), ("mod", "inicio"), ("rol", R_ADMIN), ("user_name", ""),
                 ("auth", None), ("rol_real", R_ADMIN), ("fallos", 0), ("bloqueo_hasta", 0.0), ("bienvenida", False)):
        if k not in ss:
            ss[k] = v


def sidebar():
    ss = st.session_state
    with st.sidebar:
        st.markdown(html_min(f"""<div class="sb-brand"><div class="sb-crest">{escudo_html()}</div><div>
            <div class="sb-t">Hospital de Equinos</div><div class="sb-s">{h(HOSPITAL_SEDE)}</div></div></div>"""), unsafe_allow_html=True)
        ini = "".join(p[0] for p in yo().split()[:2]).upper() or "?"
        st.markdown(html_min(f"""<div class="ucard"><div class="av">{h(ini)}</div><div><b>{h(yo())}</b><br><span>{h(ss.rol_real)}</span></div></div>"""),
                    unsafe_allow_html=True)
        if ss.rol_real == R_ADMIN:
            with st.expander("Probar la interfaz de otro perfil"):
                nuevo = st.selectbox("Perfil", list(ROLES), index=list(ROLES).index(ss.rol), key="vista_rol")
                if nuevo != ss.rol:
                    ss.rol, ss.mod = nuevo, "inicio"
                    st.rerun()
                st.caption("Solo cambia lo que usted ve para revisar el diseño; su cuenta sigue siendo de administrador.")
        st.markdown("---")
        for m in ROLES[ss.rol]["ver"]:
            nom = MODULOS[m]
            if st.button(nom, key=f"nav_{m}", type="primary" if ss.mod == m else "secondary", **STRETCH):
                ss.mod = m
                st.rerun()
        st.markdown("---")
        if st.button("Cerrar sesión", key="logout", **STRETCH):
            cerrar_sesion()
        st.caption("Prototipo de interfaz. No constituye un sistema oficialmente aprobado, certificado o implementado por la UNAM.")


def main():
    init_state()
    ss = st.session_state
    if not ss.auth:
        pantalla_acceso()
        return
    st.markdown(CSS, unsafe_allow_html=True)
    sidebar()
    hero()
    if ss.bienvenida:
        ss.bienvenida = False
        try:
            st.toast(f"¡Bienvenido(a), {yo().split()[0]}!")
        except Exception:
            pass
    if ss.flash:
        st.success(ss.flash)
        ss.flash = None
    if ss.mod not in ROLES[ss.rol]["ver"]:
        ss.mod = "inicio"
    PAGINAS[ss.mod]()
    st.markdown('<div class="disc">Sistema Integral de Gestión Hospitalaria Veterinaria · Hospital de Equinos · Uso interno · Todos los datos mostrados deben ser capturados o configurados por el hospital.</div>', unsafe_allow_html=True)


main()
