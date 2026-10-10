"""
Bankrup By Jamuna — Enterprise Land Document Intelligence & GIS Platform
Pipeline: 
1) Fast Local Path: Tesseract OCR -> Strict DB Match
2) Smart Fallback Path: Deep AI Vision (Gemini) -> DB Match (Triggers ONLY when Local OCR fails)
"""

from __future__ import annotations

import importlib.util
import json
import re
import shutil
from pathlib import Path

import google.generativeai as genai
import pandas as pd
import pydeck as pdk
import streamlit as st
from PIL import Image

# Page config
st.set_page_config(
    page_title="Bankrup By Jamuna",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Safe Gemini API Key loading from Streamlit Secrets or Environment
GEMINI_API_KEY = ""
try:
    if "GEMINI_API_KEY" in st.secrets:
        GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
except Exception:
    pass

if not GEMINI_API_KEY:
    import os
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)


# ══════════════════════════════════════════════════════════════════════════════
# UI LAYER — design tokens, CSS, icons and small HTML helpers (presentation only)
# ══════════════════════════════════════════════════════════════════════════════
def get_css(is_dark: bool) -> str:
    """Design tokens per theme + one shared stylesheet that consumes them."""
    if is_dark:
        t = {
            "bg": "#0f1319",
            "sidebar": "#0b0f14",
            "surface": "#151b23",
            "surface-2": "#1b222c",
            "border": "rgba(255,255,255,0.08)",
            "border-strong": "rgba(255,255,255,0.16)",
            "text": "#e6e9ee",
            "muted": "#9099a8",
            "accent": "#2dd4bf",
            "accent-solid": "#0f766e",
            "accent-soft": "rgba(45,212,191,0.12)",
            "blue": "#60a5fa",
            "ok": "#34d399",
            "warn": "#fbbf24",
            "err": "#f87171",
            "info": "#38bdf8",
            "shadow": "0 1px 2px rgba(0,0,0,0.45)",
            "hero": "linear-gradient(135deg,#141b24 0%,#0f2429 55%,#101f38 100%)",
        }
    else:
        t = {
            "bg": "#f5f7fa",
            "sidebar": "#eef1f5",
            "surface": "#ffffff",
            "surface-2": "#f1f4f8",
            "border": "rgba(15,23,42,0.10)",
            "border-strong": "rgba(15,23,42,0.20)",
            "text": "#0f172a",
            "muted": "#5b6678",
            "accent": "#0f766e",
            "accent-solid": "#0f766e",
            "accent-soft": "rgba(15,118,110,0.10)",
            "blue": "#1d4ed8",
            "ok": "#047857",
            "warn": "#b45309",
            "err": "#b91c1c",
            "info": "#0369a1",
            "shadow": "0 1px 2px rgba(16,24,40,0.06)",
            "hero": "linear-gradient(135deg,#ffffff 0%,#ecf6f6 55%,#e8f0fb 100%)",
        }
    tokens = "".join(f"--bj-{k}:{v};" for k, v in t.items())
    return "<style>:root{" + tokens + "}" + STATIC_CSS + "</style>"


STATIC_CSS = """
/* Base ---------------------------------------------------------------------- */
.stApp{background:var(--bj-bg); color:var(--bj-text);
  font-family:"Inter","Segoe UI",system-ui,-apple-system,"Noto Sans Bengali","Hind Siliguri",sans-serif;}
header[data-testid="stHeader"]{background:transparent;}
#MainMenu, footer{visibility:hidden;}
[data-testid="stElementContainer"]:has(style){display:none;}
.block-container{padding-top:1.5rem; padding-bottom:3rem; max-width:1420px;}
h1,h2,h3{letter-spacing:-0.02em; color:var(--bj-text); font-weight:700;}
[data-testid="stHorizontalBlock"]{flex-wrap:wrap;}
[data-testid="stColumn"]{min-width:min(100%,230px);}
:focus-visible{outline:2px solid var(--bj-accent) !important; outline-offset:2px;}
@media (prefers-reduced-motion: reduce){*{transition:none !important; animation:none !important;}}

/* Native text colours so both themes stay readable -------------------------- */
[data-testid="stWidgetLabel"] p, [data-testid="stWidgetLabel"] label{color:var(--bj-text);}
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] *{color:var(--bj-muted);}
[data-testid="stMarkdownContainer"] code{
  background:var(--bj-surface-2); color:var(--bj-accent); border-radius:6px; padding:.1rem .4rem; font-size:.82em;}
[data-testid="stAlert"]{border-radius:12px;}
[data-testid="stAlert"] p{color:var(--bj-text);}
[data-testid="stSpinner"] *{color:var(--bj-muted);}

/* Hero ---------------------------------------------------------------------- */
.bj-hero{
  position:relative; overflow:hidden; border-radius:16px; padding:1.5rem 1.8rem; margin-bottom:1.2rem;
  background:var(--bj-hero); border:1px solid var(--bj-border); box-shadow:var(--bj-shadow);
}
.bj-hero::before{
  content:""; position:absolute; left:0; right:0; top:0; height:2px;
  background:linear-gradient(90deg,var(--bj-accent),var(--bj-blue),transparent 85%);
}
.bj-eyebrow{font-size:.72rem; font-weight:700; letter-spacing:.14em; text-transform:uppercase; color:var(--bj-accent);}
.bj-hero h1{margin:.25rem 0 .3rem 0; padding:0; font-size:2rem; font-weight:800; letter-spacing:-0.03em; line-height:1.15;}
.bj-hero h1 span{background:linear-gradient(90deg,var(--bj-accent),var(--bj-blue)); -webkit-background-clip:text;
  background-clip:text; -webkit-text-fill-color:transparent;}
.bj-hero p{margin:0; max-width:720px; font-size:.97rem; line-height:1.55; color:var(--bj-muted);}
.bj-chips{display:flex; flex-wrap:wrap; gap:.45rem; margin-top:1rem;}
.bj-chip{
  display:inline-flex; align-items:center; gap:.4rem; padding:.28rem .7rem; border-radius:999px;
  font-size:.75rem; font-weight:600; color:var(--bj-text); background:var(--bj-surface); border:1px solid var(--bj-border);
}
.bj-chip svg{color:var(--bj-accent);}

/* Cards --------------------------------------------------------------------- */
div[class*="st-key-card-"]{
  border:1px solid var(--bj-border); border-radius:14px; padding:1.25rem 1.4rem 1.3rem 1.4rem;
  background:var(--bj-surface); box-shadow:var(--bj-shadow); transition:border-color .18s ease;
}
div[class*="st-key-card-"]:hover{border-color:var(--bj-border-strong);}
.bj-sec{display:flex; align-items:center; gap:.8rem; margin-bottom:1rem; flex-wrap:wrap;}
.bj-step{
  flex:0 0 auto; width:28px; height:28px; border-radius:8px; display:grid; place-items:center;
  font-weight:700; font-size:.82rem; color:var(--bj-accent);
  background:var(--bj-accent-soft); border:1px solid color-mix(in srgb,var(--bj-accent) 35%,transparent);
}
.bj-sec-title{font-size:1.05rem; font-weight:700; line-height:1.25; color:var(--bj-text);}
.bj-sec-sub{font-size:.8rem; color:var(--bj-muted); margin-top:.1rem;}
.bj-sec-right{margin-left:auto;}

/* Badges -------------------------------------------------------------------- */
.bj-badge{
  display:inline-flex; align-items:center; gap:.38rem; padding:.18rem .62rem; border-radius:999px;
  font-size:.71rem; font-weight:700; border:1px solid transparent; white-space:nowrap;
}
.bj-badge i{width:6px; height:6px; border-radius:50%; background:currentColor; display:inline-block;}
.bj-success{color:var(--bj-ok);   background:color-mix(in srgb,var(--bj-ok) 13%,transparent);   border-color:color-mix(in srgb,var(--bj-ok) 30%,transparent);}
.bj-warn   {color:var(--bj-warn); background:color-mix(in srgb,var(--bj-warn) 13%,transparent); border-color:color-mix(in srgb,var(--bj-warn) 30%,transparent);}
.bj-error  {color:var(--bj-err);  background:color-mix(in srgb,var(--bj-err) 13%,transparent);  border-color:color-mix(in srgb,var(--bj-err) 30%,transparent);}
.bj-info   {color:var(--bj-info); background:color-mix(in srgb,var(--bj-info) 13%,transparent); border-color:color-mix(in srgb,var(--bj-info) 30%,transparent);}
.bj-neutral{color:var(--bj-muted); background:var(--bj-surface-2); border-color:var(--bj-border);}
.bj-row{display:flex; flex-wrap:wrap; gap:.4rem; margin:.55rem 0 .85rem 0;}

/* KPI tiles ----------------------------------------------------------------- */
.bj-kpi{
  display:flex; justify-content:space-between; align-items:flex-start; gap:.75rem; min-height:98px;
  border:1px solid var(--bj-border); border-radius:12px; padding:.9rem 1.05rem; background:var(--bj-surface);
  box-shadow:var(--bj-shadow); border-top:2px solid var(--bj-accent);
}
.bj-kpi-label{font-size:.7rem; font-weight:700; letter-spacing:.08em; text-transform:uppercase; color:var(--bj-muted);}
.bj-kpi-value{font-size:1.3rem; font-weight:800; line-height:1.25; margin-top:.2rem; color:var(--bj-text); overflow-wrap:anywhere;}
.bj-kpi-value.ok{color:var(--bj-ok);} .bj-kpi-value.err{color:var(--bj-err);} .bj-kpi-value.muted{color:var(--bj-muted);}
.bj-kpi-hint{font-size:.74rem; color:var(--bj-muted); margin-top:.1rem;}
.bj-kpi-icon{
  flex:0 0 auto; width:32px; height:32px; border-radius:9px; display:grid; place-items:center;
  color:var(--bj-accent); background:var(--bj-accent-soft);
}

/* Field tiles + key/value panel --------------------------------------------- */
.bj-grid{display:grid; grid-template-columns:repeat(auto-fit,minmax(190px,1fr)); gap:.65rem; margin:.5rem 0 .4rem 0;}
.bj-tile{border:1px solid var(--bj-border); border-radius:10px; padding:.7rem .9rem; background:var(--bj-surface-2); min-width:0;}
.bj-tile-label{font-size:.68rem; font-weight:700; letter-spacing:.08em; text-transform:uppercase; color:var(--bj-muted);}
.bj-tile-value{font-size:.98rem; font-weight:650; margin-top:.2rem; color:var(--bj-text);
  overflow-wrap:anywhere; user-select:all; font-variant-numeric:tabular-nums;}
.bj-tile.missing{border-style:dashed; background:transparent;}
.bj-tile.missing .bj-tile-value{color:var(--bj-muted); font-weight:500; user-select:none;}
.bj-kv{border:1px solid var(--bj-border); border-radius:12px; background:var(--bj-surface-2); padding:.2rem .95rem; margin-bottom:.8rem;}
.bj-kv-row{display:flex; justify-content:space-between; align-items:baseline; gap:1rem; padding:.55rem 0; border-bottom:1px solid var(--bj-border);}
.bj-kv-row:last-child{border-bottom:none;}
.bj-kv-k{font-size:.7rem; font-weight:700; letter-spacing:.07em; text-transform:uppercase; color:var(--bj-muted); flex:0 0 auto;}
.bj-kv-v{font-size:.92rem; font-weight:600; color:var(--bj-text); text-align:right; overflow-wrap:anywhere; user-select:all;}
.bj-kv-v.mono{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace; font-size:.86rem;}

/* Empty state --------------------------------------------------------------- */
.bj-empty{text-align:center; padding:2rem 1rem; border:1.5px dashed var(--bj-border-strong); border-radius:12px; color:var(--bj-muted);}
.bj-empty b{display:block; font-size:.97rem; color:var(--bj-text); margin:.5rem 0 .15rem 0;}
.bj-empty .ico{width:44px; height:44px; margin:0 auto; border-radius:12px; display:grid; place-items:center;
  color:var(--bj-accent); background:var(--bj-accent-soft);}

/* Sidebar ------------------------------------------------------------------- */
section[data-testid="stSidebar"]{background:var(--bj-sidebar); border-right:1px solid var(--bj-border);}
[data-testid="stSidebarContent"]{background:transparent;}
.bj-brand{display:flex; align-items:center; gap:.7rem; padding:.2rem 0 1rem 0; border-bottom:1px solid var(--bj-border); margin-bottom:.4rem;}
.bj-brand svg{flex:0 0 auto;}
.bj-brand-name{font-weight:800; font-size:1.05rem; line-height:1.15; letter-spacing:-0.02em; color:var(--bj-text);}
.bj-brand-name span{color:var(--bj-accent);}
.bj-brand-sub{font-size:.72rem; color:var(--bj-muted); font-weight:500; margin-top:.1rem;}
.bj-side-label{font-size:.66rem; font-weight:700; letter-spacing:.12em; text-transform:uppercase; color:var(--bj-muted); margin:1.1rem 0 .45rem 0;}
.bj-status{display:flex; align-items:center; justify-content:space-between; gap:.6rem; padding:.45rem 0;
  font-size:.84rem; color:var(--bj-text); border-bottom:1px solid var(--bj-border);}
.bj-status:last-child{border-bottom:none;}

/* Controls ------------------------------------------------------------------ */
div[data-testid="stRadio"] div[role="radiogroup"]{gap:.35rem;}
div[data-testid="stRadio"] label[data-baseweb="radio"]{
  margin:0; padding:.28rem .7rem; border:1px solid var(--bj-border); border-radius:8px;
  background:var(--bj-surface); transition:border-color .15s ease, background .15s ease;
}
div[data-testid="stRadio"] label[data-baseweb="radio"]:hover{border-color:var(--bj-border-strong);}
div[data-testid="stRadio"] label[data-baseweb="radio"] p{color:var(--bj-muted); font-size:.84rem; font-weight:600;}
div[data-testid="stRadio"] label[data-baseweb="radio"]:has(input:checked){
  background:var(--bj-accent-soft); border-color:color-mix(in srgb,var(--bj-accent) 50%,transparent);}
div[data-testid="stRadio"] label[data-baseweb="radio"]:has(input:checked) p{color:var(--bj-accent);}

[data-baseweb="select"] > div{background:var(--bj-surface); border:1px solid var(--bj-border); border-radius:10px; color:var(--bj-text);}
[data-baseweb="select"] > div:hover{border-color:var(--bj-border-strong);}
[data-baseweb="select"] *{color:var(--bj-text);}
[data-baseweb="select"] svg{fill:var(--bj-muted);}
[data-baseweb="popover"] ul, [data-baseweb="menu"]{background:var(--bj-surface-2) !important; border:1px solid var(--bj-border);}
[data-baseweb="popover"] li{color:var(--bj-text) !important;}
[data-baseweb="popover"] li:hover{background:var(--bj-accent-soft) !important;}

[data-testid="stFileUploaderDropzone"]{
  background:var(--bj-surface-2); border:1.5px dashed var(--bj-border-strong); border-radius:12px;
  transition:border-color .18s ease, background .18s ease;
}
[data-testid="stFileUploaderDropzone"]:hover{border-color:var(--bj-accent); background:var(--bj-accent-soft);}
[data-testid="stFileUploaderDropzone"] *{color:var(--bj-muted);}
[data-testid="stFileUploaderFile"]{background:var(--bj-surface-2); border:1px solid var(--bj-border); border-radius:10px; padding:.3rem .6rem;}
[data-testid="stFileUploaderFileName"]{color:var(--bj-text);}
[data-testid="stImage"] img{border-radius:10px; border:1px solid var(--bj-border); background:var(--bj-surface-2);
  max-height:440px; object-fit:contain;}
[data-testid="stImageCaption"]{color:var(--bj-muted);}

[data-testid="stBaseButton-secondary"], [data-testid="stBaseLinkButton-secondary"],
[data-testid="stFileUploaderDropzone"] button{
  background:var(--bj-surface-2); color:var(--bj-text) !important; border:1px solid var(--bj-border-strong);
  border-radius:10px; font-weight:600; transition:border-color .15s ease, color .15s ease, background .15s ease;
}
[data-testid="stBaseButton-secondary"]:hover, [data-testid="stBaseLinkButton-secondary"]:hover,
[data-testid="stFileUploaderDropzone"] button:hover{border-color:var(--bj-accent); color:var(--bj-accent) !important;}
[data-testid="stBaseButton-primary"]{
  background:var(--bj-accent-solid); color:#fff !important; border:1px solid transparent; border-radius:10px;
  font-weight:700; box-shadow:var(--bj-shadow); transition:filter .15s ease, transform .05s ease;
}
[data-testid="stBaseButton-primary"]:hover{filter:brightness(1.12);}
[data-testid="stBaseButton-primary"]:active, [data-testid="stBaseButton-secondary"]:active{transform:translateY(1px);}
[data-testid="stBaseButton-primary"] p, [data-testid="stBaseButton-secondary"] p,
[data-testid="stBaseLinkButton-secondary"] p{color:inherit;}

[data-testid="stDeckGlJsonChart"]{border:1px solid var(--bj-border); border-radius:12px; overflow:hidden;}

/* Responsive ---------------------------------------------------------------- */
@media (max-width: 900px){
  .block-container{padding-left:1.2rem; padding-right:1.2rem;}
  .bj-hero{padding:1.2rem 1.3rem;}
  .bj-hero h1{font-size:1.6rem;}
}
@media (max-width: 640px){
  .block-container{padding:1rem .8rem 2rem .8rem;}
  .bj-hero h1{font-size:1.4rem;}
  .bj-kv-row{flex-direction:column; align-items:flex-start; gap:.15rem;}
  .bj-kv-v{text-align:left;}
}
"""


def _svg(inner: str, size: int = 18) -> str:
    return (
        f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        f'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{inner}</svg>'
    )


ICON_DOC = _svg('<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/><path d="M9 13h6M9 17h4"/>')
ICON_DB = _svg('<ellipse cx="12" cy="6" rx="8" ry="3"/><path d="M4 6v6c0 1.66 3.58 3 8 3s8-1.34 8-3V6"/><path d="M4 12v6c0 1.66 3.58 3 8 3s8-1.34 8-3v-6"/>')
ICON_CHECK = _svg('<path d="M9 11l3 3 8-8"/><path d="M20 12v7a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2h9"/>')
ICON_LAYERS = _svg('<path d="M12 3l9 5-9 5-9-5z"/><path d="M3 13l9 5 9-5"/>')
ICON_SEARCH = _svg('<circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/>')
ICON_PIN = _svg('<path d="M12 21s7-6.2 7-11a7 7 0 1 0-14 0c0 4.8 7 11 7 11z"/><circle cx="12" cy="10" r="2.5"/>')

LOGO_SVG = (
    '<svg width="36" height="36" viewBox="0 0 36 36" aria-hidden="true">'
    '<defs><linearGradient id="bjg" x1="0" y1="0" x2="1" y2="1">'
    '<stop offset="0" stop-color="#14b8a6"/><stop offset="1" stop-color="#2563eb"/></linearGradient></defs>'
    '<rect width="36" height="36" rx="10" fill="url(#bjg)"/>'
    '<path d="M9 24 L12 13 L21 11 L27 19 L23 27 Z" fill="none" stroke="#fff" stroke-width="1.8" stroke-linejoin="round"/>'
    '<circle cx="19" cy="18" r="2.6" fill="#fff"/></svg>'
)


def html(markup: str) -> None:
    st.markdown(markup, unsafe_allow_html=True)


def badge(text: str, kind: str = "neutral", dot: bool = True) -> str:
    dot_html = "<i></i>" if dot else ""
    return f'<span class="bj-badge bj-{kind}">{dot_html}{text}</span>'


def badge_row(*badges: str) -> None:
    html(f'<div class="bj-row">{"".join(badges)}</div>')


def section_header(step: int, title: str, subtitle: str, right: str = "") -> None:
    html(
        f'<div class="bj-sec"><div class="bj-step">{step}</div>'
        f'<div><div class="bj-sec-title">{title}</div><div class="bj-sec-sub">{subtitle}</div></div>'
        f'<div class="bj-sec-right">{right}</div></div>'
    )


def kpi(label: str, value: str, hint: str = "", icon: str = "", tone: str = "") -> str:
    icon_html = f'<div class="bj-kpi-icon">{icon}</div>' if icon else ""
    return (
        f'<div class="bj-kpi"><div><div class="bj-kpi-label">{label}</div>'
        f'<div class="bj-kpi-value {tone}">{value}</div><div class="bj-kpi-hint">{hint}</div></div>'
        f"{icon_html}</div>"
    )


def empty_state(icon: str, title: str, text: str) -> None:
    html(
        f'<div class="bj-empty"><div class="ico">{icon}</div><b>{title}</b>{text}</div>'
    )


def fmt_bytes(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n} B"


# ══════════════════════════════════════════════════════════════════════════════
# BUSINESS LOGIC — unchanged
# ══════════════════════════════════════════════════════════════════════════════
def normalize_digits(text: str) -> str:
    trans = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")
    return str(text).translate(trans)


def en_to_bn_digits(text: str) -> str:
    trans = str.maketrans("0123456789", "০১২৩৪৫৬৭৮৯")
    return str(text).translate(trans)


# Universal Language-Agnostic GeoJSON Database Lookup with Dynamic Properties
def load_plot_from_geojson(plot_no: str | int, lang: str = "বাংলা"):
    if not plot_no:
        return None, None
    try:
        geojson_path = Path("sample_data.geojson")
        if not geojson_path.is_file():
            geojson_path = Path("plots.geojson")

        if geojson_path.is_file():
            with open(geojson_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                target = normalize_digits(str(plot_no)).strip()

                for feature in data.get("features", []):
                    props = feature.get("properties", {})
                    pno = normalize_digits(
                        str(props.get("plot_no") or props.get("plot_number") or "")
                    )

                    if pno == target:
                        coords = feature["geometry"]["coordinates"][0]
                        lons = [pt[0] for pt in coords]
                        lats = [pt[1] for pt in coords]
                        center_lon = sum(lons) / len(lons)
                        center_lat = sum(lats) / len(lats)

                        is_bn = lang == "বাংলা"

                        raw_pno = props.get("plot_no", "501")
                        raw_khatian = str(props.get("khatian_no", "1203"))
                        raw_owner = props.get("owner_name", "Abdul Karim")
                        raw_owner_bn = props.get("owner_name_bn", "আব্দুল করিম")
                        
                        raw_mouza = props.get("mouza", "Mirpur")
                        raw_district = props.get("district", "Dhaka")
                        raw_jl = str(props.get("jl_no", "11"))
                        raw_khatian_type = props.get("khatian_type", "RS")
                        raw_land_type = props.get("land_type", "Nal")

                        district_bn_map = {
                            "Dhaka": "ঢাকা", "Gazipur": "গাজীপুর", "Narayanganj": "নারায়ণগঞ্জ", "Tangail": "টাঙ্গাইল", 
                            "Faridpur": "ফরিদপুর", "Manikganj": "মানিকগঞ্জ", "Munshiganj": "মুন্সিগঞ্জ", "Narsingdi": "নরসিংদী", 
                            "Rajbari": "রাজবাড়ী", "Gopalganj": "গোপালগঞ্জ", "Madaripur": "মাদারীপুর", "Shariatpur": "শরীয়তপুর", 
                            "Kishoreganj": "কিশোরগঞ্জ", "Chattogram": "চট্টগ্রাম", "Cox's Bazar": "কক্সবাজার", "Cumilla": "কুমিল্লা", 
                            "Feni": "ফেনী", "Noakhali": "নোয়াখালী", "Lakshmipur": "লক্ষ্মীপুর", "Brahmanbaria": "ব্রাহ্মণবাড়িয়া", 
                            "Chandpur": "চাঁদপুর", "Khagrachhari": "খাগড়াছড়ি", "Rangamati": "রাঙ্গামাটি", "Bandarban": "বান্দরবান", 
                            "Rajshahi": "রাজশাহী", "Bogra": "বগুড়া", "Pabna": "পাবনা", "Sirajganj": "সিরাজগঞ্জ", 
                            "Naogaon": "নওগাঁ", "Natore": "নাটোর", "Chapai Nawabganj": "চাঁপাইনবাবগঞ্জ", "Joypurhat": "জয়পুরহাট", 
                            "Khulna": "খুলনা", "Jashore": "যশোর", "Kushtia": "কুষ্টিয়া", "Satkhira": "সাতক্ষীরা", 
                            "Bagerhat": "বাগেরহাট", "Jhenaidah": "ঝিনাইদহ", "Chuadanga": "চুয়াডাঙ্গা", "Meherpur": "মেহেরপুর", 
                            "Narail": "নড়াইল", "Magura": "মাগুরা", "Barishal": "বরিশাল", "Bhola": "ভোলা", 
                            "Patuakhali": "পটুয়াখালী", "Pirojpur": "পিরোজপুর", "Barguna": "বরগুনা", "Jhalokati": "ঝালকাঠি", 
                            "Sylhet": "সিলেট", "Moulvibazar": "মৌলভীবাজার", "Habiganj": "হবিগঞ্জ", "Sunamganj": "সুনামগঞ্জ", 
                            "Nilphamari": "নীলফামারী", "Dinajpur": "দিনাজপুর", "Gaibandha": "গাইবান্ধা", "Kurigram": "কুড়িগ্রাম", 
                            "Lalmonirhat": "লালমনিরহাট", "Panchagarh": "পঞ্চগড়", "Thakurgaon": "ঠাকুরগাঁও", "Mymensingh": "ময়মনসিংহ", 
                            "Jamalpur": "জামালপুর", "Netrokona": "নেত্রকোনা", "Sherpur": "শেরপুর"
                        }

                        mouza_bn_map = {
                            "Mirpur": "মিরপুর", "Sadar": "সদর", "Tongi": "টঙ্গী", "Siddhirganj": "সিদ্ধিরগঞ্জ", 
                            "Goalchamat": "গোয়ালচামত", "Singair": "সিঙ্গাইর", "Garia": "গাড়িয়া", "Panchdona": "পাঁচদোনা", 
                            "Pangsha": "পাংশা", "Tungipara": "টুঙ্গিপাড়া", "Rajoir": "রাজৈর", "Naria": "নড়িয়া", 
                            "Bhairab": "ভৈরব", "Agrabad": "আগ্রাবাদ", "Ramua": "রামু", "Kandirpar": "কান্দিরপাড়", 
                            "Dagonbhuiyan": "দাগনভূঞা", "Maijdee": "মাইজদী", "Raipur": "রায়পুর", "Ashuganj": "আশুগঞ্জ", 
                            "Hajiganj": "হাজীগঞ্জ", "Dighinala": "দীঘিনালা", "Kaptai": "কাপ্তাই", "Thanchi": "থানচি", 
                            "Boalia": "বোয়ালিয়া", "Sherpur": "শেরপুর", "Ishwardi": "ঈশ্বরদী", "Ullapara": "উল্লাপাড়া", 
                            "Dhamoirhat": "ধামইরহাট", "Baraigram": "বড়াইগ্রাম", "Shibganj": "শিবগঞ্জ", "Akkelpur": "আক্কেলপুর", 
                            "Khalishpur": "খালিশপুর", "Jhikargachha": "ঝিকরগাছা", "Bheramara": "ভেড়ামারা", "Kalaroa": "কলারোয়া", 
                            "Mongla": "মংলা", "Kaliganj": "কালীগঞ্জ", "Damurhuda": "দামুড়হুদা", "Gangni": "গাংনী", 
                            "Lohagara": "লোহাগাড়া", "Shripur": "শ্রীপুর", "Agailjhara": "আগৈলঝাড়া", "Char Fasson": "চরফ্যাশন", 
                            "Kuakata": "কুয়াকাটা", "Bhandaria": "ভাণ্ডারিয়া", "Amtali": "আমতলী", "Nalchity": "নলছিটি", 
                            "Zindabazar": "জিন্দাবাজার", "Sreemangal": "শ্রীমঙ্গল", "Madhabpur": "মাধবপুর", "Tahirpur": "তাহিরপুর", 
                            "Pirganj": "পীরগঞ্জ", "Chilahati": "চিলাহাটি", "Birganj": "বীরগঞ্জ", "Gobindaganj": "গোবিন্দগঞ্জ", 
                            "Nageswari": "নাগেশ্বরী", "Patgram": "পাটগ্রাম", "Tetulia": "তেঁতুলিয়া", "Muktagachha": "মুক্তাগাছা", 
                            "Sarbari": "সরবারি", "Durgapur": "দুর্গাপুর", "Nalitabari": "নালিতাবাড়ী"
                        }

                        pno_disp = en_to_bn_digits(raw_pno) if is_bn else raw_pno
                        khatian_disp = en_to_bn_digits(raw_khatian) if is_bn else raw_khatian
                        owner_disp = raw_owner_bn if is_bn else raw_owner

                        if is_bn:
                            mouza_disp = mouza_bn_map.get(raw_mouza, raw_mouza)
                            district_disp = district_bn_map.get(raw_district, raw_district)
                            jl_disp = en_to_bn_digits(raw_jl)
                        else:
                            mouza_disp = raw_mouza
                            district_disp = raw_district
                            jl_disp = raw_jl

                        khatian_type_disp = raw_khatian_type
                        land_type_disp = raw_land_type

                        area_raw = props.get("declared_area", "0.14 Acre")
                        if is_bn:
                            area_disp = area_raw.replace("Acre", "একর")
                        else:
                            area_disp = area_raw

                        return coords, {
                            "plot": pno_disp,
                            "khatian": khatian_disp,
                            "owner": owner_disp,
                            "mouza": mouza_disp,
                            "jl_no": jl_disp,
                            "khatian_type": khatian_type_disp,
                            "land_type": land_type_disp,
                            "district": district_disp,
                            "declared_area": area_disp,
                            "lat": center_lat,
                            "lon": center_lon,
                            "area_sqm": 566.0,
                        }
    except Exception:
        pass
    return None, None


def tesseract_available() -> bool:
    return (
        importlib.util.find_spec("pytesseract") is not None
        and shutil.which("tesseract") is not None
    )


def run_local_ocr(image: Image.Image) -> str:
    if tesseract_available():
        import pytesseract
        try:
            return pytesseract.image_to_string(image, lang="ben+eng").strip()
        except Exception:
            try:
                return pytesseract.image_to_string(image, lang="eng").strip()
            except Exception:
                pass
    return ""


def run_deep_ai_vision(image: Image.Image) -> str:
    if not GEMINI_API_KEY:
        return ""
    try:
        model = genai.GenerativeModel("gemini-1.5-flash")
        prompt = "Extract all text, numbers, plot/dag numbers, and khatian numbers from this land record image accurately."
        response = model.generate_content([prompt, image])
        return response.text.strip()
    except Exception:
        return ""


def search_plot_in_text(text: str) -> str | None:
    if not text:
        return None
    normalized_text = normalize_digits(text)
    flags = re.IGNORECASE

    plot = re.search(
        r"(?:plot|parcel|khatian|dag|দাগ|নম্বর)\s*(?:no\.?|number|#)?\s*[:\-]?\s*([0-9]+)",
        normalized_text,
        flags,
    )
    if plot:
        return plot.group(1)

    for p in ["501", "502", "503", "504", "107", "3365"]:
        if p in normalized_text:
            return p

    return None


def process_hybrid_pipeline(image: Image.Image, lang: str = "বাংলা") -> dict:
    local_text = run_local_ocr(image)
    detected_plot = search_plot_in_text(local_text)

    if detected_plot:
        _, fields = load_plot_from_geojson(detected_plot, lang=lang)
        if fields and fields.get("lat"):
            return {
                "text": local_text,
                "engine": "Local Fast OCR (Tesseract)",
                "fields": fields,
            }

    deep_ai_text = run_deep_ai_vision(image)
    detected_plot_ai = search_plot_in_text(deep_ai_text)

    if detected_plot_ai:
        _, fields = load_plot_from_geojson(detected_plot_ai, lang=lang)
        if fields and fields.get("lat"):
            return {
                "text": deep_ai_text,
                "engine": "Deep AI Vision (Gemini 1.5 Flash)",
                "fields": fields,
            }

    not_found_fields = {
        "plot": None,
        "khatian": None,
        "owner": "⚠️ এই ডকুমেন্টটি আমাদের ডাটাবেজে নেই (Not Found)",
        "mouza": None,
        "jl_no": None,
        "khatian_type": None,
        "land_type": None,
        "district": None,
        "declared_area": None,
        "lat": None,
        "lon": None,
        "area_sqm": None
    }
    return {
        "text": local_text or deep_ai_text,
        "engine": "Database Match Failed",
        "fields": not_found_fields,
    }


# Session state initialization
for key, default in {
    "result": None,
    "file_sig": None,
    "docs_processed": 0,
    "lat": 23.8103,
    "lon": 90.4125,
}.items():
    st.session_state.setdefault(key, default)

# ══════════════════════════════════════════════════════════════════════════════
# Sidebar
# ══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    html(
        f'<div class="bj-brand">{LOGO_SVG}'
        '<div><div class="bj-brand-name">Bankrup <span>By Jamuna</span></div>'
        '<div class="bj-brand-sub">Enterprise Land Intelligence</div></div></div>'
    )

    html('<div class="bj-side-label">Language / ভাষা</div>')
    selected_lang = st.radio(
        "Interface Mode", ["বাংলা", "English"], index=0, horizontal=True, label_visibility="collapsed"
    )
    is_bn = selected_lang == "বাংলা"

    html('<div class="bj-side-label">Theme Mode / থিম</div>')
    selected_theme = st.radio(
        "Theme Mode", ["Dark 🌙", "Light ☀️"], index=0, horizontal=True, label_visibility="collapsed"
    )
    is_dark = selected_theme == "Dark 🌙"

    st.markdown(get_css(is_dark), unsafe_allow_html=True)

    html('<div class="bj-side-label">GIS Map Configuration</div>')
    default_map_idx = 1 if is_dark else 0
    map_style = st.selectbox(
        "Basemap", ["light", "dark", "road"], index=default_map_idx
    )
    show_boundary = st.toggle("Show parcel footprint", value=True)

    html('<div class="bj-side-label">Pipeline Status</div>')
    status_slot = st.container()

# ══════════════════════════════════════════════════════════════════════════════
# Hero Banner
# ══════════════════════════════════════════════════════════════════════════════
hero_sub = (
    "এন্টারপ্রাইজ গ্রেড হাইব্রিড ও.সি.আর ও রিয়েল-টাইম জিআইএস পার্সেল ভেরিফিকেশন প্ল্যাটফর্ম।"
    if is_bn
    else "Enterprise-grade hybrid OCR pipeline with real-time cadastral parcel verification & GIS mapping."
)

html(
    f'<div class="bj-hero"><div class="bj-eyebrow">'
    f'{"ল্যান্ড ডকুমেন্ট ইন্টেলিজেন্স" if is_bn else "Land Document Intelligence"}</div>'
    f"<h1>Bankrup <span>By Jamuna</span></h1>"
    f"<p>{hero_sub}</p>"
    f'<div class="bj-chips">'
    f'<span class="bj-chip">{ICON_DOC} {"ডকুমেন্ট আপলোড" if is_bn else "Document Upload"}</span>'
    f'<span class="bj-chip">{ICON_SEARCH} {"স্মার্ট ও.সি.আর" if is_bn else "Smart Extraction"}</span>'
    f'<span class="bj-chip">{ICON_PIN} {"জিআইএস বাউন্ডারি" if is_bn else "GIS Boundary"}</span></div></div>'
)
kpi_slot = st.container()
st.write("")

# Row 1 — Upload & Extracted Fields
col_upload, col_ocr = st.columns([1, 1.25], gap="large")
image: Image.Image | None = None

with col_upload:
    with st.container(key="card-upload"):
        sec1_title = "ডকুমেন্ট আপলোড করুন" if is_bn else "Upload Document"
        sec1_sub = (
            "খতিয়ান বা পর্চার স্ক্যান কপি (PNG, JPG, TIFF)"
            if is_bn
            else "Scanned land records or Khatian (PNG, JPG, TIFF)"
        )
        section_header(1, sec1_title, sec1_sub)
        uploaded = st.file_uploader(
            "Land document",
            type=["png", "jpg", "jpeg", "tif", "tiff"],
            label_visibility="collapsed",
        )

        if uploaded is not None:
            try:
                image = Image.open(uploaded).convert("RGB")
            except Exception:
                st.error("Invalid image file format.")

        if image is not None:
            sig = (uploaded.name, uploaded.size)
            if sig != st.session_state.file_sig:
                st.session_state.file_sig = sig
                st.session_state.result = None

            st.image(image, caption=uploaded.name)
            badge_row(
                badge("Ready", "success"),
                badge(f"{image.width}×{image.height}px", "neutral", dot=False),
                badge(fmt_bytes(uploaded.size), "neutral", dot=False),
            )
            btn_txt = (
                "ও.সি.আর ও ডাটাবেজ যাচাই করুন"
                if is_bn
                else "Run OCR & Verify Database"
            )
            run_clicked = st.button(btn_txt, type="primary", use_container_width=True)
            if run_clicked:
                with st.spinner(
                    "Executing Hybrid Pipeline (Local Fast OCR -> Deep AI Fallback)..."
                ):
                    res = process_hybrid_pipeline(image, lang=selected_lang)
                st.session_state.result = res
                st.session_state.docs_processed += 1
                fields = res["fields"]
                if fields["lat"] is not None and fields["lon"] is not None:
                    st.session_state.lat, st.session_state.lon = (
                        fields["lat"],
                        fields["lon"],
                    )
        else:
            st.session_state.file_sig = None
            st.session_state.result = None
            empty_title = "কোনো ফাইল দেওয়া হয়নি" if is_bn else "No Document Uploaded"
            empty_desc = (
                "যাচাইকরণের জন্য খতিয়ানের স্ক্যান কপি আপলোড করুন।"
                if is_bn
                else "Upload a land record document above to begin extraction."
            )
            empty_state(ICON_DOC, empty_title, empty_desc)

result = st.session_state.result

if result and result.get("fields"):
    raw_plot = result["fields"].get("plot")
    if raw_plot:
        clean_plot = normalize_digits(str(raw_plot))
        _, updated_fields = load_plot_from_geojson(clean_plot, lang=selected_lang)
        if updated_fields:
            result["fields"] = updated_fields

with col_ocr:
    with st.container(key="card-ocr"):
        if result is None:
            right = badge("অপেক্ষা করা হচ্ছে" if is_bn else "Waiting", "neutral")
        elif result["fields"].get("lat") is not None:
            right = badge(
                "ডাটাবেজে যাচাইকৃত" if is_bn else "Verified in Database",
                "success",
            )
        else:
            right = badge(
                "ডাটাবেজে নেই" if is_bn else "Not Found", "error"
            )

        sec2_title = (
            "এক্সট্রাক্ট করা ফিল্ডসমূহ" if is_bn else "Extracted Parcel Fields"
        )
        sec2_sub = (
            "জিওজোসন ডাটাবেজ থেকে রিয়েল-টাইম ম্যাচকৃত তথ্য"
            if is_bn
            else "Structured land record attributes & database status"
        )
        section_header(2, sec2_title, sec2_sub, right)

        if result is None:
            empty_state(
                ICON_SEARCH,
                "কোনো তথ্য এক্সট্রাক্ট হয়নি" if is_bn else "No Extraction Yet",
                (
                    "ডকুমেন্ট আপলোড করে প্রসেস রান করুন।"
                    if is_bn
                    else "Upload a document and execute pipeline to view fields."
                ),
            )
        else:
            fields = result["fields"]
            st.caption(
                f"⚡ **Pipeline Engine:** `{result.get('engine', 'Unknown')}`"
            )

            if fields.get("lat") is None:
                st.warning(
                    "⚠️ এই খতিয়ান বা প্লট নম্বরটি ডাটাবেজে পাওয়া যায়নি।"
                    if is_bn
                    else "⚠️ Record not found in GeoJSON database."
                )

            if is_bn:
                tiles = [
                    ("দাগ নম্বর", fields.get("plot")),
                    ("খতিয়ান নম্বর", fields.get("khatian")),
                    ("মালিকের নাম", fields.get("owner")),
                    ("মৌজা নাম", fields.get("mouza")),
                    ("জে.এল. নম্বর", fields.get("jl_no")),
                    ("খতিয়ান প্রকার", fields.get("khatian_type")),
                    ("জমির শ্রেণি", fields.get("land_type")),
                    ("জেলা / উপজেলা", fields.get("district")),
                    ("জমির পরিমাণ", fields.get("declared_area")),
                    (
                        "জিপিএস কোঅর্ডিনেট",
                        (
                            f"{fields['lat']:.5f}, {fields['lon']:.5f}"
                            if fields.get("lat")
                            else None
                        ),
                    ),
                ]
            else:
                tiles = [
                    ("Plot / Dag No", fields.get("plot")),
                    ("Khatian No", fields.get("khatian")),
                    ("Owner Name", fields.get("owner")),
                    ("Mouza Name", fields.get("mouza")),
                    ("J.L. No", fields.get("jl_no")),
                    ("Khatian Type", fields.get("khatian_type")),
                    ("Land Class", fields.get("land_type")),
                    ("District", fields.get("district")),
                    ("Declared Area", fields.get("declared_area")),
                    (
                        "Coordinates",
                        (
                            f"{fields['lat']:.5f}, {fields['lon']:.5f}"
                            if fields.get("lat")
                            else None
                        ),
                    ),
                ]

            grid = "".join(
                f'<div class="bj-tile{"" if v else " missing"}">'
                f'<div class="bj-tile-label">{label}</div>'
                f'<div class="bj-tile-value">{v or ("পাওয়া যায়নি" if is_bn else "Not found")}</div></div>'
                for label, v in tiles
            )
            html(f'<div class="bj-grid">{grid}</div>')

            found = sum(1 for _, v in tiles if v)
            badge_row(
                badge(
                    f"{found}/{len(tiles)} "
                    + (
                        "ফিল্ড সফলভাবে ভেরিফাই হয়েছে"
                        if is_bn
                        else "fields successfully verified"
                    ),
                    "success" if found == len(tiles) else "warn",
                )
            )

            st.download_button(
                "ডাউনলোড করুন (JSON)" if is_bn else "Export Fields (JSON)",
                data=json.dumps(fields, indent=2, ensure_ascii=False),
                file_name="bankrup_verified_land_fields.json",
                mime="application/json",
                use_container_width=True,
            )

st.write("")

# Row 2 — GIS Map Viewer
with st.container(key="card-map"):
    fields = result["fields"] if result else {}
    lat = fields.get("lat")
    lon = fields.get("lon")
    plot_no = fields.get("plot")

    polygon_coords = None
    if plot_no:
        clean_plot = normalize_digits(str(plot_no))
        polygon_coords, _ = load_plot_from_geojson(clean_plot, lang=selected_lang)

    has_coords = lat is not None and lon is not None and polygon_coords is not None

    sec3_title = (
        "স্যাটেলাইট ম্যাপ ভিউয়ার (GIS)"
        if is_bn
        else "GIS Map Viewer & Cadastral Overlay"
    )
    sec3_sub = (
        "ভেরিফাইকৃত প্লটের জিওস্পেশিয়াল বাউন্ডারি ও পিন পয়েন্ট"
        if is_bn
        else "Verified parcel boundary polygon and satellite coordinate overlay"
    )
    section_header(
        3,
        sec3_title,
        sec3_sub,
        (
            badge("ম্যাচ সফল" if is_bn else "Database Match Active", "success")
            if has_coords
            else badge("ম্যাপ নিষ্ক্রিয়" if is_bn else "Inactive", "neutral")
        ),
    )

    col_map, col_info = st.columns([2.1, 1], gap="large")

    with col_info:
        if has_coords:
            if is_bn:
                rows = [
                    ("দাগ নং", plot_no),
                    ("খতিয়ান নং", fields.get("khatian")),
                    ("মালিকের নাম", fields.get("owner")),
                    ("মৌজা", fields.get("mouza")),
                    ("জমির পরিমাণ", fields.get("declared_area")),
                    ("অবস্থান", f"{lat:.5f}, {lon:.5f}"),
                ]
            else:
                rows = [
                    ("Plot No", plot_no),
                    ("Khatian No", fields.get("khatian")),
                    ("Owner", fields.get("owner")),
                    ("Mouza", fields.get("mouza")),
                    ("Area", fields.get("declared_area")),
                    ("Position", f"{lat:.5f}, {lon:.5f}"),
                ]
            kv = "".join(
                f'<div class="bj-kv-row"><span class="bj-kv-k">{k}</span>'
                f'<span class="bj-kv-v{" mono" if i == len(rows) - 1 else ""}">{v or "—"}</span></div>'
                for i, (k, v) in enumerate(rows)
            )
            html(f'<div class="bj-kv">{kv}</div>')
            st.link_button(
                "গুগল ম্যাপে লোকেশন দেখুন" if is_bn else "Open in Google Maps",
                f"https://www.google.com/maps?q={lat},{lon}",
                use_container_width=True,
            )
        else:
            st.info(
                "সফল ডাটাবেজ ম্যাচ না হওয়া পর্যন্ত ম্যাপ ভিউয়ার নিষ্ক্রিয় থাকবে।"
                if is_bn
                else "Map viewer is on standby awaiting a valid parcel database match."
            )

    with col_map:
        if has_coords:
            layers = []
            if show_boundary:
                layers.append(
                    pdk.Layer(
                        "PolygonLayer",
                        data=[{"polygon": polygon_coords}],
                        get_polygon="polygon",
                        get_fill_color=[14, 165, 233, 85],
                        get_line_color=[14, 165, 233, 255],
                        line_width_min_pixels=3,
                        stroked=True,
                        filled=True,
                    )
                )
            layers.append(
                pdk.Layer(
                    "ScatterplotLayer",
                    data=pd.DataFrame([{"lat": lat, "lon": lon, "plot": plot_no}]),
                    get_position="[lon, lat]",
                    get_radius=6,
                    radius_min_pixels=9,
                    get_fill_color=[16, 185, 129, 240],
                    get_line_color=[255, 255, 255, 255],
                    line_width_min_pixels=2,
                    stroked=True,
                    pickable=True,
                )
            )
            st.pydeck_chart(
                pdk.Deck(
                    layers=layers,
                    initial_view_state=pdk.ViewState(
                        latitude=lat, longitude=lon, zoom=18, pitch=0
                    ),
                    map_style=map_style,
                    tooltip={
                        "text": f"Plot: {plot_no}\nOwner: "
                        + str(fields.get("owner", ""))
                    },
                ),
                height=465,
            )
        else:
            empty_state(
                ICON_PIN,
                "ম্যাপ নিষ্ক্রিয়" if is_bn else "GIS Map Standby",
                (
                    "ডাটাবেজে বৈধ রেকর্ড না পাওয়ায় ম্যাপ রেন্ডার করা হয়নি।"
                    if is_bn
                    else "No matching parcel found in GeoJSON database to render boundary."
                ),
            )

# KPI row & Status
with kpi_slot:
    k1, k2, k3, k4 = st.columns(4, gap="medium")
    res = st.session_state.result
    n_fields = sum(1 for v in res["fields"].values() if v is not None) if res else 0

    lbl_docs = "মোট প্রসেসড" if is_bn else "Documents"
    lbl_db = "ডাটাবেজ স্ট্যাটাস" if is_bn else "Database Status"
    lbl_extracted = "সফল এক্সট্রাকশন" if is_bn else "Fields Extracted"
    lbl_mode = "জিআইএস লেয়ার" if is_bn else "GIS Layer"

    val_db = (
        ("ম্যাচ সফল" if is_bn else "Matched")
        if (res and res["fields"].get("lat"))
        else ("ম্যাচ হয়নি" if is_bn else "No Match")
    )
    # Display-only tone for the database KPI (same data as val_db above)
    db_tone = "ok" if (res and res["fields"].get("lat")) else ("err" if res else "muted")

    k1.markdown(
        kpi(
            lbl_docs,
            str(st.session_state.docs_processed),
            "নথি প্রসেসড" if is_bn else "scans processed",
            icon=ICON_DOC,
        ),
        unsafe_allow_html=True,
    )
    k2.markdown(
        kpi(lbl_db, val_db, "GeoJSON Index", icon=ICON_DB, tone=db_tone),
        unsafe_allow_html=True,
    )
    k3.markdown(
        kpi(
            lbl_extracted,
            f"{n_fields}/10",
            "যাচাইকৃত এট্রিবিউট" if is_bn else "verified attributes",
            icon=ICON_CHECK,
        ),
        unsafe_allow_html=True,
    )
    k4.markdown(
        kpi(
            lbl_mode,
            "সক্রিয় বাউন্ডারি" if is_bn else "Polygon Active",
            "Cadastral Overlay",
            icon=ICON_LAYERS,
        ),
        unsafe_allow_html=True,
    )

with status_slot:
    engine_name = result.get("engine", "Standby") if result else "Idle"
    items = [
        ("Pipeline", badge(engine_name, "info")),
        (
            "Document",
            (
                badge("লোড হয়েছে" if is_bn else "Loaded", "success")
                if st.session_state.file_sig
                else badge("অপেক্ষমাণ" if is_bn else "Waiting", "neutral")
            ),
        ),
        (
            "Database",
            (
                badge("যাচাইকৃত" if is_bn else "Verified", "success")
                if (result and result["fields"].get("lat"))
                else badge("অপেক্ষমাণ" if is_bn else "Pending", "neutral")
            ),
        ),
        (
            "GIS Map",
            (
                badge("অনলাইন" if is_bn else "Active", "success")
                if (result and result["fields"].get("lat"))
                else badge("অপেক্ষমাণ" if is_bn else "Pending", "neutral")
            ),
        ),
    ]
    html(
        "".join(
            f'<div class="bj-status"><span>{name}</span>{b}</div>'
            for name, b in items
        )
    )