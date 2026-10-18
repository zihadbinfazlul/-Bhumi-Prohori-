"""
Bhumi Prohori — Land Document Intelligence & GIS Platform
Features: Dual Login (Citizen vs Govt Employee), Hybrid OCR Pipeline, Cadastral GIS.
"""

from __future__ import annotations

import base64
import importlib.util
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import shutil
import time
from collections.abc import Mapping
from pathlib import Path

import google.generativeai as genai
import folium
import pandas as pd
import pydeck as pdk
import psycopg
import streamlit as st
from cryptography.fernet import Fernet, InvalidToken
from PIL import Image
from psycopg.rows import dict_row
from streamlit.errors import StreamlitSecretNotFoundError
from streamlit_folium import st_folium

DATABASE_ERRORS = (sqlite3.Error, psycopg.Error)
DATABASE_INTEGRITY_ERRORS = (sqlite3.IntegrityError, psycopg.IntegrityError)

# Page config
APP_ICON_PATH = Path(__file__).with_name("photo_2026-10-18_02-25-37.jpg")
APP_ICON_DATA_URI = (
    "data:image/jpeg;base64,"
    + base64.b64encode(APP_ICON_PATH.read_bytes()).decode("ascii")
)
st.set_page_config(
    page_title="ভূমিপ্রহরী | Bhumi Prohori",
    page_icon=str(APP_ICON_PATH),
    layout="wide",
    initial_sidebar_state="expanded",
)

# Safe Gemini API Key loading
GEMINI_API_KEY = ""
try:
    if "GEMINI_API_KEY" in st.secrets:
        GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
except Exception:
    pass

if not GEMINI_API_KEY:
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

OWNERSHIP_DB_PATH = Path(
    os.environ.get(
        "LAND_OWNERSHIP_DB",
        Path(__file__).resolve().with_name("ownership_changes.sqlite3"),
    )
)
OWNERSHIP_PROOF_MAX_BYTES = 10 * 1024 * 1024
APP_VERSION = "1.0.0"


def land_geojson_path() -> Path:
    configured_path = os.environ.get("LAND_RECORDS_GEOJSON")
    if configured_path:
        path = Path(configured_path).expanduser().resolve()
        if path.is_file():
            return path
        raise FileNotFoundError(
            f"Configured land-record GeoJSON file was not found: {path}"
        )

    data_directory = Path(__file__).resolve().parent
    for filename in (
        "bangladesh_demo_data.geojson",
        "sample_data.geojson",
        "plots.geojson",
    ):
        path = data_directory / filename
        if path.is_file():
            return path
    raise FileNotFoundError("Land-record GeoJSON file was not found.")


def get_css(is_dark: bool, system_mode: bool = False) -> str:
    if is_dark:
        background_color = "#10150c"
        surface_bg = "rgba(255, 255, 255, 0.025)"
        border_color = "rgba(173, 193, 132, 0.16)"
        text_color = "#f3f4f6"
        muted_color = "rgba(243, 244, 246, 0.55)"
        hero_bg = "linear-gradient(135deg, #10150c 0%, #1b2413 55%, #26351b 100%)"
        sidebar_bg = "#171e11"
        accent_color = "#b8d68a"
        accent_color_2 = "#d0e7a2"
    else:
        background_color = "#ffffff"
        surface_bg = "rgba(255, 255, 255, 0.82)"
        border_color = "rgba(85, 107, 47, 0.16)"
        text_color = "#26301f"
        muted_color = "rgba(38, 48, 31, 0.62)"
        hero_bg = "linear-gradient(135deg, #ffffff 0%, #f7f9f3 55%, #edf3e5 100%)"
        sidebar_bg = "#f7f9f3"
        accent_color = "#556b2f"
        accent_color_2 = "#6b8e23"

    css = """
    <style>
    :root {
      color-scheme: COLOR_SCHEME;
      --background-color: BACKGROUND_COLOR !important;
      --secondary-background-color: SIDEBAR_BG !important;
      --text-color: TEXT_COLOR !important;
      --primary-color: #556b2f !important;
      --border-color: BORDER_COLOR !important;
      --link-color: #556b2f !important;
      --bj-accent: ACCENT_COLOR;
      --bj-accent-2: ACCENT_COLOR_2;
      --bj-accent-soft: rgba(85, 107, 47, 0.1);
      --bj-line: BORDER_COLOR;
      --bj-surface: SURFACE_BG;
      --bj-muted: MUTED_COLOR;
    }
    .stApp, [data-testid="stAppViewContainer"] {
      --background-color: BACKGROUND_COLOR !important;
      --secondary-background-color: SIDEBAR_BG !important;
      --text-color: TEXT_COLOR !important;
      --primary-color: #556b2f !important;
      --border-color: BORDER_COLOR !important;
      --link-color: #556b2f !important;
      color-scheme: COLOR_SCHEME;
      background: BACKGROUND_COLOR !important;
      color: TEXT_COLOR !important;
    }
    [data-testid="stSidebar"] {background: SIDEBAR_BG !important; color: TEXT_COLOR !important;}
    [data-testid="stHeader"], [data-testid="stToolbar"] {background: BACKGROUND_COLOR !important;}
    .stApp p, .stApp label, .stApp [data-testid="stMarkdownContainer"], .stApp [data-testid="stWidgetLabel"],
    [data-testid="stSidebar"] p, [data-testid="stSidebar"] label, [data-testid="stSidebar"] [data-testid="stMarkdownContainer"],
    [data-testid="stSidebar"] [data-testid="stWidgetLabel"] {color: TEXT_COLOR;}
    .stApp input, .stApp textarea, .stApp [data-baseweb="select"] > div, .stApp [data-baseweb="input"] > div,
    [data-testid="stSidebar"] input, [data-testid="stSidebar"] textarea,
    [data-testid="stSidebar"] [data-baseweb="select"] > div, [data-testid="stSidebar"] [data-baseweb="input"] > div {
      background-color: SIDEBAR_BG !important; color: TEXT_COLOR !important; border-color: BORDER_COLOR !important;
    }
    .stApp [data-baseweb="select"] input, .stApp [data-baseweb="input"] input,
    [data-testid="stSidebar"] [data-baseweb="select"] input,
    [data-testid="stSidebar"] [data-baseweb="input"] input {color: TEXT_COLOR !important;}
    [data-baseweb="popover"], [role="listbox"], [role="option"] {background: SIDEBAR_BG !important; color: TEXT_COLOR !important;}
    .stApp [data-testid="stTabs"] button[role="tab"] {color: TEXT_COLOR;}
    .stApp [data-testid="stTabs"] button[role="tab"][aria-selected="true"] {color: var(--bj-accent); border-bottom-color: var(--bj-accent);}
    .stApp [data-testid="stDataFrame"], .stApp [data-testid="stTable"] {border-color: BORDER_COLOR;}
    .stApp [data-testid="stFileUploaderDropzone"], [data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] {
      background: SIDEBAR_BG !important; color: TEXT_COLOR !important; border-color: BORDER_COLOR !important;
    }
    .stApp [data-testid="stBaseButton-secondary"], [data-testid="stSidebar"] [data-testid="stBaseButton-secondary"] {
      background: SIDEBAR_BG !important; color: TEXT_COLOR !important; border-color: BORDER_COLOR !important;
    }
    #MainMenu, footer {visibility: hidden;}
    .block-container {padding-top: 4rem; padding-bottom: 2rem; max-width: 1420px; color: TEXT_COLOR;}
    h1, h2, h3 {letter-spacing: -0.03em; color: TEXT_COLOR; font-weight: 700;}
    a {color: var(--bj-accent);}
    [data-testid="stBaseButton-primary"] {background-color: #556b2f; border-color: #556b2f; color: #fff !important;}
    [data-testid="stBaseButton-primary"] p {color: #fff !important;}
    [data-testid="stBaseButton-primary"]:hover {background-color: #405522; border-color: #405522;}
    [data-testid="stBaseButton-primary"]:focus-visible {box-shadow: 0 0 0 0.2rem rgba(85, 107, 47, 0.28);}
    [data-baseweb="radio"] div[aria-checked="true"], [data-baseweb="checkbox"] div[aria-checked="true"] {background-color: var(--bj-accent); border-color: var(--bj-accent);}
    [data-testid="stFileUploaderDropzone"]:hover {border-color: var(--bj-accent); background: var(--bj-accent-soft);}

    .bj-hero {
      position: relative; overflow: hidden; border-radius: 16px; padding: 1.4rem 1.8rem; margin-bottom: 1rem;
      background: HERO_BG; border: 1px solid var(--bj-line); box-shadow: 0 10px 28px -18px rgba(0, 0, 0, 0.25);
    }
    .bj-hero h1 {margin: 0.1rem 0 0.25rem 0; font-size: 2rem; font-weight: 800; letter-spacing: -0.04em;}
    .bj-hero h1 span {background: linear-gradient(90deg, var(--bj-accent), var(--bj-accent-2)); -webkit-background-clip: text; -webkit-text-fill-color: transparent;}
    .bj-hero p {margin: 0; max-width: 680px; font-size: 0.92rem; opacity: 0.85; line-height: 1.45;}
    .bj-eyebrow {font-size: 0.75rem; font-weight: 700; letter-spacing: 0.16em; text-transform: uppercase; color: var(--bj-accent);}
    .bj-chips {display: flex; flex-wrap: wrap; gap: 0.5rem; margin-top: 1.2rem;}
    .bj-chip {
      display: inline-flex; align-items: center; gap: 0.4rem; padding: 0.3rem 0.8rem; border-radius: 999px;
      font-size: 0.76rem; font-weight: 600; background: var(--bj-surface); border: 1px solid var(--bj-line); color: TEXT_COLOR;
    }

    div[class*="st-key-card-"] {
      border: 1px solid var(--bj-line); border-radius: 16px; padding: 1.35rem 1.5rem;
      background: var(--bj-surface); box-shadow: 0 4px 20px -4px rgba(0, 0, 0, 0.05);
    }
    .bj-sec {display: flex; align-items: center; gap: 0.85rem; margin-bottom: 1rem;}
    .bj-step {
      flex: 0 0 auto; width: 32px; height: 32px; border-radius: 10px; display: grid; place-items: center;
      font-weight: 700; font-size: 0.9rem; color: #fff; background: linear-gradient(135deg, #556b2f, #6b8e23);
      box-shadow: 0 4px 12px rgba(85, 107, 47, 0.3);
    }
    .bj-sec-title {font-size: 1.1rem; font-weight: 700; color: TEXT_COLOR;}
    .bj-sec-sub {font-size: 0.82rem; color: var(--bj-muted); margin-top: 0.05rem;}
    .bj-sec-right {margin-left: auto;}

    .bj-badge {
      display: inline-flex; align-items: center; gap: 0.35rem; padding: 0.2rem 0.65rem; border-radius: 999px;
      font-size: 0.72rem; font-weight: 700; border: 1px solid transparent; white-space: nowrap;
    }
    .bj-badge i {width: 6px; height: 6px; border-radius: 50%; background: currentColor; display: inline-block;}
    .bj-success {color: #SUCCESS_TEXT; background: rgba(107, 142, 35, 0.1); border-color: rgba(85, 107, 47, 0.25);}
    .bj-warn    {color: #f59e0b; background: rgba(245, 158, 11, 0.1); border-color: rgba(245, 158, 11, 0.25);}
    .bj-error   {color: #ef4444; background: rgba(239, 68, 68, 0.1);  border-color: rgba(239, 68, 68, 0.25);}
    .bj-info    {color: #INFO_TEXT; background: rgba(85, 107, 47, 0.1); border-color: rgba(85, 107, 47, 0.25);}
    .bj-neutral {color: var(--bj-muted); background: var(--bj-surface); border-color: var(--bj-line);}
    .bj-row {display: flex; flex-wrap: wrap; gap: 0.45rem; margin: 0.5rem 0 0.8rem 0;}

    .bj-kpi {
      border: 1px solid var(--bj-line); border-radius: 14px; padding: 1rem 1.2rem; background: var(--bj-surface);
      position: relative; overflow: hidden;
    }
    .bj-kpi::before {
      content: ""; position: absolute; left: 0; top: 0; bottom: 0; width: 3px;
      background: linear-gradient(180deg, #556b2f, #8a9a5b);
    }
    .bj-kpi-label {font-size: 0.72rem; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; color: var(--bj-muted);}
    .bj-kpi-value {font-size: 1.6rem; font-weight: 800; line-height: 1.2; margin-top: 0.2rem; color: TEXT_COLOR;}
    .bj-kpi-hint {font-size: 0.75rem; color: var(--bj-muted); margin-top: 0.1rem;}

    .bj-grid {display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 0.75rem; margin: 0.6rem 0 0.5rem 0;}
    .bj-tile {border: 1px solid var(--bj-line); border-radius: 12px; padding: 0.8rem 1rem; background: var(--bj-surface);}
    .bj-tile-label {font-size: 0.7rem; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; color: var(--bj-muted);}
    .bj-tile-value {font-size: 1.02rem; font-weight: 700; margin-top: 0.2rem; word-break: break-word; color: TEXT_COLOR;}
    .bj-tile.missing {border-style: dashed; border-color: rgba(239, 68, 68, 0.3);}
    .bj-tile.missing .bj-tile-value {color: #ef4444; font-weight: 500;}

    .bj-empty {text-align: center; padding: 2.5rem 1rem; border: 1.5px dashed var(--bj-line); border-radius: 14px; color: var(--bj-muted);}
    .bj-empty b {display: block; font-size: 0.98rem; color: TEXT_COLOR; margin: 0.4rem 0 0.15rem 0;}
    .bj-empty .ico {font-size: 1.8rem;}

    section[data-testid="stSidebar"] {border-right: 1px solid var(--bj-line);}
    .bj-brand {display: flex; align-items: center; gap: 0.75rem; padding: 0.4rem 0 1rem 0; border-bottom: 1px solid var(--bj-line); margin-bottom: 1rem;}
    .bj-logo {
      width: 38px; height: 38px; border-radius: 10px; display: grid; place-items: center; font-size: 1.2rem;
      background: linear-gradient(135deg, #556b2f, #6b8e23); box-shadow: 0 4px 12px rgba(85, 107, 47, 0.28);
    }
    .bj-brand-name {font-weight: 800; font-size: 1.05rem; line-height: 1.1; color: TEXT_COLOR;}
    .bj-brand-sub {font-size: 0.74rem; color: var(--bj-muted); font-weight: 500;}
    .bj-side-label {font-size: 0.68rem; font-weight: 700; letter-spacing: 0.12em; text-transform: uppercase; color: var(--bj-muted); margin: 1rem 0 0.4rem 0;}
    .bj-status {display: flex; align-items: center; justify-content: space-between; padding: 0.35rem 0; font-size: 0.85rem; color: TEXT_COLOR;}
    .bj-login-card {text-align:center; padding:1.4rem 1.8rem; border:1px solid var(--bj-line); border-radius:16px; background:var(--bj-surface); color:TEXT_COLOR; box-shadow:0 12px 36px rgba(38,48,31,0.08);}
    .bj-login-card h2 {margin:0; color:TEXT_COLOR; font-weight:800;}
    .bj-login-card p {color:var(--bj-muted); font-size:0.9rem; margin:0.35rem 0 0;}
    .bj-app-version {font-size:0.72rem; color:var(--bj-muted); text-align:center; padding:0.6rem 0;}

    @media (max-width: 768px) {
      .block-container {padding: 1rem 0.75rem 1.5rem; max-width: 100%;}
      .bj-hero {padding: 1rem 1.1rem; border-radius: 12px;}
      .bj-hero h1 {font-size: 1.55rem;}
      div[class*="st-key-card-"] {padding: 1rem;}
      .bj-grid {grid-template-columns: repeat(auto-fit, minmax(145px, 1fr));}
      [data-testid="stTabs"] [role="tablist"] {flex-wrap: wrap; gap: 0.25rem;}
      [data-testid="stTabs"] [role="tab"] {
        flex: 1 1 40%;
        justify-content: center;
        white-space: normal;
        min-height: 2.7rem;
        padding: 0.5rem 0.4rem;
        text-align: center;
      }
      [data-testid="stDataFrame"] {max-width: 100%; overflow-x: auto;}
    }
    </style>
    """
    rendered_css = (
        css.replace("BORDER_COLOR", border_color)
        .replace("BACKGROUND_COLOR", background_color)
        .replace("SIDEBAR_BG", sidebar_bg)
        .replace("COLOR_SCHEME", "dark" if is_dark else "light")
        .replace("ACCENT_COLOR_2", accent_color_2)
        .replace("ACCENT_COLOR", accent_color)
        .replace("SUCCESS_TEXT", "b8d68a" if is_dark else "4d6b27")
        .replace("INFO_TEXT", "b8d68a" if is_dark else "556b2f")
        .replace("SURFACE_BG", surface_bg)
        .replace("MUTED_COLOR", muted_color)
        .replace("TEXT_COLOR", text_color)
        .replace("HERO_BG", hero_bg)
    )
    if system_mode:
        return rendered_css + system_theme_css()
    return rendered_css


def system_theme_css() -> str:
    return """
    <style>
    @media (prefers-color-scheme: dark) {
      :root, .stApp, [data-testid="stAppViewContainer"] {
        color-scheme: dark;
        --background-color: #10150c !important;
        --secondary-background-color: #171e11 !important;
        --text-color: #f3f4f6 !important;
        --border-color: rgba(173, 193, 132, 0.2) !important;
        --bj-accent: #b8d68a;
        --bj-accent-2: #d0e7a2;
        --bj-accent-soft: rgba(184, 214, 138, 0.12);
        --bj-line: rgba(173, 193, 132, 0.2);
        --bj-surface: rgba(255, 255, 255, 0.035);
        --bj-muted: rgba(243, 244, 246, 0.62);
        background: #10150c !important;
        color: #f3f4f6 !important;
      }
      [data-testid="stSidebar"], [data-testid="stHeader"], [data-testid="stToolbar"] {
        background: #171e11 !important;
        color: #f3f4f6 !important;
      }
      .stApp p, .stApp label, .stApp [data-testid="stMarkdownContainer"],
      .stApp [data-testid="stWidgetLabel"], [data-testid="stSidebar"] p,
      [data-testid="stSidebar"] label, [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] {
        color: #f3f4f6 !important;
      }
      .stApp input, .stApp textarea, .stApp [data-baseweb="select"] > div,
      .stApp [data-baseweb="input"] > div, [data-baseweb="popover"],
      [role="listbox"], [role="option"], [data-testid="stFileUploaderDropzone"] {
        background-color: #171e11 !important;
        color: #f3f4f6 !important;
        border-color: rgba(173, 193, 132, 0.2) !important;
      }
      .stApp [data-testid="stTabs"] button[role="tab"] {color: #f3f4f6;}
      .stApp [data-testid="stTabs"] button[role="tab"][aria-selected="true"] {
        color: #b8d68a;
        border-bottom-color: #b8d68a;
      }
      h1, h2, h3, .bj-login-card h2, .bj-brand-name, .bj-kpi-value,
      .bj-sec-title, .bj-tile-value, .bj-empty b {color: #f3f4f6 !important;}
      .bj-login-card, .bj-hero {
        background: linear-gradient(135deg, #10150c 0%, #1b2413 55%, #26351b 100%) !important;
        border-color: rgba(173, 193, 132, 0.2) !important;
        color: #f3f4f6 !important;
      }
      .bj-hero h1 span {
        background: linear-gradient(90deg, #b8d68a, #d0e7a2);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
      }
      .bj-chip, .bj-tile, .bj-kpi, .bj-empty,
      div[class*="st-key-card-"] {
        background-color: rgba(255, 255, 255, 0.035) !important;
        border-color: rgba(173, 193, 132, 0.2) !important;
        color: #f3f4f6 !important;
      }
      .bj-tile-label, .bj-kpi-label, .bj-kpi-hint, .bj-brand-sub,
      .bj-sec-sub, .bj-side-label {color: rgba(243, 244, 246, 0.62) !important;}
      .bj-success, .bj-info {color: #b8d68a !important;}
      [data-testid="stDataFrame"], [data-testid="stTable"] {color-scheme: dark;}
    }
    </style>
    """


def html(markup: str) -> None:
    st.markdown(markup, unsafe_allow_html=True)


def render_app_menu() -> None:
    is_bn = st.session_state.language == "বাংলা"
    _, menu_col = st.columns([9, 1])
    with menu_col:
        with st.popover(
            "⋮",
            help="মেনু" if is_bn else "Menu",
            width="content",
        ):
            st.selectbox(
                "ভাষা" if is_bn else "Language",
                ["বাংলা", "English"],
                key="language",
                format_func=lambda language: (
                    "বাংলা" if language == "বাংলা" else "ইংরেজি"
                )
                if is_bn
                else language,
            )
            st.selectbox(
                "রঙের ধরন" if is_bn else "Appearance",
                ["system", "light", "dark"],
                key="theme_mode",
                format_func=lambda mode: (
                    {
                        "system": "সিস্টেম",
                        "light": "লাইট",
                        "dark": "ডার্ক",
                    }[mode]
                    if is_bn
                    else {
                        "system": "System",
                        "light": "Light",
                        "dark": "Dark",
                    }[mode]
                ),
            )
            menu_section = st.selectbox(
                "আরও" if is_bn else "More",
                ["none", "about", "privacy", "credits", "feedback"],
                key="app_menu_section",
                format_func=lambda section: (
                    {
                        "none": "একটি অপশন বেছে নিন",
                        "about": "অ্যাপ সম্পর্কে",
                        "privacy": "গোপনীয়তা নীতি",
                        "credits": "কৃতিত্ব ও কপিরাইট",
                        "feedback": "মতামত / সমস্যা জানান",
                    }[section]
                    if is_bn
                    else {
                        "none": "Choose an option",
                        "about": "About the app",
                        "privacy": "Privacy policy",
                        "credits": "Credits and copyright",
                        "feedback": "Feedback and report a bug",
                    }[section]
                ),
            )

            if menu_section == "about":
                st.markdown("#### অ্যাপ সম্পর্কে" if is_bn else "#### About the app")
                st.write(
                    "ভূমির নথি থেকে তথ্য যাচাই এবং অ্যাপের জমির রেকর্ড দেখা ও মালিকানা-পরিবর্তনের আবেদন পর্যালোচনার একটি ডেমো অ্যাপ।"
                    if is_bn
                    else "A demo app for checking land-document information, viewing app land records, and reviewing ownership-change requests."
                )
                st.warning(
                    "এটি সরকারি ভূমি-রেজিস্ট্রি নয়; এখানে অনুমোদন সরকারি মালিকানা বদলায় না।"
                    if is_bn
                    else "This is not a government land registry. Approvals here do not change legal ownership."
                )
            elif menu_section == "privacy":
                st.markdown("#### গোপনীয়তা নীতি" if is_bn else "#### Privacy policy")
                st.write(
                    "মালিকানা-পরিবর্তনের আবেদন ও মতামত এই অ্যাপের স্থানীয় SQLite ডাটাবেজে থাকে। লগইন করা ব্যবহারকারীর সার্চের ধরন, দাগ/খতিয়ান নম্বর ও সময়ও সংরক্ষিত হয়; অনুমোদিত কর্মকর্তারা সার্চ ইতিহাস দেখতে পারেন। সম্পূর্ণ OCR লেখা বা আপলোড করা নথি সার্চ ইতিহাসে রাখা হয় না। আবেদন-সংযুক্ত প্রমাণপত্র এনক্রিপ্ট করে রাখা হয় এবং আবেদন শেষ হলে ফাইলটি মুছে ফেলা হয়। নথি যাচাইয়ের OCR-এ Gemini API চালু থাকলে আপলোড করা ছবি Google-এর Gemini সেবায় পাঠানো হতে পারে। সংবেদনশীল নথি আপলোডের আগে অনুমতি ও প্রয়োজনীয়তা যাচাই করুন।"
                    if is_bn
                    else "Ownership applications and feedback are stored in this app's local SQLite database. Search type, plot/khatian numbers, and time are also saved for signed-in users; authorized staff can view search history. Full OCR text and uploaded documents are not stored in search history. Supporting evidence is encrypted and its file is removed when a request is decided. If Gemini OCR is enabled, uploaded document images may be sent to Google's Gemini service. Confirm you are allowed to share a sensitive document before uploading it."
                )
            elif menu_section == "credits":
                st.markdown(
                    "#### কৃতিত্ব ও কপিরাইট" if is_bn else "#### Credits and copyright"
                )
                st.write(
                    f"ভূমিপ্রহরী · সংস্করণ {APP_VERSION}"
                    if is_bn
                    else f"Bhumi Prohori · Version {APP_VERSION}"
                )
                st.caption(
                    "অ্যাপের নাম ও নিজস্ব উপাদান © ২০২৬ ভূমিপ্রহরী। ব্যবহৃত তৃতীয়-পক্ষ সফটওয়্যার ও মানচিত্র-তথ্য নিজ নিজ লাইসেন্সে ব্যবহৃত।"
                    if is_bn
                    else "App name and original materials © 2026 Bhumi Prohori. Third-party software and map data remain under their respective licenses."
                )
            elif menu_section == "feedback":
                st.markdown(
                    "#### মতামত / সমস্যা জানান"
                    if is_bn
                    else "#### Feedback and report a bug"
                )
                st.caption(
                    "বার্তাটি এই অ্যাপের ডাটাবেজে সংরক্ষিত হবে; ব্যক্তিগত বা দলিলের তথ্য লিখবেন না।"
                    if is_bn
                    else "Your message is saved in this app's database. Do not include personal or land-document information."
                )
                with st.form("app-feedback-form"):
                    category = st.selectbox(
                        "ধরন" if is_bn else "Type",
                        ["feedback", "bug"],
                        format_func=lambda item: (
                            {"feedback": "মতামত", "bug": "সমস্যার প্রতিবেদন"}[item]
                            if is_bn
                            else {"feedback": "Feedback", "bug": "Bug report"}[item]
                        ),
                    )
                    message = st.text_area(
                        "আপনার বার্তা" if is_bn else "Your message",
                        max_chars=5000,
                    )
                    submitted = st.form_submit_button(
                        "জমা দিন" if is_bn else "Submit"
                    )
                if submitted:
                    try:
                        save_app_feedback(
                            category,
                            message,
                            st.session_state.get("user_role", "Guest"),
                        )
                        st.success(
                            "ধন্যবাদ, বার্তাটি জমা হয়েছে।"
                            if is_bn
                            else "Thank you. Your message was submitted."
                        )
                    except (ValueError, *DATABASE_ERRORS) as exc:
                        st.error(
                            f"{'বার্তা জমা দেওয়া যায়নি' if is_bn else 'Could not submit message'}: {exc}"
                        )
            html(
                f'<div class="bj-app-version">'
                f'{"ভূমিপ্রহরী" if is_bn else "Bhumi Prohori"} · v{APP_VERSION}</div>'
            )


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


def normalize_digits(text: str) -> str:
    trans = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")
    return str(text).translate(trans)


def en_to_bn_digits(text: str) -> str:
    trans = str.maketrans("0123456789", "০১২৩৪৫৬৭৮৯")
    return str(text).translate(trans)


class PostgresConnection:
    def __init__(self, database_url: str) -> None:
        self._connection = psycopg.connect(
            database_url,
            connect_timeout=10,
            row_factory=dict_row,
        )

    def __enter__(self) -> PostgresConnection:
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        try:
            if exc_type is None:
                self.commit()
            else:
                self.rollback()
        finally:
            self.close()

    def execute(self, sql: str, parameters=()):
        sql = sql.replace(
            "INTEGER PRIMARY KEY AUTOINCREMENT",
            "INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY",
        )
        sql = sql.replace(" BLOB", " BYTEA").replace(" COLLATE NOCASE", "")
        if sql.strip().upper() == "BEGIN IMMEDIATE":
            sql = "BEGIN"
        else:
            sql = sql.replace("?", "%s")
        cursor = self._connection.cursor()
        cursor.execute(sql, parameters)
        return cursor

    def commit(self) -> None:
        self._connection.commit()

    def rollback(self) -> None:
        self._connection.rollback()

    def close(self) -> None:
        self._connection.close()


def ownership_connection() -> sqlite3.Connection | PostgresConnection:
    database_url = postgres_database_url()
    if database_url:
        return PostgresConnection(database_url)

    connection = sqlite3.connect(OWNERSHIP_DB_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA secure_delete = ON")
    return connection


def app_secret(name: str, environment_name: str) -> str | None:
    environment_value = os.environ.get(environment_name)
    if environment_value:
        return environment_value
    try:
        value = st.secrets.get(name)
    except StreamlitSecretNotFoundError:
        return None
    return str(value) if value else None


def postgres_database_url() -> str | None:
    force_sqlite = os.environ.get("LAND_USE_SQLITE", "").strip().casefold()
    if force_sqlite in {"1", "true", "yes"}:
        return None
    return app_secret("DATABASE_URL", "DATABASE_URL")


if (
    not postgres_database_url()
    and os.environ.get("LAND_USE_SQLITE", "").strip().casefold()
    not in {"1", "true", "yes"}
):
    st.warning(
        "Using local SQLite storage. For persistent Streamlit Cloud data, "
        "configure DATABASE_URL in Streamlit Secrets."
    )


def staff_account_hashes() -> dict[str, str]:
    try:
        configured_accounts = st.secrets.get("staff_accounts", {})
    except StreamlitSecretNotFoundError:
        configured_accounts = {}
    if not isinstance(configured_accounts, Mapping):
        return {}
    return {
        str(staff_id).strip(): str(password_hash)
        for staff_id, password_hash in configured_accounts.items()
        if str(staff_id).strip() and isinstance(password_hash, str)
    }


def canonical_staff_id(staff_id: str) -> str | None:
    return next(
        (
            account_id
            for account_id in staff_account_hashes()
            if account_id.casefold() == staff_id.strip().casefold()
        ),
        None,
    )


def verify_staff_credentials(staff_id: str, password: str) -> bool:
    accounts = staff_account_hashes()
    matching_id = canonical_staff_id(staff_id)
    if matching_id is None:
        return False

    try:
        algorithm, rounds_text, salt_hex, digest_hex = accounts[matching_id].split("$")
        rounds = int(rounds_text)
        salt = bytes.fromhex(salt_hex)
        expected_digest = bytes.fromhex(digest_hex)
    except (ValueError, TypeError):
        return False
    if (
        algorithm != "pbkdf2_sha256"
        or rounds < 300_000
        or rounds > 2_000_000
        or len(salt) < 16
        or len(expected_digest) != hashlib.sha256().digest_size
    ):
        return False

    actual_digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        rounds,
        dklen=len(expected_digest),
    )
    return hmac.compare_digest(actual_digest, expected_digest)


def normalize_citizen_identifier(identifier: str) -> str:
    normalized = normalize_digits(identifier).strip().casefold()
    if "@" in normalized:
        if (
            len(normalized) > 254
            or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", normalized)
        ):
            raise ValueError("Enter a valid email address or phone number.")
        return normalized

    if len(normalized) > 20 or not re.fullmatch(r"[0-9+() -]+", normalized):
        raise ValueError("Enter a valid email address or phone number.")
    phone_digits = re.sub(r"\D", "", normalized)
    if not 7 <= len(phone_digits) <= 15:
        raise ValueError("Enter a valid email address or phone number.")
    if len(phone_digits) == 11 and phone_digits.startswith("01"):
        phone_digits = "88" + phone_digits
    return phone_digits


def validate_citizen_password(password: str) -> None:
    if len(password) < 12:
        raise ValueError("Password must be at least 12 characters.")
    if len(password) > 128:
        raise ValueError("Password must be 128 characters or fewer.")


def hash_citizen_password(password: str) -> str:
    validate_citizen_password(password)
    salt = secrets.token_bytes(16)
    rounds = 600_000
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, rounds)
    return f"pbkdf2_sha256${rounds}${salt.hex()}${digest.hex()}"


def verify_password_hash(password_hash: str, password: str) -> bool:
    try:
        algorithm, rounds_text, salt_hex, digest_hex = password_hash.split("$")
        rounds = int(rounds_text)
        salt = bytes.fromhex(salt_hex)
        expected_digest = bytes.fromhex(digest_hex)
    except (ValueError, TypeError):
        return False
    if (
        algorithm != "pbkdf2_sha256"
        or rounds < 300_000
        or rounds > 2_000_000
        or len(salt) < 16
        or len(expected_digest) != hashlib.sha256().digest_size
    ):
        return False
    actual_digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        rounds,
        dklen=len(expected_digest),
    )
    return hmac.compare_digest(actual_digest, expected_digest)


def citizen_identifier_code_digest(
    identifier: str, purpose: str, code: str
) -> str:
    message = f"{purpose}\0{identifier}\0{code}".encode("utf-8")
    return hashlib.sha256(message).hexdigest()


def issue_citizen_demo_code(
    identifier: str,
    purpose: str,
    password_hash: str | None = None,
) -> str:
    if purpose not in {"verify", "reset"}:
        raise ValueError("Unsupported verification-code purpose.")
    normalized_identifier = normalize_citizen_identifier(identifier)
    now = int(time.time())
    code = f"{secrets.randbelow(1_000_000):06d}"
    code_digest = citizen_identifier_code_digest(
        normalized_identifier, purpose, code
    )

    with ownership_connection() as connection:
        connection.execute(
            """
            UPDATE citizen_email_codes SET consumed_at = ?
            WHERE email = ? AND purpose = ? AND consumed_at IS NULL
            """,
            (now, normalized_identifier, purpose),
        )
        connection.execute(
            """
            DELETE FROM citizen_email_codes
            WHERE consumed_at IS NOT NULL OR expires_at < ?
            """,
            (now,),
        )
        connection.execute(
            """
            INSERT INTO citizen_email_codes
                (email, purpose, code_hash, password_hash, created_at, expires_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                normalized_identifier,
                purpose,
                code_digest,
                password_hash,
                now,
                now + 600,
            ),
        )
    return code


def consume_citizen_email_code(
    identifier: str,
    purpose: str,
    code: str,
) -> tuple[bool, str | None]:
    normalized_identifier = normalize_citizen_identifier(identifier)
    cleaned_code = code.strip()
    if not re.fullmatch(r"\d{6}", cleaned_code):
        return False, None
    now = int(time.time())
    with ownership_connection() as connection:
        row = connection.execute(
            """
            SELECT id, code_hash, password_hash, expires_at, attempts
            FROM citizen_email_codes
            WHERE email = ? AND purpose = ? AND consumed_at IS NULL
            ORDER BY id DESC LIMIT 1
            """,
            (normalized_identifier, purpose),
        ).fetchone()
        if row is None:
            return False, None
        if row["expires_at"] < now or row["attempts"] >= 5:
            connection.execute(
                "UPDATE citizen_email_codes SET consumed_at = ? WHERE id = ?",
                (now, row["id"]),
            )
            return False, None

        connection.execute(
            "UPDATE citizen_email_codes SET attempts = attempts + 1 WHERE id = ?",
            (row["id"],),
        )
        submitted_digest = citizen_identifier_code_digest(
            normalized_identifier,
            purpose,
            cleaned_code,
        )
        if not hmac.compare_digest(submitted_digest, row["code_hash"]):
            return False, None

        connection.execute(
            "UPDATE citizen_email_codes SET consumed_at = ? WHERE id = ?",
            (now, row["id"]),
        )
        return True, row["password_hash"]


def citizen_account_exists(identifier: str) -> bool:
    normalized_identifier = normalize_citizen_identifier(identifier)
    with ownership_connection() as connection:
        return (
            connection.execute(
                "SELECT 1 FROM citizen_accounts WHERE email = ?",
                (normalized_identifier,),
            ).fetchone()
            is not None
        )


def register_citizen_account(identifier: str, code: str) -> bool:
    normalized_identifier = normalize_citizen_identifier(identifier)
    code_valid, pending_password_hash = consume_citizen_email_code(
        normalized_identifier,
        "verify",
        code,
    )
    if not code_valid or not pending_password_hash:
        return False
    now = int(time.time())
    try:
        with ownership_connection() as connection:
            connection.execute(
                """
                INSERT INTO citizen_accounts (email, password_hash, created_at, verified_at)
                VALUES (?, ?, ?, ?)
                """,
                (normalized_identifier, pending_password_hash, now, now),
            )
    except DATABASE_INTEGRITY_ERRORS:
        return False
    return True


def verify_citizen_login(identifier: str, password: str) -> bool:
    normalized_identifier = normalize_citizen_identifier(identifier)
    with ownership_connection() as connection:
        account = connection.execute(
            """
            SELECT password_hash FROM citizen_accounts
            WHERE email = ? AND verified_at IS NOT NULL
            """,
            (normalized_identifier,),
        ).fetchone()
    return account is not None and verify_password_hash(
        account["password_hash"],
        password,
    )


def reset_citizen_password(
    identifier: str, code: str, new_password: str
) -> bool:
    normalized_identifier = normalize_citizen_identifier(identifier)
    new_password_hash = hash_citizen_password(new_password)
    if not citizen_account_exists(normalized_identifier):
        return False
    code_valid, _ = consume_citizen_email_code(
        normalized_identifier, "reset", code
    )
    if not code_valid:
        return False
    with ownership_connection() as connection:
        cursor = connection.execute(
            """
            UPDATE citizen_accounts SET password_hash = ?
            WHERE email = ? AND verified_at IS NOT NULL
            """,
            (new_password_hash, normalized_identifier),
        )
    return cursor.rowcount == 1


def active_history_actor() -> tuple[str, str] | None:
    if not st.session_state.get("logged_in"):
        return None
    role = st.session_state.get("user_role")
    if role == "Citizen":
        identifier = st.session_state.get("user_email")
    elif role == "Employee":
        identifier = st.session_state.get("staff_id")
    else:
        return None
    if not identifier:
        return None
    return role, str(identifier)


def record_search_history(
    search_type: str,
    query: str,
    result_count: int | None = None,
) -> None:
    actor = active_history_actor()
    clean_query = query.strip()
    if actor is None or not clean_query:
        return
    actor_role, actor_id = actor
    with ownership_connection() as connection:
        connection.execute(
            """
            INSERT INTO search_history
                (actor_role, actor_id, search_type, query, result_count)
            VALUES (?, ?, ?, ?, ?)
            """,
            (actor_role, actor_id, search_type, clean_query[:500], result_count),
        )


def land_number_history_query(
    plot_number: object = None,
    khatian_number: object = None,
) -> str:
    query_parts = []
    for label, value in (
        ("Plot", plot_number),
        ("Khatian", khatian_number),
    ):
        if value is None:
            continue
        digits = re.sub(r"\D", "", normalize_digits(str(value)))
        if digits and len(digits) <= 40:
            query_parts.append(f"{label} {digits}")
    return " · ".join(query_parts)


def search_history_filters(
    actor_role: str | None = None,
    actor_id: str | None = None,
    identifier_search: str = "",
) -> tuple[str, tuple[object, ...]]:
    conditions = []
    parameters: list[object] = []
    if actor_role:
        conditions.append("actor_role = ?")
        parameters.append(actor_role)
    if actor_id:
        conditions.append("actor_id = ?")
        parameters.append(actor_id)
    clean_identifier_search = identifier_search.strip()
    if clean_identifier_search:
        escaped_search = (
            clean_identifier_search.replace("\\", "\\\\")
            .replace("%", "\\%")
            .replace("_", "\\_")
        )
        conditions.append("actor_id LIKE ? ESCAPE '\\'")
        parameters.append(f"%{escaped_search}%")
    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    return where_clause, tuple(parameters)


def count_search_history(
    actor_role: str | None = None,
    actor_id: str | None = None,
    identifier_search: str = "",
) -> int:
    where_clause, parameters = search_history_filters(
        actor_role,
        actor_id,
        identifier_search,
    )
    with ownership_connection() as connection:
        row = connection.execute(
            f"SELECT COUNT(*) AS total FROM search_history {where_clause}",
            parameters,
        ).fetchone()
    return int(row["total"])


def list_search_history(
    actor_role: str | None = None,
    actor_id: str | None = None,
    identifier_search: str = "",
    limit: int = 100,
    offset: int = 0,
) -> list[sqlite3.Row]:
    where_clause, parameters = search_history_filters(
        actor_role,
        actor_id,
        identifier_search,
    )
    with ownership_connection() as connection:
        return list(
            connection.execute(
                f"""
                SELECT actor_role, actor_id, search_type, query,
                       result_count, searched_at
                FROM search_history
                {where_clause}
                ORDER BY id DESC
                LIMIT ? OFFSET ?
                """,
                (*parameters, max(1, min(limit, 500)), max(0, offset)),
            )
        )


def search_history_frame(
    rows: list[sqlite3.Row],
    is_bn: bool,
    include_actor: bool = False,
) -> pd.DataFrame:
    search_type_labels = {
        "document_ocr": "নথি যাচাই" if is_bn else "Document verification",
        "ownership_lookup": "জমি খোঁজা" if is_bn else "Land lookup",
        "staff_khatian": "খতিয়ান সার্চ" if is_bn else "Khatian search",
    }
    result_rows = []
    for row in rows:
        display_row = {}
        if include_actor:
            display_row["ব্যবহারকারী" if is_bn else "User"] = (
                row["actor_id"]
            )
            display_row["ভূমিকা" if is_bn else "Role"] = (
                "নাগরিক" if is_bn and row["actor_role"] == "Citizen"
                else "কর্মকর্তা" if is_bn
                else row["actor_role"]
            )
        display_row["ধরন" if is_bn else "Type"] = search_type_labels.get(
            row["search_type"],
            row["search_type"],
        )
        display_row["খোঁজের তথ্য" if is_bn else "Search query"] = row["query"]
        if row["result_count"] is not None:
            display_row["ফলাফল" if is_bn else "Results"] = row["result_count"]
        display_row["সময়" if is_bn else "Time"] = row["searched_at"]
        result_rows.append(display_row)
    return pd.DataFrame(result_rows)


def ownership_proof_cipher() -> Fernet:
    key = app_secret("ownership_document_key", "LAND_OWNERSHIP_DOCUMENT_KEY")
    if not key:
        raise ValueError(
            "Set ownership_document_key in Streamlit secrets before accepting applications."
        )
    try:
        return Fernet(key.encode("ascii"))
    except (ValueError, UnicodeEncodeError) as exc:
        raise ValueError("The ownership document encryption key is invalid.") from exc


def validate_ownership_proof(filename: str, proof_data: bytes) -> str:
    suffix = Path(filename).suffix.lower()
    signatures = {
        ".pdf": proof_data.startswith(b"%PDF-"),
        ".png": proof_data.startswith(b"\x89PNG\r\n\x1a\n"),
        ".jpg": proof_data.startswith(b"\xff\xd8\xff"),
        ".jpeg": proof_data.startswith(b"\xff\xd8\xff"),
    }
    if len(proof_data) > OWNERSHIP_PROOF_MAX_BYTES:
        raise ValueError("The supporting document must be 10 MB or smaller.")
    if not proof_data or suffix not in signatures or not signatures[suffix]:
        raise ValueError("Upload a valid PDF, PNG, or JPEG supporting document.")
    return suffix


def load_ownership_proof(request_id: int) -> tuple[str, bytes, str]:
    with ownership_connection() as connection:
        row = connection.execute(
            """
            SELECT proof_filename, proof_ciphertext, proof_sha256
            FROM ownership_changes
            WHERE id = ?
            """,
            (request_id,),
        ).fetchone()
    if row is None or row["proof_ciphertext"] is None:
        raise ValueError("No supporting document is attached to this application.")
    try:
        proof_data = ownership_proof_cipher().decrypt(row["proof_ciphertext"])
    except InvalidToken as exc:
        raise ValueError("The supporting document failed its integrity check.") from exc
    if not hmac.compare_digest(
        hashlib.sha256(proof_data).hexdigest(),
        row["proof_sha256"],
    ):
        raise ValueError("The supporting document failed its integrity check.")
    return row["proof_filename"], proof_data, row["proof_sha256"]


def initialize_ownership_database() -> None:
    is_postgres = bool(postgres_database_url())
    if not is_postgres:
        OWNERSHIP_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with ownership_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS ownership_changes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plot_no TEXT NOT NULL,
                khatian_no TEXT NOT NULL,
                previous_owner_en TEXT NOT NULL,
                previous_owner_bn TEXT NOT NULL,
                new_owner_en TEXT NOT NULL,
                new_owner_bn TEXT NOT NULL,
                contact_number TEXT NOT NULL,
                deed_number TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'approved', 'rejected')),
                requested_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                reviewed_at TEXT,
                reviewed_by TEXT,
                proof_filename TEXT,
                proof_ciphertext BLOB,
                proof_sha256 TEXT
            )
            """
        )
        if is_postgres:
            existing_columns = {
                row["column_name"]
                for row in connection.execute(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = current_schema()
                        AND table_name = 'ownership_changes'
                    """
                )
            }
        else:
            existing_columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(ownership_changes)")
            }
        for column_name, column_type in (
            ("proof_filename", "TEXT"),
            ("proof_ciphertext", "BLOB"),
            ("proof_sha256", "TEXT"),
        ):
            if column_name not in existing_columns:
                connection.execute(
                    f"ALTER TABLE ownership_changes ADD COLUMN {column_name} {column_type}"
                )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS ownership_reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id INTEGER NOT NULL REFERENCES ownership_changes(id),
                reviewer_id TEXT NOT NULL,
                decision TEXT NOT NULL CHECK (decision IN ('approved', 'rejected')),
                deed_checked INTEGER NOT NULL CHECK (deed_checked IN (0, 1)),
                identity_checked INTEGER NOT NULL CHECK (identity_checked IN (0, 1)),
                ownership_checked INTEGER NOT NULL CHECK (ownership_checked IN (0, 1)),
                verification_notes TEXT NOT NULL,
                reviewed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (request_id, reviewer_id)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS app_feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL CHECK (category IN ('feedback', 'bug')),
                message TEXT NOT NULL,
                user_role TEXT NOT NULL,
                app_version TEXT NOT NULL,
                submitted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS citizen_accounts (
                email TEXT PRIMARY KEY COLLATE NOCASE,
                password_hash TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                verified_at INTEGER
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS citizen_email_codes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL COLLATE NOCASE,
                purpose TEXT NOT NULL CHECK (purpose IN ('verify', 'reset')),
                code_hash TEXT NOT NULL,
                password_hash TEXT,
                created_at INTEGER NOT NULL,
                expires_at INTEGER NOT NULL,
                attempts INTEGER NOT NULL DEFAULT 0,
                consumed_at INTEGER
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS search_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                actor_role TEXT NOT NULL CHECK (actor_role IN ('Citizen', 'Employee')),
                actor_id TEXT NOT NULL,
                search_type TEXT NOT NULL,
                query TEXT NOT NULL,
                result_count INTEGER,
                searched_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS search_history_actor_time
            ON search_history (actor_role, actor_id, id DESC)
            """
        )
        connection.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS one_pending_transfer_per_plot
            ON ownership_changes (plot_no, khatian_no)
            WHERE status = 'pending'
            """
        )


def save_app_feedback(category: str, message: str, user_role: str) -> None:
    if category not in {"feedback", "bug"}:
        raise ValueError("Choose feedback or bug report.")
    clean_message = message.strip()
    if len(clean_message) < 10:
        raise ValueError("Please describe the feedback or issue in at least 10 characters.")
    if len(clean_message) > 5000:
        raise ValueError("Feedback must be 5000 characters or fewer.")
    with ownership_connection() as connection:
        connection.execute(
            """
            INSERT INTO app_feedback (category, message, user_role, app_version)
            VALUES (?, ?, ?, ?)
            """,
            (category, clean_message, user_role, APP_VERSION),
        )


def list_app_feedback() -> list[sqlite3.Row]:
    with ownership_connection() as connection:
        return list(
            connection.execute(
                """
                SELECT category, message, user_role, app_version, submitted_at
                FROM app_feedback
                ORDER BY id DESC
                LIMIT 200
                """
            ).fetchall()
        )


def find_land_record(plot_no: str, khatian_no: str) -> dict | None:
    geojson_path = land_geojson_path()
    with geojson_path.open("r", encoding="utf-8") as source:
        data = json.load(source)

    normalized_plot = normalize_digits(plot_no).strip()
    normalized_khatian = normalize_digits(khatian_no).strip()
    for feature in data.get("features", []):
        properties = feature.get("properties", {})
        feature_plot = normalize_digits(
            str(properties.get("plot_no") or properties.get("plot_number") or "")
        ).strip()
        feature_khatian = normalize_digits(str(properties.get("khatian_no") or "")).strip()
        if feature_plot == normalized_plot and feature_khatian == normalized_khatian:
            return properties
    return None


def find_land_record_by_plot(plot_no: str) -> dict | None:
    geojson_path = land_geojson_path()
    with geojson_path.open("r", encoding="utf-8") as source:
        data = json.load(source)

    normalized_plot = normalize_digits(plot_no).strip()
    for feature in data.get("features", []):
        properties = feature.get("properties", {})
        feature_plot = normalize_digits(
            str(properties.get("plot_no") or properties.get("plot_number") or "")
        ).strip()
        if feature_plot == normalized_plot:
            return properties
    return None


def find_land_records_by_khatian(khatian_no: str) -> list[dict]:
    normalized_khatian = normalize_digits(khatian_no).strip()
    if not normalized_khatian:
        return []

    geojson_path = land_geojson_path()
    with geojson_path.open("r", encoding="utf-8") as source:
        data = json.load(source)

    return [
        feature.get("properties", {})
        for feature in data.get("features", [])
        if normalize_digits(
            str(feature.get("properties", {}).get("khatian_no") or "")
        ).strip()
        == normalized_khatian
    ]


def extract_document_fields(ocr_text: str) -> dict[str, str]:
    field_labels = {
        "plot": r"(?:plot|parcel|dag|দাগ)",
        "khatian_type": r"(?:khatian\s*type|খতিয়ান\s*(?:এর\s*)?ধরন|খতিয়ান\s*(?:এর\s*)?ধরন)",
        "khatian": r"(?:khatian(?!\s*type)|খতিয়ান|খতিয়ান)",
        "owner": r"(?:owner(?:'s)?\s*name|owner|মালিক(?:ের)?\s*নাম)",
        "mouza": r"(?:mouza|মৌজা)",
        "jl_no": r"(?:j\.?\s*l\.?\s*(?:no\.?|number)?|জে\s*\.?\s*এল\.?\s*(?:নং|নম্বর)?)",
        "land_type": r"(?:land\s*(?:class|type)|জমির\s*শ্রেণি)",
        "district": r"(?:district|জেলা)",
        "declared_area": r"(?:declared\s*area|area|জমির\s*পরিমাণ|পরিমাণ)",
    }
    matches = []
    for field, label_pattern in field_labels.items():
        match = re.compile(
            rf"(?im)^\s*(?:{label_pattern})"
            rf"(?:\s*(?:no\.?|number|নং|নম্বর))?\s*[:：#\-]?\s*(.*?)\s*$"
        )
        matches.append((field, match))

    extracted: dict[str, str] = {}
    for line in normalize_digits(ocr_text).splitlines():
        clean_line = line.strip()
        if not clean_line:
            continue
        for field, pattern in matches:
            match = pattern.match(clean_line)
            if match and match.group(1).strip():
                extracted[field] = match.group(1).strip(" \t:：#-")
                break
    return extracted


def ocr_database_field_comparison(
    ocr_fields: dict[str, str],
    properties: dict,
    display_fields: dict,
    is_bn: bool,
) -> tuple[list[tuple[str, str, str]], int, int]:
    checks = [
        ("plot", "plot_no" if "plot_no" in properties else "plot_number"),
        ("khatian", "khatian_no"),
        ("owner", "owner_name"),
        ("mouza", "mouza"),
        ("jl_no", "jl_no"),
        ("khatian_type", "khatian_type"),
        ("land_type", "land_type"),
        ("district", "district"),
        ("declared_area", "declared_area"),
    ]
    labels = {
        "plot": "দাগ নম্বর" if is_bn else "Plot number",
        "khatian": "খতিয়ান নম্বর" if is_bn else "Khatian number",
        "owner": "মালিকের নাম" if is_bn else "Owner name",
        "mouza": "মৌজার নাম" if is_bn else "Mouza",
        "jl_no": "জে.এল. নম্বর" if is_bn else "J.L. number",
        "khatian_type": "খতিয়ানের ধরন" if is_bn else "Khatian type",
        "land_type": "জমির শ্রেণি" if is_bn else "Land class",
        "district": "জেলা" if is_bn else "District",
        "declared_area": "জমির পরিমাণ" if is_bn else "Declared area",
    }

    def normalize_value(value: str) -> str:
        return re.sub(
            r"[^\w]",
            "",
            normalize_digits(str(value)).casefold(),
            flags=re.UNICODE,
        )

    mismatches = []
    matched_count = 0
    checked_count = 0

    for field_key, property_key in checks:
        ocr_value = ocr_fields.get(field_key)
        if not ocr_value:
            continue

        values = [display_fields.get(field_key), properties.get(property_key)]
        if field_key == "owner":
            owner_en, owner_bn = get_current_owner(
                str(properties.get("plot_no") or properties.get("plot_number") or ""),
                str(properties.get("khatian_no") or ""),
                str(properties.get("owner_name") or ""),
                str(properties.get("owner_name_bn") or properties.get("owner_name") or ""),
            )
            values = [display_fields.get(field_key), owner_en, owner_bn]
        elif field_key == "plot":
            values.extend(
                [properties.get("plot_no"), properties.get("plot_number")]
            )
        elif field_key == "khatian":
            values.append(properties.get("khatian_no"))
        elif field_key == "mouza":
            values.extend([properties.get("mouza"), properties.get("mouza_bn")])

        expected_values = list(
            dict.fromkeys(
                str(value).strip()
                for value in values
                if value is not None and str(value).strip()
            )
        )
        if not expected_values:
            continue

        checked_count += 1
        if any(
            normalize_value(ocr_value) == normalize_value(expected)
            for expected in expected_values
        ):
            matched_count += 1
        else:
            mismatches.append((labels[field_key], ocr_value, expected_values[0]))

    return mismatches, matched_count, checked_count


def get_current_owner(
    plot_no: str,
    khatian_no: str,
    default_owner_en: str,
    default_owner_bn: str,
) -> tuple[str, str]:
    with ownership_connection() as connection:
        row = connection.execute(
            """
            SELECT new_owner_en, new_owner_bn
            FROM ownership_changes
            WHERE plot_no = ? AND khatian_no = ? AND status = 'approved'
            ORDER BY id DESC
            LIMIT 1
            """,
            (normalize_digits(plot_no).strip(), normalize_digits(khatian_no).strip()),
        ).fetchone()
    if row:
        return row["new_owner_en"], row["new_owner_bn"]
    return default_owner_en, default_owner_bn


def create_ownership_request(
    properties: dict,
    new_owner_en: str,
    new_owner_bn: str,
    contact_number: str,
    deed_number: str,
    proof_filename: str,
    proof_data: bytes,
) -> None:
    plot_no = normalize_digits(
        str(properties.get("plot_no") or properties.get("plot_number") or "")
    ).strip()
    khatian_no = normalize_digits(str(properties.get("khatian_no") or "")).strip()
    if not plot_no or not khatian_no:
        raise ValueError("The selected land record is missing its plot or khatian number.")
    current_owner_en, current_owner_bn = get_current_owner(
        plot_no,
        khatian_no,
        str(properties.get("owner_name") or ""),
        str(properties.get("owner_name_bn") or properties.get("owner_name") or ""),
    )
    if (
        current_owner_en.casefold() == new_owner_en.casefold()
        and current_owner_bn == new_owner_bn
    ):
        raise ValueError("The new owner must be different from the current owner.")
    proof_suffix = validate_ownership_proof(proof_filename, proof_data)
    proof_ciphertext = ownership_proof_cipher().encrypt(proof_data)
    proof_sha256 = hashlib.sha256(proof_data).hexdigest()

    try:
        with ownership_connection() as connection:
            connection.execute(
                """
                INSERT INTO ownership_changes (
                    plot_no, khatian_no, previous_owner_en, previous_owner_bn,
                    new_owner_en, new_owner_bn, contact_number, deed_number,
                    proof_filename, proof_ciphertext, proof_sha256
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    plot_no,
                    khatian_no,
                    current_owner_en,
                    current_owner_bn,
                    new_owner_en.strip(),
                    new_owner_bn.strip(),
                    contact_number.strip(),
                    deed_number.strip(),
                    f"proof{proof_suffix}",
                    proof_ciphertext,
                    proof_sha256,
                ),
            )
    except DATABASE_INTEGRITY_ERRORS as exc:
        raise ValueError(
            "A pending ownership application already exists for this land record."
        ) from exc


def list_ownership_requests(status: str | None = None) -> list[sqlite3.Row]:
    query = """
        SELECT id, plot_no, khatian_no, previous_owner_en,
            previous_owner_bn, new_owner_en, new_owner_bn, contact_number,
            deed_number, status, requested_at, reviewed_at, reviewed_by,
            proof_filename, proof_sha256
        FROM ownership_changes
    """
    parameters: tuple[str, ...] = ()
    if status is not None:
        query += " WHERE ownership_changes.status = ?"
        parameters = (status,)
    query += " ORDER BY id DESC"
    with ownership_connection() as connection:
        return list(connection.execute(query, parameters).fetchall())


def list_ownership_reviews(request_id: int) -> list[sqlite3.Row]:
    with ownership_connection() as connection:
        return list(
            connection.execute(
                """
                SELECT reviewer_id, decision, deed_checked, identity_checked,
                    ownership_checked, verification_notes, reviewed_at
                FROM ownership_reviews
                WHERE request_id = ?
                ORDER BY id
                """,
                (request_id,),
            ).fetchall()
        )


def review_ownership_request(
    request_id: int,
    decision: str,
    reviewer: str,
    deed_checked: bool,
    identity_checked: bool,
    ownership_checked: bool,
    verification_notes: str,
) -> str:
    if decision not in {"approved", "rejected"}:
        raise ValueError("Review status must be approved or rejected.")
    if not reviewer.strip():
        raise ValueError("An authenticated reviewer is required.")
    canonical_reviewer = canonical_staff_id(reviewer)
    if canonical_reviewer is None:
        raise ValueError("The reviewer is not a configured staff account.")
    reviewer = canonical_reviewer
    configured_reviewers = staff_account_hashes()
    if decision == "approved" and len(
        {staff_id.casefold() for staff_id in configured_reviewers}
    ) < 2:
        raise ValueError("Two separately configured staff accounts are required.")
    if len(verification_notes.strip()) < 20:
        raise ValueError("Add at least 20 characters explaining the review outcome.")
    if decision == "approved" and not all(
        (deed_checked, identity_checked, ownership_checked)
    ):
        raise ValueError("All verification checks must pass before a review approval.")

    connection = ownership_connection()
    original_geojson: str | None = None
    geojson_path: Path | None = None
    try:
        connection.execute("BEGIN IMMEDIATE")
        request_query = (
            "SELECT * FROM ownership_changes WHERE id = ? AND status = 'pending'"
        )
        if isinstance(connection, PostgresConnection):
            request_query += " FOR UPDATE"
        request = connection.execute(
            request_query,
            (request_id,),
        ).fetchone()
        if request is None:
            raise ValueError("This application has already been reviewed.")

        if decision == "approved":
            if not request["proof_ciphertext"] or not request["proof_sha256"]:
                raise ValueError(
                    "This application has no supporting document and cannot be approved."
                )
            try:
                proof_data = ownership_proof_cipher().decrypt(request["proof_ciphertext"])
            except InvalidToken as exc:
                raise ValueError("The supporting document failed its integrity check.") from exc
            if not hmac.compare_digest(
                hashlib.sha256(proof_data).hexdigest(),
                request["proof_sha256"],
            ):
                raise ValueError("The supporting document failed its integrity check.")

        prior_review = connection.execute(
            """
            SELECT reviewer_id FROM ownership_reviews
            WHERE request_id = ? AND reviewer_id = ?
            """,
            (request_id, reviewer.strip()),
        ).fetchone()
        if prior_review:
            raise ValueError("A reviewer cannot review the same application twice.")
        approval_count = connection.execute(
            """
            SELECT COUNT(*) AS count FROM ownership_reviews
            WHERE request_id = ? AND decision = 'approved'
            """,
            (request_id,),
        ).fetchone()["count"]
        if approval_count >= 2:
            raise ValueError("This application already has two approvals.")

        connection.execute(
            """
            INSERT INTO ownership_reviews (
                request_id, reviewer_id, decision, deed_checked,
                identity_checked, ownership_checked, verification_notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                request_id,
                reviewer.strip(),
                decision,
                int(deed_checked),
                int(identity_checked),
                int(ownership_checked),
                verification_notes.strip(),
            ),
        )

        next_status = "pending"
        if decision == "rejected":
            next_status = "rejected"
        elif approval_count == 1:
            next_status = "approved"

        if next_status == "approved":
            geojson_path = land_geojson_path()
            original_geojson = geojson_path.read_text(encoding="utf-8")
            data = json.loads(original_geojson)
            feature_found = False
            for feature in data.get("features", []):
                properties = feature.get("properties", {})
                feature_plot = normalize_digits(
                    str(properties.get("plot_no") or properties.get("plot_number") or "")
                ).strip()
                feature_khatian = normalize_digits(
                    str(properties.get("khatian_no") or "")
                ).strip()
                if (
                    feature_plot == normalize_digits(request["plot_no"]).strip()
                    and feature_khatian == normalize_digits(request["khatian_no"]).strip()
                ):
                    properties["owner_name"] = request["new_owner_en"]
                    properties["owner_name_bn"] = request["new_owner_bn"]
                    feature_found = True
                    break
            if not feature_found:
                raise ValueError("The land record no longer exists in the GeoJSON.")

            temporary_path = geojson_path.with_name(f"{geojson_path.name}.tmp")
            temporary_path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            os.replace(temporary_path, geojson_path)

        connection.execute(
            """
            UPDATE ownership_changes
            SET status = ?, reviewed_at = CURRENT_TIMESTAMP, reviewed_by = ?,
                proof_ciphertext = CASE WHEN ? = 'pending' THEN proof_ciphertext ELSE NULL END
            WHERE id = ?
            """,
            (next_status, reviewer.strip(), next_status, request_id),
        )
        connection.commit()
        return next_status
    except Exception:
        connection.rollback()
        if original_geojson is not None and geojson_path is not None:
            restore_path = geojson_path.with_name(f"{geojson_path.name}.restore.tmp")
            restore_path.write_text(original_geojson, encoding="utf-8")
            os.replace(restore_path, geojson_path)
        raise
    finally:
        connection.close()


def load_plot_from_geojson(plot_no: str | int, lang: str = "বাংলা"):
    if not plot_no:
        return None, None
    try:
        geojson_path = land_geojson_path()
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
                        raw_owner, raw_owner_bn = get_current_owner(
                            str(raw_pno),
                            raw_khatian,
                            str(raw_owner),
                            str(raw_owner_bn),
                        )
                        
                        raw_mouza = props.get("mouza", "Mirpur")
                        raw_mouza_bn = props.get("mouza_bn", raw_mouza)
                        raw_district = props.get("district", "Dhaka")
                        raw_upazila = props.get("upazila", "")
                        raw_jl = str(props.get("jl_no") or "")
                        raw_khatian_type = props.get("khatian_type", "RS")
                        raw_land_type = props.get("land_type", "Nal")

                        district_bn_map = {
                            "Dhaka": "ঢাকা", "Gazipur": "গাজীপুর", "Narayanganj": "নারায়ণগঞ্জ", "Tangail": "টাঙ্গাইল",
                            "Faridpur": "ফরিদপুর", "Manikganj": "মানিকগঞ্জ", "Munshiganj": "মুন্সিগঞ্জ", "Narsingdi": "নরসিংদী", 
                            "Rajbari": "রাজবাড়ী", "Gopalganj": "গোপালগঞ্জ", "Madaripur": "মাদারীপুর", "Shariatpur": "শরীয়তপুর",
                            "Kishoreganj": "কিশোরগঞ্জ", "Chattogram": "চট্টগ্রাম", "Cox's Bazar": "কক্সবাজার", "Cumilla": "কুমিল্লা", 
                            "Feni": "ফেনী", "Noakhali": "নোয়াখালী", "Lakshmipur": "লক্ষ্মীপুর", "Brahmanbaria": "ব্রাহ্মণবাড়িয়া",
                            "Chandpur": "চাঁদপুর", "Khagrachhari": "খাগড়াছড়ি", "Rangamati": "রাঙ্গামাটি", "Bandarban": "বান্দরবান",
                            "Rajshahi": "রাজশাহী", "Bogra": "বগুড়া", "Pabna": "পাবনা", "Sirajganj": "সিরাজগঞ্জ",
                            "Naogaon": "নওগাঁ", "Natore": "নাটোর", "Chapai Nawabganj": "চাঁপাইনবাবগঞ্জ", "Joypurhat": "জয়পুরহাট",
                            "Khulna": "খুলনা", "Jashore": "যশোর", "Kushtia": "কুষ্টিয়া", "Satkhira": "সাতক্ষীরা",
                            "Bagerhat": "বাগেরহাট", "Jhenaidah": "ঝিনাইদহ", "Chuadanga": "চুয়াডাঙ্গা", "Meherpur": "মেহেরপুর",
                            "Narail": "নড়াইল", "Magura": "মাগুরা", "Barishal": "বরিশাল", "Bhola": "ভোলা",
                            "Patuakhali": "পটুয়াখালী", "Pirojpur": "পিরোজপুর", "Barguna": "বরগুনা", "Jhalokati": "ঝালকাঠি",
                            "Sylhet": "সিলেট", "Moulvibazar": "মৌলভীবাজার", "Habiganj": "হবিগঞ্জ", "Sunamganj": "সুনামগঞ্জ", 
                            "Nilphamari": "নীলফামারী", "Dinajpur": "দিনাজপুর", "Gaibandha": "গাইবান্ধা", "Kurigram": "কুড়িগ্রাম",
                            "Lalmonirhat": "লালমনিরহাট", "Panchagarh": "পঞ্চগড়", "Thakurgaon": "ঠাকুরগাঁও", "Mymensingh": "ময়মনসিংহ",
                            "Jamalpur": "জামালপুর", "Netrokona": "নেত্রকোনা", "Sherpur": "শেরপুর"
                        }

                        mouza_bn_map = {
                            "Mirpur": "মিরপুর", "Sadar": "সদর", "Tongi": "টঙ্গী", "Siddhirganj": "সিদ্ধিরগঞ্জ", 
                            "Goalchamat": "গোয়ালচামত", "Singair": "সিঙ্গাইর", "Garia": "গাড়িয়া", "Panchdona": "পাঁচদোনা",
                            "Pangsha": "পাংশা", "Tungipara": "টুঙ্গিপাড়া", "Rajoir": "রাজৈর", "Naria": "নড়িয়া",
                            "Bhairab": "ভৈরব", "Agrabad": "আগ্রাবাদ", "Ramua": "রামু", "Kandirpar": "কান্দিরপাড়",
                            "Dagonbhuiyan": "দাগনভূঞা", "Maijdee": "মাইজদী", "Raipur": "রায়পুর", "Ashuganj": "আশুগঞ্জ",
                            "Hajiganj": "হাজীগঞ্জ", "Dighinala": "দীঘিনালা", "Kaptai": "কাপ্তাই", "Thanchi": "থানচি", 
                            "Boalia": "বোয়ালিয়া", "Sherpur": "শেরপুর", "Ishwardi": "ঈশ্বরদী", "Ullapara": "উল্লাপাড়া",
                            "Dhamoirhat": "ধামইরহাট", "Baraigram": "বড়াইগ্রাম", "Shibganj": "শিবগঞ্জ", "Akkelpur": "আক্কেলপুর",
                            "Khalishpur": "খালিশপুর", "Jhikargachha": "ঝিকরগাছা", "Bheramara": "ভেড়ামারা", "Kalaroa": "কলারোয়া",
                            "Mongla": "মংলা", "Kaliganj": "কালীগঞ্জ", "Damurhuda": "দামুড়হুদা", "Gangni": "গাংনী",
                            "Lohagara": "লোহাগাড়া", "Shripur": "শ্রীপুর", "Agailjhara": "আগৈলঝাড়া", "Char Fasson": "চরফ্যাশন",
                            "Kuakata": "কুয়াকাটা", "Bhandaria": "ভাণ্ডারিয়া", "Amtali": "আমতলী", "Nalchity": "নলছিটি",
                            "Zindabazar": "জিন্দাবাজার", "Sreemangal": "শ্রীমঙ্গল", "Madhabpur": "মাধবপুর", "Tahirpur": "তাহিরপুর", 
                            "Pirganj": "পীরগঞ্জ", "Chilahati": "চিলাহাটি", "Birganj": "বীরগঞ্জ", "Gobindaganj": "গোবিন্দগঞ্জ", 
                            "Nageswari": "নাগেশ্বরী", "Patgram": "পাটগ্রাম", "Tetulia": "তেঁতুলিয়া", "Muktagachha": "মুক্তাগাছা", 
                            "Sarbari": "সরবারি", "Durgapur": "দুর্গাপুর", "Nalitabari": "নালিতাবাড়ী"
                        }

                        pno_disp = en_to_bn_digits(raw_pno) if is_bn else raw_pno
                        khatian_disp = en_to_bn_digits(raw_khatian) if is_bn else raw_khatian
                        owner_disp = raw_owner_bn if is_bn else raw_owner

                        if is_bn:
                            mouza_disp = raw_mouza_bn or mouza_bn_map.get(
                                raw_mouza, raw_mouza
                            )
                            district_disp = district_bn_map.get(raw_district, raw_district)
                            jl_disp = en_to_bn_digits(raw_jl)
                        else:
                            mouza_disp = raw_mouza
                            district_disp = raw_district
                            jl_disp = raw_jl
                        upazila_disp = props.get("upazila_bn", raw_upazila)

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
                            "upazila": upazila_disp,
                            "jl_no": jl_disp,
                            "khatian_type": khatian_type_disp,
                            "land_type": land_type_disp,
                            "district": district_disp,
                            "declared_area": area_disp,
                            "lat": center_lat,
                            "lon": center_lon,
                            "area_sqm": 566.0,
                        }
    except DATABASE_ERRORS:
        raise
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
        model = genai.GenerativeModel("gemini-3.8-flash")
        prompt = (
            "Transcribe the land record exactly. Put each labeled value on its own line "
            "using these labels when present: Plot, Khatian, Owner Name, Mouza, J.L. No, "
            "Khatian Type, Land Class, District, Declared Area. Do not infer or correct "
            "values; leave out labels that are unreadable."
        )
        response = model.generate_content([prompt, image])
        return response.text.strip()
    except Exception:
        return ""


def match_ocr_text_to_land_records(
    ocr_text: str,
    lang: str,
) -> tuple[dict | None, list[dict], dict[str, str], dict | None]:
    extracted_fields = extract_document_fields(ocr_text)
    khatian_number = extracted_fields.get("khatian")
    plot_number = extracted_fields.get("plot")
    candidate_records: list[dict] = []

    if khatian_number:
        candidate_records = find_land_records_by_khatian(khatian_number)
        if plot_number:
            normalized_plot = normalize_digits(plot_number).strip()
            plot_candidates = [
                properties
                for properties in candidate_records
                if normalize_digits(
                    str(properties.get("plot_no") or properties.get("plot_number") or "")
                ).strip()
                == normalized_plot
            ]
            if plot_candidates:
                candidate_records = plot_candidates
        if len(candidate_records) == 1:
            properties = candidate_records[0]
            _, display_fields = load_plot_from_geojson(
                str(properties.get("plot_no") or properties.get("plot_number") or ""),
                lang=lang,
            )
            return properties, candidate_records, extracted_fields, display_fields
        return None, candidate_records, extracted_fields, None

    if plot_number:
        properties = find_land_record_by_plot(plot_number)
        if properties:
            _, display_fields = load_plot_from_geojson(plot_number, lang=lang)
            return properties, [properties], extracted_fields, display_fields

    return None, candidate_records, extracted_fields, None


def process_hybrid_pipeline(image: Image.Image, lang: str = "বাংলা") -> dict:
    local_text = run_local_ocr(image)
    properties, candidates, ocr_fields, fields = match_ocr_text_to_land_records(
        local_text,
        lang,
    )
    if properties and fields and fields.get("lat") is not None:
        return {
            "text": local_text,
            "engine": "Local Fast OCR (Tesseract)",
            "fields": fields,
            "ocr_fields": ocr_fields,
            "matched_properties": properties,
        }

    deep_ai_text = run_deep_ai_vision(image)
    ai_properties, ai_candidates, ai_ocr_fields, ai_fields = match_ocr_text_to_land_records(
        deep_ai_text,
        lang,
    )
    if ai_properties and ai_fields and ai_fields.get("lat") is not None:
        return {
            "text": deep_ai_text,
            "engine": "Deep AI Vision (Gemini 3.8 Flash)",
            "fields": ai_fields,
            "ocr_fields": ai_ocr_fields,
            "matched_properties": ai_properties,
        }

    not_found_fields = {
        "plot": None,
        "khatian": None,
        "owner": None,
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
    selected_text = local_text or deep_ai_text
    return {
        "text": selected_text,
        "engine": "Database Match Failed",
        "fields": not_found_fields,
        "ocr_fields": ocr_fields if local_text else ai_ocr_fields,
        "candidate_records": (
            candidates
            if local_text and candidates
            else ai_candidates
        ),
    }


initialize_ownership_database()


# --- SESSION STATE INITIALIZATION FOR LOGIN & APP ---
for key, default in {
    "logged_in": False,
    "user_role": "Citizen",
    "language": "বাংলা",
    "result": None,
    "file_sig": None,
    "docs_processed": 0,
    "lat": 23.8103,
    "lon": 90.4125,
}.items():
    st.session_state.setdefault(key, default)

if "theme_mode" not in st.session_state:
    previous_theme = str(st.session_state.get("theme", "Light ☀️"))
    st.session_state.theme_mode = (
        "dark"
        if previous_theme.startswith("Dark")
        else "light"
        if previous_theme.startswith("Light")
        else "light"
    )
st.session_state.pop("theme", None)


# --- LOGIN SCREEN ---
if not st.session_state.logged_in:
    render_app_menu()
    selected_lang = st.session_state.language
    is_bn = selected_lang == "বাংলা"
    is_dark = st.session_state.theme_mode == "dark"
    st.markdown(
        get_css(is_dark, system_mode=st.session_state.theme_mode == "system"),
        unsafe_allow_html=True,
    )

    _, col2, _ = st.columns([1, 1.5, 1])
    with col2:
        html(
            '<div class="bj-login-card">'
            f'<img src="{APP_ICON_DATA_URI}" alt="ভূমিপ্রহরী" '
            'style="width:76px;height:76px;object-fit:contain;margin-bottom:0.35rem;">'
            f'<h2>{"ভূমিপ্রহরী" if is_bn else "Bhumi Prohori"}</h2>'
            f'<p>{"ভূমি রেকর্ড যাচাই" if is_bn else "Land Records & Verification"}</p>'
            '</div>'
        )

        tab_cit, tab_emp = st.tabs(
            ["নাগরিক" if is_bn else "Citizen", "কর্মকর্তা" if is_bn else "Staff"]
        )

        with tab_cit:
            st.markdown("### নাগরিক পোর্টাল" if is_bn else "Citizen portal")
            citizen_auth_tab_labels = [
                "লগইন" if is_bn else "Sign in",
                "নিবন্ধন" if is_bn else "Register",
                "পাসওয়ার্ড ভুলে গেছি" if is_bn else "Forgot password",
            ]
            default_citizen_auth_tab = st.session_state.pop(
                "citizen_auth_default_tab",
                citizen_auth_tab_labels[0],
            )
            citizen_login_tab, citizen_register_tab, citizen_reset_tab = st.tabs(
                citizen_auth_tab_labels,
                default=default_citizen_auth_tab,
            )

            with citizen_login_tab:
                if st.session_state.pop("citizen_registration_complete", False):
                    st.success(
                        "নিবন্ধন সম্পন্ন হয়েছে। এখন ইমেইল/নম্বর ও পাসওয়ার্ড দিয়ে লগইন করুন।"
                        if is_bn
                        else "Registration complete. Sign in with your email or phone number and password."
                    )
                with st.form("citizen_login_form"):
                    citizen_identifier = st.text_input(
                        "ইমেইল অথবা মোবাইল নম্বর" if is_bn else "Email or phone number",
                        key="citizen_login_email",
                        autocomplete="username",
                    )
                    citizen_password = st.text_input(
                        "পাসওয়ার্ড" if is_bn else "Password",
                        type="password",
                        key="citizen_login_password",
                        autocomplete="current-password",
                    )
                    login_submitted = st.form_submit_button(
                        "লগইন" if is_bn else "Sign in",
                        type="primary",
                        width="stretch",
                    )
                if login_submitted:
                    try:
                        normalized_identifier = normalize_citizen_identifier(
                            citizen_identifier
                        )
                        authenticated = verify_citizen_login(
                            normalized_identifier,
                            citizen_password,
                        )
                    except ValueError as exc:
                        st.error(
                            "সঠিক ইমেইল ঠিকানা অথবা মোবাইল নম্বর লিখুন।"
                            if is_bn
                            else str(exc)
                        )
                    else:
                        if authenticated:
                            st.session_state.logged_in = True
                            st.session_state.user_role = "Citizen"
                            st.session_state.user_email = normalized_identifier
                            st.rerun()
                        else:
                            st.error(
                                "ইমেইল/নম্বর বা পাসওয়ার্ড ভুল, অথবা অ্যাকাউন্ট যাচাই করা হয়নি।"
                                if is_bn
                                else "Email/phone or password is incorrect, or the account is not verified."
                            )

            with citizen_register_tab:
                st.caption(
                    "ডেমোতে যাচাইকরণ কোড স্ক্রিনেই দেখানো হবে; কোনো ইমেইল বা SMS পাঠানো হবে না।"
                    if is_bn
                    else "Demo mode: the verification code is shown here; no email or SMS is sent."
                )
                with st.form("citizen_register_request_form"):
                    register_identifier = st.text_input(
                        "ইমেইল অথবা মোবাইল নম্বর" if is_bn else "Email or phone number",
                        key="citizen_register_email",
                        autocomplete="username",
                    )
                    register_password = st.text_input(
                        "নতুন পাসওয়ার্ড (কমপক্ষে ১২ অক্ষর)"
                        if is_bn
                        else "New password (at least 12 characters)",
                        type="password",
                        key="citizen_register_password",
                        autocomplete="new-password",
                    )
                    register_password_confirm = st.text_input(
                        "পাসওয়ার্ড আবার লিখুন" if is_bn else "Confirm password",
                        type="password",
                        key="citizen_register_password_confirm",
                        autocomplete="new-password",
                    )
                    request_registration_code = st.form_submit_button(
                        "ডেমো কোড দেখান" if is_bn else "Show demo code",
                        width="stretch",
                    )
                if request_registration_code:
                    try:
                        normalized_identifier = normalize_citizen_identifier(
                            register_identifier
                        )
                        validate_citizen_password(register_password)
                        if register_password != register_password_confirm:
                            raise ValueError("The passwords do not match.")
                        if citizen_account_exists(normalized_identifier):
                            raise ValueError(
                                "An account already exists for this email or phone number."
                            )
                        demo_code = issue_citizen_demo_code(
                            normalized_identifier,
                            "verify",
                            hash_citizen_password(register_password),
                        )
                        st.session_state.citizen_register_demo_code = demo_code
                    except ValueError as exc:
                        st.error(
                            (
                                "ডেমো কোড তৈরি হয়নি। ইমেইল/নম্বর ও পাসওয়ার্ডের তথ্য পরীক্ষা করুন। "
                                f"বিস্তারিত: {exc}"
                            )
                            if is_bn
                            else str(exc)
                        )
                    else:
                        st.success(
                            "ডেমো যাচাইকরণ কোড তৈরি হয়েছে। নিচে কোডটি দিয়ে নিবন্ধন সম্পন্ন করুন।"
                            if is_bn
                            else "Demo verification code created. Enter the code below to finish registration."
                        )
                if st.session_state.get("citizen_register_demo_code"):
                    st.info(
                        (
                            "ডেমো যাচাইকরণ কোড: "
                            f"`{st.session_state.citizen_register_demo_code}`"
                        )
                        if is_bn
                        else (
                            "Demo verification code: "
                            f"`{st.session_state.citizen_register_demo_code}`"
                        )
                    )

                with st.form("citizen_register_verify_form"):
                    verify_identifier = st.text_input(
                        "ইমেইল অথবা মোবাইল নম্বর" if is_bn else "Email or phone number",
                        key="citizen_verify_email",
                        autocomplete="username",
                    )
                    verify_code = st.text_input(
                        "৬ সংখ্যার কোড" if is_bn else "6-digit verification code",
                        key="citizen_verify_code",
                        max_chars=6,
                        autocomplete="one-time-code",
                    )
                    complete_registration = st.form_submit_button(
                        "নিবন্ধন সম্পন্ন করুন" if is_bn else "Complete registration",
                        type="primary",
                        width="stretch",
                    )
                if complete_registration:
                    try:
                        if register_citizen_account(
                            verify_identifier, verify_code
                        ):
                            st.session_state.pop("citizen_register_demo_code", None)
                            st.session_state.citizen_registration_complete = True
                            st.session_state.citizen_auth_default_tab = (
                                "লগইন" if is_bn else "Sign in"
                            )
                            st.rerun()
                        else:
                            st.error(
                                "কোডটি ভুল, মেয়াদোত্তীর্ণ, অথবা ইতিমধ্যে ব্যবহার করা হয়েছে।"
                                if is_bn
                                else "The code is invalid, expired, or already used."
                            )
                    except ValueError as exc:
                        st.error(
                            "সঠিক ইমেইল ঠিকানা অথবা মোবাইল নম্বর লিখুন।"
                            if is_bn
                            else str(exc)
                        )

            with citizen_reset_tab:
                st.caption(
                    "ডেমোতে রিসেট কোড স্ক্রিনেই দেখানো হবে; কোনো ইমেইল বা SMS পাঠানো হবে না।"
                    if is_bn
                    else "Demo mode: the reset code is shown here; no email or SMS is sent."
                )
                with st.form("citizen_reset_request_form"):
                    reset_request_identifier = st.text_input(
                        "ইমেইল অথবা মোবাইল নম্বর" if is_bn else "Email or phone number",
                        key="citizen_reset_request_email",
                        autocomplete="username",
                    )
                    request_reset_code = st.form_submit_button(
                        "ডেমো রিসেট কোড দেখান" if is_bn else "Show demo reset code",
                        width="stretch",
                    )
                if request_reset_code:
                    try:
                        st.session_state.pop("citizen_reset_demo_code", None)
                        normalized_identifier = normalize_citizen_identifier(
                            reset_request_identifier
                        )
                        if citizen_account_exists(normalized_identifier):
                            demo_code = issue_citizen_demo_code(
                                normalized_identifier,
                                "reset",
                            )
                            st.session_state.citizen_reset_demo_code = demo_code
                        st.success(
                            "ইমেইল/নম্বরটি নিবন্ধিত থাকলে ডেমো রিসেট কোড নিচে দেখানো হবে।"
                            if is_bn
                            else "If the email or phone number is registered, a demo reset code will appear below."
                        )
                        if citizen_account_exists(normalized_identifier):
                            st.info(
                                (
                                    "ডেমো রিসেট কোড: "
                                    f"`{st.session_state.citizen_reset_demo_code}`"
                                )
                                if is_bn
                                else (
                                    "Demo reset code: "
                                    f"`{st.session_state.citizen_reset_demo_code}`"
                                )
                            )
                    except ValueError as exc:
                        st.error(
                            (
                                "ডেমো কোড তৈরি করা যায়নি। ইমেইল ঠিকানা বা মোবাইল নম্বর পরীক্ষা করুন। "
                                f"বিস্তারিত: {exc}"
                            )
                            if is_bn
                            else str(exc)
                        )

                with st.form("citizen_reset_password_form"):
                    reset_identifier = st.text_input(
                        "ইমেইল অথবা মোবাইল নম্বর" if is_bn else "Email or phone number",
                        key="citizen_reset_email",
                        autocomplete="username",
                    )
                    reset_code = st.text_input(
                        "৬ সংখ্যার কোড" if is_bn else "6-digit reset code",
                        key="citizen_reset_code",
                        max_chars=6,
                        autocomplete="one-time-code",
                    )
                    new_password = st.text_input(
                        "নতুন পাসওয়ার্ড (কমপক্ষে ১২ অক্ষর)"
                        if is_bn
                        else "New password (at least 12 characters)",
                        type="password",
                        key="citizen_new_password",
                        autocomplete="new-password",
                    )
                    confirm_new_password = st.text_input(
                        "পাসওয়ার্ড আবার লিখুন" if is_bn else "Confirm new password",
                        type="password",
                        key="citizen_new_password_confirm",
                        autocomplete="new-password",
                    )
                    reset_password_submitted = st.form_submit_button(
                        "পাসওয়ার্ড পরিবর্তন করুন" if is_bn else "Reset password",
                        type="primary",
                        width="stretch",
                    )
                if reset_password_submitted:
                    try:
                        if new_password != confirm_new_password:
                            raise ValueError("The passwords do not match.")
                        if reset_citizen_password(
                            reset_identifier,
                            reset_code,
                            new_password,
                        ):
                            st.session_state.pop("citizen_reset_demo_code", None)
                            st.success(
                                "পাসওয়ার্ড বদলানো হয়েছে। এখন লগইন করুন।"
                                if is_bn
                                else "Password updated. You can now sign in."
                            )
                        else:
                            st.error(
                                "কোডটি ভুল, মেয়াদোত্তীর্ণ, অথবা ইতিমধ্যে ব্যবহার করা হয়েছে।"
                                if is_bn
                                else "The code is invalid, expired, or already used."
                            )
                    except ValueError as exc:
                        st.error(
                            "ইমেইল/নম্বর বা পাসওয়ার্ডের তথ্য পরীক্ষা করুন।"
                            if is_bn
                            else str(exc)
                        )

        with tab_emp:
            st.markdown("### কর্মকর্তা পোর্টাল" if is_bn else "Staff portal")
            with st.form("staff_login_form", clear_on_submit=True):
                emp_id = st.text_input(
                    "কর্মকর্তা আইডি" if is_bn else "Staff ID",
                    placeholder="আইডি লিখুন" if is_bn else "Enter staff ID",
                    autocomplete="off",
                )
                emp_pass = st.text_input(
                    "পাসওয়ার্ড" if is_bn else "Password",
                    type="password",
                    placeholder="পাসওয়ার্ড লিখুন" if is_bn else "Enter password",
                    autocomplete="off",
                )
                staff_login_submitted = st.form_submit_button(
                    "লগইন" if is_bn else "Sign in",
                    type="primary",
                    width="stretch",
                )

            if staff_login_submitted:
                if verify_staff_credentials(emp_id, emp_pass):
                    st.session_state.logged_in = True
                    st.session_state.user_role = "Employee"
                    st.session_state.staff_id = canonical_staff_id(emp_id)
                    st.success("লগইন সফল হয়েছে" if is_bn else "Signed in successfully")
                    st.rerun()
                else:
                    if not staff_account_hashes():
                        st.error(
                            "Staff login চালু করতে `.streamlit/secrets.toml`-এ আলাদা Staff account configure করুন।"
                            if is_bn
                            else "Configure individual staff accounts in `.streamlit/secrets.toml` to enable staff login."
                        )
                    else:
                        st.error(
                            "আইডি বা পাসওয়ার্ড সঠিক নয়"
                            if is_bn
                            else "Incorrect staff ID or password"
                        )
    html(
        f'<div class="bj-app-version">'
        f'{"ভূমিপ্রহরী" if is_bn else "Bhumi Prohori"} · v{APP_VERSION}</div>'
    )
    st.stop()


# --- SIDEBAR & THEME / LOGOUT ---
render_app_menu()
selected_lang = st.session_state.language
is_bn = selected_lang == "বাংলা"
is_dark = st.session_state.theme_mode == "dark"
st.markdown(
    get_css(is_dark, system_mode=st.session_state.theme_mode == "system"),
    unsafe_allow_html=True,
)

with st.sidebar:
    html(
        f'<div class="bj-brand"><div class="bj-logo">'
        f'<img src="{APP_ICON_DATA_URI}" alt="" style="width:38px;height:38px;object-fit:contain;border-radius:10px;">'
        f'</div><div><div class="bj-brand-name">'
        f'{"ভূমিপ্রহরী" if st.session_state.language == "বাংলা" else "Bhumi Prohori"}</div>'
        f'<div class="bj-brand-sub">{"ভূমিকা" if st.session_state.language == "বাংলা" else "Role"}: '
        f'<b>{("নাগরিক" if st.session_state.user_role == "Citizen" else "কর্মকর্তা") if st.session_state.language == "বাংলা" else st.session_state.user_role}</b></div></div></div>'
    )

    is_bn = st.session_state.language == "বাংলা"
    if st.button(
        "লগআউট" if is_bn else "Sign out",
        use_container_width=True,
    ):
        st.session_state.logged_in = False
        st.session_state.user_role = "Citizen"
        st.session_state.pop("staff_id", None)
        st.session_state.pop("user_email", None)
        st.rerun()

    active_actor = active_history_actor()
    if active_actor:
        actor_role, actor_id = active_actor
        with st.expander("সার্চের ইতিহাস" if is_bn else "Search history"):
            st.caption(
                "সার্চের ধরন ও দাগ/খতিয়ান নম্বর সংরক্ষিত হয়; অনুমোদিত কর্মকর্তা ইতিহাস দেখতে পারেন।"
                if is_bn
                else "Search type and plot/khatian numbers are saved; authorized staff can view history."
            )
            try:
                own_history_count = count_search_history(
                    actor_role=actor_role,
                    actor_id=actor_id,
                )
                if own_history_count:
                    own_history_page_count = (own_history_count + 19) // 20
                    own_history_page_key = (
                        f"own_search_history_page_{actor_role}_{actor_id}"
                    )
                    st.session_state[own_history_page_key] = min(
                        max(
                            1,
                            st.session_state.get(own_history_page_key, 1),
                        ),
                        own_history_page_count,
                    )
                    own_history_page = st.selectbox(
                        "পৃষ্ঠা" if is_bn else "Page",
                        list(range(1, own_history_page_count + 1)),
                        key=own_history_page_key,
                    )
                    own_search_history = list_search_history(
                        actor_role=actor_role,
                        actor_id=actor_id,
                        limit=20,
                        offset=(own_history_page - 1) * 20,
                    )
                else:
                    own_search_history = []
            except DATABASE_ERRORS as exc:
                st.error(
                    f"{'সার্চের ইতিহাস লোড করা যায়নি' if is_bn else 'Could not load search history'}: {exc}"
                )
            else:
                if not own_search_history:
                    st.caption(
                        "এখনও কোনো সার্চ নেই।"
                        if is_bn
                        else "No searches yet."
                    )
                for history_item in own_search_history:
                    history_type = {
                        "document_ocr": "নথি যাচাই" if is_bn else "Document verification",
                        "ownership_lookup": "জমি খোঁজা" if is_bn else "Land lookup",
                        "staff_khatian": "খতিয়ান সার্চ" if is_bn else "Khatian search",
                    }.get(history_item["search_type"], history_item["search_type"])
                    st.markdown(
                        f"**{history_type}** · {history_item['query']}"
                    )
                    st.caption(
                        f"{history_item['searched_at']} · "
                        f"{'ফলাফল' if is_bn else 'Results'}: "
                        f"{history_item['result_count'] if history_item['result_count'] is not None else '—'}"
                    )

    if st.session_state.user_role == "Citizen":
        html(f'<div class="bj-side-label">{"ম্যাপ সেটিংস" if is_bn else "Map settings"}</div>')
        default_map_idx = 1 if is_dark else 0
        map_styles = ["light", "dark", "road", "satellite"]
        map_style = st.selectbox(
            "মানচিত্র" if is_bn else "Basemap",
            map_styles,
            index=default_map_idx,
            format_func=lambda style: {
                "light": "হালকা" if is_bn else "Light",
                "dark": "গাঢ়" if is_bn else "Dark",
                "road": "রাস্তা" if is_bn else "Road",
                "satellite": "স্যাটেলাইট" if is_bn else "Satellite",
            }[style],
        )
        show_boundary = st.toggle(
            "প্লটের সীমানা দেখান" if is_bn else "Show parcel boundary",
            value=True,
        )

    html(
        f'<div class="bj-app-version">'
        f'{"ভূমিপ্রহরী" if is_bn else "Bhumi Prohori"} · v{APP_VERSION}</div>'
    )


# ==========================================
# 🏛️ GOVT EMPLOYEE PORTAL (BACKEND / MANAGEMENT)
# ==========================================
if st.session_state.user_role == "Employee":
    html(
        f'<div class="bj-hero"><div class="bj-eyebrow">{"ভূমি রেকর্ড" if is_bn else "LAND RECORDS"}</div>'
        f'<h1>{"রেকর্ড ব্যবস্থাপনা" if is_bn else "Registry"} & '
        f'<span>{"ডাটাবেজ" if is_bn else "Database"}</span></h1></div>'
    )

    with st.form("staff_khatian_search_form"):
        khatian_search = normalize_digits(
            st.text_input(
                "খতিয়ান নম্বর দিয়ে খুঁজুন" if is_bn else "Search by khatian number",
                placeholder="খতিয়ান নম্বর লিখুন" if is_bn else "Enter a khatian number",
                key="staff_khatian_search",
            )
        ).strip().casefold()
        staff_search_submitted = st.form_submit_button(
            "খুঁজুন" if is_bn else "Search",
            width="stretch",
        )
    if staff_search_submitted:
        numeric_search = re.sub(r"\D", "", normalize_digits(khatian_search))
        if numeric_search:
            try:
                record_search_history(
                    "staff_khatian",
                    f"Khatian {numeric_search}",
                )
            except DATABASE_ERRORS as exc:
                st.error(
                    f"{'সার্চ ইতিহাস সংরক্ষণ করা যায়নি' if is_bn else 'Could not save search history'}: {exc}"
                )
    st.caption(
        "এই খোঁজ অপেক্ষমাণ আবেদন, আবেদনের ইতিহাস ও জমির রেকর্ড—সবগুলোতেই কাজ করবে। নম্বরের অংশ লিখলেও মিল খুঁজে দেখাবে।"
        if is_bn
        else "This search filters pending applications, application history, and land records. You can enter part of a number."
    )

    def matches_khatian(khatian_number: object) -> bool:
        normalized_number = normalize_digits(
            str(khatian_number or "")
        ).strip().casefold()
        return not khatian_search or khatian_search in normalized_number

    tab_pending, tab_history, tab_records, tab_feedback, tab_search_history = st.tabs(
        [
            "অপেক্ষমাণ আবেদন" if is_bn else "Pending applications",
            "সিদ্ধান্তের ইতিহাস" if is_bn else "Decision history",
            "জমির রেকর্ড" if is_bn else "Land records",
            "মতামত / সমস্যা" if is_bn else "Feedback / Bug reports",
            "সার্চ ইতিহাস" if is_bn else "Search history",
        ]
    )

    with tab_pending:
        active_staff_ids = {
            staff_id.casefold() for staff_id in staff_account_hashes()
        }
        if len(active_staff_ids) < 2:
            st.error(
                "মালিকানা পরিবর্তনের অনুমোদন বন্ধ আছে: দুইজন আলাদা Staff account configure করতে হবে।"
                if is_bn
                else "Ownership approvals are disabled until two separate staff accounts are configured."
            )
        pending = [
            application
            for application in list_ownership_requests("pending")
            if matches_khatian(application["khatian_no"])
        ]
        if not pending:
            st.info(
                (
                    "এই খতিয়ান নম্বরে কোনো অপেক্ষমাণ আবেদন নেই।"
                    if khatian_search
                    else "কোনো অপেক্ষমাণ আবেদন নেই।"
                )
                if is_bn
                else (
                    "No pending applications match this khatian number."
                    if khatian_search
                    else "No pending applications."
                )
            )
        for application in pending:
            with st.container(border=True):
                st.markdown(
                    f"**{'দাগ' if is_bn else 'Plot'} {application['plot_no']} · "
                    f"{'খতিয়ান' if is_bn else 'Khatian'} {application['khatian_no']}**"
                )
                left, right = st.columns(2)
                left.write(
                    f"**{'বর্তমান মালিক' if is_bn else 'Current owner'}:** "
                    f"{application['previous_owner_bn' if is_bn else 'previous_owner_en']}"
                )
                right.write(
                    f"**{'প্রস্তাবিত মালিক' if is_bn else 'Proposed owner'}:** "
                    f"{application['new_owner_bn' if is_bn else 'new_owner_en']}"
                )
                st.caption(
                    f"{'যোগাযোগ' if is_bn else 'Contact'}: {application['contact_number']} · "
                    f"{'দলিল নম্বর' if is_bn else 'Deed no.'}: {application['deed_number']} · "
                    f"{'আবেদনের সময়' if is_bn else 'Submitted'}: {application['requested_at']}"
                )
                prior_reviews = list_ownership_reviews(application["id"])
                approval_total = sum(
                    review["decision"] == "approved" for review in prior_reviews
                )
                st.info(
                    (
                        "প্রথম যাচাই বাকি"
                        if approval_total == 0
                        else "প্রথম অনুমোদন হয়েছে—দ্বিতীয়, আলাদা Staff-এর যাচাই বাকি"
                    )
                    if is_bn
                    else (
                        "First review pending"
                        if approval_total == 0
                        else "One approval recorded — a second, different staff member must review"
                    )
                )
                if application["proof_filename"]:
                    try:
                        proof_filename, proof_data, proof_digest = load_ownership_proof(
                            application["id"]
                        )
                        suffix = Path(proof_filename).suffix.lower()
                        proof_mime = {
                            ".pdf": "application/pdf",
                            ".png": "image/png",
                            ".jpg": "image/jpeg",
                            ".jpeg": "image/jpeg",
                        }[suffix]
                        st.caption(
                            f"{'প্রমাণপত্র' if is_bn else 'Evidence'}: "
                            f"{proof_filename} · SHA-256: `{proof_digest}`"
                        )
                        st.download_button(
                            "প্রমাণপত্র ডাউনলোড" if is_bn else "Download evidence",
                            data=proof_data,
                            file_name=f"ownership-{application['id']}{suffix}",
                            mime=proof_mime,
                            key=f"proof-{application['id']}",
                        )
                    except (ValueError, *DATABASE_ERRORS) as exc:
                        st.error(
                            f"{'প্রমাণপত্র যাচাই করা যায়নি' if is_bn else 'Could not verify evidence'}: {exc}"
                        )
                else:
                    st.error(
                        "পুরোনো এই আবেদনে প্রমাণপত্র নেই—এটি অনুমোদন করা যাবে না; প্রত্যাখ্যান করে প্রমাণসহ নতুন আবেদন নিন।"
                        if is_bn
                        else "This legacy application has no evidence and cannot be approved. Reject it and request a new application with proof."
                    )

                for review in prior_reviews:
                    st.caption(
                        f"{'যাচাইকারী' if is_bn else 'Reviewer'}: {review['reviewer_id']} · "
                        f"{'সিদ্ধান্ত' if is_bn else 'Decision'}: {review['decision']} · "
                        f"{review['reviewed_at']} · {review['verification_notes']}"
                    )

                current_staff_id = st.session_state.get("staff_id", "")
                if any(
                    review["reviewer_id"].casefold() == current_staff_id.casefold()
                    for review in prior_reviews
                ):
                    st.warning(
                        "আপনি এই আবেদনটি একবার যাচাই করেছেন; দ্বিতীয় অনুমোদন অন্য Staff-কে দিতে হবে।"
                        if is_bn
                        else "You have already reviewed this application. The second decision must come from another staff member."
                    )
                    continue

                with st.form(f"review-form-{application['id']}"):
                    decision_label = st.radio(
                        "সিদ্ধান্ত" if is_bn else "Decision",
                        ["প্রত্যাখ্যান", "যাচাই শেষে অনুমোদন"]
                        if is_bn
                        else ["Reject", "Approve after checks"],
                        index=0,
                        key=f"decision-{application['id']}",
                    )
                    deed_checked = st.checkbox(
                        "মূল দলিল/দলিল নম্বর যাচাই করেছি"
                        if is_bn
                        else "I verified the deed and deed number",
                        key=f"deed-check-{application['id']}",
                    )
                    identity_checked = st.checkbox(
                        "আবেদনকারীর পরিচয়পত্র ও পরিচয় মিলিয়েছি"
                        if is_bn
                        else "I verified the applicant's identity document",
                        key=f"identity-check-{application['id']}",
                    )
                    ownership_checked = st.checkbox(
                        "বর্তমান রেকর্ড ও মালিকানা-ধারাবাহিকতা মিলিয়েছি"
                        if is_bn
                        else "I matched the current record and ownership chain",
                        key=f"ownership-check-{application['id']}",
                    )
                    review_notes = st.text_area(
                        "যাচাইয়ের নোট (কমপক্ষে ২০ অক্ষর)"
                        if is_bn
                        else "Review notes (at least 20 characters)",
                        key=f"review-notes-{application['id']}",
                    )
                    submit_review = st.form_submit_button(
                        "যাচাই জমা দিন" if is_bn else "Submit review",
                        type="primary",
                    )
                if submit_review:
                    decision = (
                        "approved"
                        if decision_label
                        in {"যাচাই শেষে অনুমোদন", "Approve after checks"}
                        else "rejected"
                    )
                    try:
                        final_status = review_ownership_request(
                            application["id"],
                            decision,
                            current_staff_id,
                            deed_checked,
                            identity_checked,
                            ownership_checked,
                            review_notes,
                        )
                        if final_status == "approved":
                            st.success(
                                "দুইজন আলাদা Staff অনুমোদন করেছেন; স্থানীয় রেকর্ড হালনাগাদ হয়েছে।"
                                if is_bn
                                else "Two different staff approved. The local record has been updated."
                            )
                        elif final_status == "rejected":
                            st.success(
                                "আবেদন প্রত্যাখ্যান করে যাচাই-নোট সংরক্ষণ করা হয়েছে।"
                                if is_bn
                                else "Application rejected; review notes were saved."
                            )
                        else:
                            st.success(
                                "প্রথম অনুমোদন সংরক্ষিত। চূড়ান্ত সিদ্ধান্তের জন্য অন্য Staff-এর যাচাই প্রয়োজন।"
                                if is_bn
                                else "First approval recorded. A different staff member must complete the review."
                            )
                        st.rerun()
                    except (ValueError, OSError, *DATABASE_ERRORS, json.JSONDecodeError) as exc:
                        st.error(f"{'যাচাই সংরক্ষণ করা যায়নি' if is_bn else 'Could not submit review'}: {exc}")

    with tab_history:
        history = [
            row
            for row in list_ownership_requests()
            if matches_khatian(row["khatian_no"])
        ]
        if history:
            status_names = (
                {"pending": "অপেক্ষমাণ", "approved": "অনুমোদিত", "rejected": "প্রত্যাখ্যাত"}
                if is_bn
                else {"pending": "Pending", "approved": "Approved", "rejected": "Rejected"}
            )
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "দাগ" if is_bn else "Plot": row["plot_no"],
                            "খতিয়ান" if is_bn else "Khatian": row["khatian_no"],
                            "আগের মালিক" if is_bn else "Previous owner": row[
                                "previous_owner_bn" if is_bn else "previous_owner_en"
                            ],
                            "নতুন মালিক" if is_bn else "New owner": row[
                                "new_owner_bn" if is_bn else "new_owner_en"
                            ],
                            "যোগাযোগ" if is_bn else "Contact": row["contact_number"],
                            "দলিল" if is_bn else "Deed": row["deed_number"],
                            "অবস্থা" if is_bn else "Status": status_names[row["status"]],
                            "যাচাই" if is_bn else "Reviews": " · ".join(
                                f"{review['reviewer_id']}: {review['decision']} — "
                                f"{review['verification_notes']}"
                                for review in list_ownership_reviews(row["id"])
                            ) or ("যাচাই শুরু হয়নি" if is_bn else "Not reviewed"),
                            "আবেদনের সময়" if is_bn else "Requested": row["requested_at"],
                            "সিদ্ধান্তের সময়" if is_bn else "Reviewed": row["reviewed_at"] or "—",
                        }
                        for row in history
                    ]
                ),
                width="stretch",
                hide_index=True,
            )
        else:
            st.info(
                (
                    "এই খতিয়ান নম্বরে কোনো আবেদন নেই।"
                    if khatian_search
                    else "এখনও কোনো আবেদন নেই।"
                )
                if is_bn
                else (
                    "No applications match this khatian number."
                    if khatian_search
                    else "No applications yet."
                )
            )

    with tab_records:
        st.caption(
            "এটি অ্যাপের স্থানীয় নমুনা রেকর্ড; সরকারি ভূমি-রেজিস্ট্রিতে সরাসরি পরিবর্তন হয় না।"
            if is_bn
            else "These are local app records; approvals do not update the government land registry."
        )
        try:
            with land_geojson_path().open("r", encoding="utf-8") as source:
                features = json.load(source).get("features", [])
            records = []
            for feature in features:
                properties = feature.get("properties", {})
                if not matches_khatian(properties.get("khatian_no")):
                    continue
                owner_en, owner_bn = get_current_owner(
                    str(properties.get("plot_no") or ""),
                    str(properties.get("khatian_no") or ""),
                    str(properties.get("owner_name") or ""),
                    str(properties.get("owner_name_bn") or properties.get("owner_name") or ""),
                )
                records.append(
                    {
                        "দাগ" if is_bn else "Plot": properties.get("plot_no"),
                        "খতিয়ান" if is_bn else "Khatian": properties.get("khatian_no"),
                        "মালিক" if is_bn else "Owner": owner_bn if is_bn else owner_en,
                        "মৌজা" if is_bn else "Mouza": (
                            properties.get("mouza_bn") if is_bn else properties.get("mouza")
                        ),
                        "উপজেলা" if is_bn else "Upazila": properties.get("upazila"),
                        "জেলা" if is_bn else "District": properties.get("district"),
                        "পরিমাণ" if is_bn else "Area": properties.get("declared_area"),
                    }
                )
            if records:
                st.dataframe(pd.DataFrame(records), width="stretch", hide_index=True)
            else:
                st.info(
                    "এই খতিয়ান নম্বরে কোনো জমির রেকর্ড নেই।"
                    if is_bn
                    else "No land records match this khatian number."
                )
        except (OSError, json.JSONDecodeError, *DATABASE_ERRORS) as exc:
            st.error(f"{'রেকর্ড লোড করা যায়নি' if is_bn else 'Could not load records'}: {exc}")

    with tab_feedback:
        try:
            feedback_items = list_app_feedback()
        except DATABASE_ERRORS as exc:
            st.error(
                f"{'মতামত লোড করা যায়নি' if is_bn else 'Could not load feedback'}: {exc}"
            )
        else:
            if not feedback_items:
                st.info(
                    "এখনও কোনো মতামত বা সমস্যা প্রতিবেদন জমা হয়নি।"
                    if is_bn
                    else "No feedback or bug reports have been submitted."
                )
            for item in feedback_items:
                with st.container(border=True):
                    category = (
                        {"feedback": "মতামত", "bug": "সমস্যার প্রতিবেদন"}[
                            item["category"]
                        ]
                        if is_bn
                        else {"feedback": "Feedback", "bug": "Bug report"}[
                            item["category"]
                        ]
                    )
                    st.markdown(f"**{category}**")
                    st.write(item["message"])
                    st.caption(
                        f"{'জমাদানকারী' if is_bn else 'Submitted by'}: "
                        f"{'নাগরিক' if is_bn and item['user_role'] == 'Citizen' else 'কর্মকর্তা' if is_bn and item['user_role'] == 'Employee' else item['user_role']} · "
                        f"{item['submitted_at']} · v{item['app_version']}"
                    )

    with tab_search_history:
        st.caption(
            "অনুমোদিত কর্মকর্তা সব নাগরিক ও কর্মকর্তার সার্চ ইতিহাস দেখতে পারবেন। এখানে শুধু খোঁজের ধরন, দাগ/খতিয়ান নম্বর, ব্যবহারকারীর পরিচয় ও সময় থাকে—দলিলের OCR লেখা বা ছবি নয়।"
            if is_bn
            else "Authorized staff can view search history for all citizens and staff. History stores the search type, plot/khatian number, user identifier, and time—not document images or OCR text."
        )
        with st.form("staff_search_history_filter_form"):
            history_filter_col, history_role_col = st.columns([2, 1])
            history_identifier_input = history_filter_col.text_input(
                "ইমেইল / মোবাইল / স্টাফ আইডি দিয়ে ফিল্টার করুন"
                if is_bn
                else "Filter by email / phone / staff ID",
                key="staff_history_identifier_input",
            )
            history_role_input = history_role_col.selectbox(
                "ব্যবহারকারীর ধরন" if is_bn else "User type",
                ["All", "Citizen", "Employee"],
                format_func=lambda role: (
                    "সবাই" if is_bn and role == "All"
                    else "নাগরিক" if is_bn and role == "Citizen"
                    else "কর্মকর্তা" if is_bn
                    else "All users" if role == "All"
                    else role
                ),
            )
            history_filter_submitted = st.form_submit_button(
                "ফিল্টার করুন" if is_bn else "Apply filters",
                width="stretch",
            )
        if history_filter_submitted:
            st.session_state.staff_history_identifier_filter = (
                history_identifier_input
            )
            st.session_state.staff_history_role_filter = history_role_input
            st.session_state.staff_history_page = 1
        history_identifier_filter = st.session_state.get(
            "staff_history_identifier_filter",
            "",
        )
        history_role_filter = st.session_state.get(
            "staff_history_role_filter",
            "All",
        )
        try:
            filtered_role = (
                history_role_filter
                if history_role_filter != "All"
                else None
            )
            history_total = count_search_history(
                actor_role=filtered_role,
                identifier_search=history_identifier_filter,
            )
            history_page_count = max(1, (history_total + 99) // 100)
            st.session_state.staff_history_page = min(
                max(1, st.session_state.get("staff_history_page", 1)),
                history_page_count,
            )
            history_page = st.selectbox(
                "পৃষ্ঠা" if is_bn else "Page",
                list(range(1, history_page_count + 1)),
                key="staff_history_page",
            )
            all_search_history = list_search_history(
                actor_role=filtered_role,
                identifier_search=history_identifier_filter,
                limit=100,
                offset=(history_page - 1) * 100,
            )
        except DATABASE_ERRORS as exc:
            st.error(
                f"{'সার্চ ইতিহাস লোড করা যায়নি' if is_bn else 'Could not load search history'}: {exc}"
            )
        else:
            if all_search_history:
                st.dataframe(
                    search_history_frame(
                        all_search_history,
                        is_bn,
                        include_actor=True,
                    ),
                    width="stretch",
                    hide_index=True,
                )
            else:
                st.info(
                    "এই ফিল্টারে কোনো সার্চ ইতিহাস নেই।"
                    if is_bn
                    else "No search history matches these filters."
                )

    st.stop()


# ==========================================
# 👤 PUBLIC CITIZEN PORTAL (FRONTEND VERIFICATION)
# ==========================================
hero_sub = (
    "জমির নথি যাচাই ও প্লটের তথ্য দেখুন।"
    if is_bn
    else "Verify land records and view parcel details."
)

tab_verify, tab_ownership, tab_map = st.tabs(
    [
        "নথি যাচাই" if is_bn else "Verify documents",
        "মালিকানা পরিবর্তন" if is_bn else "Ownership change",
        "প্লটের মানচিত্র" if is_bn else "Parcel map",
    ]
)

with tab_verify:
    html(
        f'<div class="bj-hero"><div class="bj-eyebrow">{"নাগরিক পোর্টাল" if is_bn else "CITIZEN PORTAL"}</div>'
        f'<h1>{"ভূমি রেকর্ড" if is_bn else "Land Records"} '
        f'<span>{"যাচাই" if is_bn else "Verification"}</span></h1>'
        f"<p>{hero_sub}</p></div>"
    )

    col_upload, col_ocr = st.columns([1, 1.25], gap="large")
    image: Image.Image | None = None

    with col_upload:
        with st.container(key="card-upload"):
            sec1_title = "নথি আপলোড" if is_bn else "Upload Document"
            sec1_sub = (
                "খতিয়ানের ছবি (PNG, JPG, TIFF)"
                if is_bn
                else "Land record image (PNG, JPG, TIFF)"
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
                    st.error("ছবির ফাইলটি পড়া যায়নি" if is_bn else "Could not read image file")

            if image is not None:
                sig = (uploaded.name, uploaded.size)
                if sig != st.session_state.file_sig:
                    st.session_state.file_sig = sig
                    st.session_state.result = None

                st.image(image, caption=uploaded.name)
                badge_row(
                    badge("প্রস্তুত" if is_bn else "Ready", "success"),
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
                        "নথি যাচাই হচ্ছে..." if is_bn else "Verifying document..."
                    ):
                        res = process_hybrid_pipeline(image, lang=selected_lang)
                    ocr_fields = res.get("ocr_fields") or {}
                    search_query = land_number_history_query(
                        ocr_fields.get("plot"),
                        ocr_fields.get("khatian"),
                    )
                    if not search_query:
                        search_query = (
                            "দাগ/খতিয়ান নম্বর পাওয়া যায়নি"
                            if is_bn
                            else "No plot/khatian number extracted"
                        )
                    history_results = len(res.get("candidate_records") or [])
                    if res.get("matched_properties"):
                        history_results = max(history_results, 1)
                    try:
                        record_search_history(
                            "document_ocr",
                            search_query,
                            history_results,
                        )
                    except DATABASE_ERRORS as exc:
                        st.error(
                            f"{'সার্চ ইতিহাস সংরক্ষণ করা যায়নি' if is_bn else 'Could not save search history'}: {exc}"
                        )
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
                empty_title = "কোনো ফাইল দেওয়া হয়নি" if is_bn else "No Document Uploaded"
                empty_desc = (
                    "শুরু করতে একটি নথি আপলোড করুন।"
                    if is_bn
                    else "Upload a land record to begin."
                )
                empty_state("📄", empty_title, empty_desc)

    result = st.session_state.result
    comparison_properties = result.get("matched_properties") if result else None

    if result and result.get("fields") and comparison_properties is None:
        raw_plot = result["fields"].get("plot")
        if raw_plot:
            clean_plot = normalize_digits(str(raw_plot))
            try:
                comparison_properties = find_land_record_by_plot(clean_plot)
                _, updated_fields = load_plot_from_geojson(
                    clean_plot,
                    lang=selected_lang,
                )
                if updated_fields:
                    result["fields"] = updated_fields
            except (OSError, json.JSONDecodeError) as exc:
                st.error(
                    f"{'ডাটাবেজের সঙ্গে তুলনা করা যায়নি' if is_bn else 'Could not compare with the database'}: {exc}"
                )
        if comparison_properties is None:
            ocr_fields = result.get("ocr_fields") or extract_document_fields(
                result.get("text", "")
            )
            khatian_number = ocr_fields.get("khatian")
            if khatian_number:
                try:
                    candidates = find_land_records_by_khatian(khatian_number)
                    result["candidate_records"] = candidates
                    if len(candidates) == 1:
                        comparison_properties = candidates[0]
                        _, database_fields = load_plot_from_geojson(
                            str(
                                candidates[0].get("plot_no")
                                or candidates[0].get("plot_number")
                                or ""
                            ),
                            lang=selected_lang,
                        )
                        if database_fields:
                            result["fields"] = database_fields
                except (OSError, json.JSONDecodeError) as exc:
                    st.error(
                        f"{'খতিয়ান নম্বর দিয়ে ডাটাবেজ খোঁজা যায়নি' if is_bn else 'Could not search the database by khatian number'}: {exc}"
                    )

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
                right = badge("ডাটাবেজে নেই" if is_bn else "Not Found", "error")

            sec2_title = (
                "প্রাপ্ত তথ্য" if is_bn else "Extracted Fields"
            )
            sec2_sub = (
                "নথি থেকে পাওয়া জমির তথ্য"
                if is_bn
                else "Land record details"
            )
            section_header(2, sec2_title, sec2_sub, right)

            if result is None:
                empty_state(
                    "🔎",
                    "কোনো তথ্য এক্সট্রাক্ট হয়নি" if is_bn else "No Extraction Yet",
                    (
                        "একটি নথি আপলোড করুন।"
                        if is_bn
                        else "Upload a document to view extracted fields."
                    ),
                )
            else:
                fields = result["fields"]
                st.caption(
                    f"**{('প্রক্রিয়া' if is_bn else 'Method')}:** `{result.get('engine', 'Unknown')}`"
                )

                if fields.get("lat") is None:
                    candidates = result.get("candidate_records", [])
                    if len(candidates) > 1:
                        st.warning(
                            "এই খতিয়ান নম্বরে একাধিক রেকর্ড আছে। নথিতে দাগ নম্বর থাকলে সেটিও মিলিয়ে সঠিক রেকর্ড দেখুন।"
                            if is_bn
                            else "More than one record has this khatian number. Use the plot number on the document to identify the correct record."
                        )
                        candidate_rows = []
                        for candidate in candidates:
                            plot_number = str(
                                candidate.get("plot_no")
                                or candidate.get("plot_number")
                                or ""
                            )
                            khatian_number = str(candidate.get("khatian_no") or "")
                            owner_en, owner_bn = get_current_owner(
                                plot_number,
                                khatian_number,
                                str(candidate.get("owner_name") or ""),
                                str(
                                    candidate.get("owner_name_bn")
                                    or candidate.get("owner_name")
                                    or ""
                                ),
                            )
                            candidate_rows.append(
                                {
                                    "দাগ" if is_bn else "Plot": plot_number,
                                    "খতিয়ান" if is_bn else "Khatian": khatian_number,
                                    "মালিক" if is_bn else "Owner": owner_bn
                                    if is_bn
                                    else owner_en,
                                    "মৌজা" if is_bn else "Mouza": (
                                        candidate.get("mouza_bn")
                                        if is_bn
                                        else candidate.get("mouza")
                                    ),
                                    "উপজেলা" if is_bn else "Upazila": candidate.get(
                                        "upazila"
                                    ),
                                    "জেলা" if is_bn else "District": candidate.get("district"),
                                    "পরিমাণ" if is_bn else "Area": candidate.get("declared_area"),
                                }
                            )
                        st.dataframe(
                            pd.DataFrame(candidate_rows),
                            width="stretch",
                            hide_index=True,
                        )
                    else:
                        recognized_khatian = (
                            (result.get("ocr_fields") or {}).get("khatian")
                            or extract_document_fields(result.get("text", "")).get(
                                "khatian"
                            )
                        )
                        st.warning(
                            (
                                f"খতিয়ান নম্বর {recognized_khatian} ডাটাবেজে পাওয়া যায়নি।"
                                if recognized_khatian
                                else "নথির খতিয়ান নম্বর OCR-এ পড়া যায়নি; ডাটাবেজের রেকর্ড দেখানো সম্ভব হয়নি।"
                            )
                            if is_bn
                            else (
                                f"Khatian number {recognized_khatian} was not found in the database."
                                if recognized_khatian
                                else "OCR could not read a khatian number, so a database record could not be shown."
                            )
                        )

                if is_bn:
                    tiles = [
                        ("দাগ নম্বর", fields.get("plot")),
                        ("খতিয়ান নম্বর", fields.get("khatian")),
                        ("মালিকের নাম", fields.get("owner")),
                        ("মৌজা নাম", fields.get("mouza")),
                        ("উপজেলা", fields.get("upazila")),
                        ("জে.এল. নম্বর", fields.get("jl_no")),
                        ("খতিয়ান প্রকার", fields.get("khatian_type")),
                        ("জমির শ্রেণি", fields.get("land_type")),
                        ("জেলা", fields.get("district")),
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
                        ("Upazila", fields.get("upazila")),
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
                    f'<div class="bj-tile-value">{v or ("পাওয়া যায়নি" if is_bn else "Not found")}</div></div>'
                    for label, v in tiles
                )
                html(f'<div class="bj-grid">{grid}</div>')

                if comparison_properties is not None:
                    ocr_fields = result.get("ocr_fields") or extract_document_fields(
                        result.get("text", "")
                    )
                    if not ocr_fields:
                        st.warning(
                            "OCR-এ তুলনা করার মতো তথ্য পাওয়া যায়নি, তাই মিলের শতাংশ হিসাব করা যায়নি।"
                            if is_bn
                            else "OCR did not identify labeled fields to compare, so a match percentage could not be calculated."
                        )
                    else:
                        mismatches, matched_count, checked_count = (
                            ocr_database_field_comparison(
                                ocr_fields,
                                comparison_properties,
                                fields,
                                is_bn,
                            )
                        )
                        if checked_count:
                            match_percentage = round(
                                matched_count * 100 / checked_count
                            )
                            st.metric(
                                "ডাটাবেজের সঙ্গে মিল" if is_bn else "Database match",
                                f"{match_percentage}%",
                            )
                        if mismatches:
                            mismatch_list = "\n".join(
                                f"- **{label}** — "
                                f"{'নথির মান' if is_bn else 'Document value'}: `{ocr_value}` · "
                                f"{'ডাটাবেজের মান' if is_bn else 'Database value'}: `{database_value}`"
                                for label, ocr_value, database_value in mismatches
                            )
                            st.warning(
                                (
                                    "শুধু অমিল পাওয়া তথ্যগুলো নিচে দেখানো হয়েছে। OCR ভুল পড়তে পারে—মূল নথি হাতে যাচাই করুন।\n\n"
                                    if is_bn
                                    else "Only fields that differ are listed below. OCR may be inaccurate, so verify them against the original document.\n\n"
                                )
                                + mismatch_list
                            )
                        elif checked_count:
                            st.success(
                                "যাচাই করা সব তথ্য ডাটাবেজের সঙ্গে মিলেছে।"
                                if is_bn
                                else "All compared fields match the database."
                            )
                        else:
                            st.info(
                                "OCR থেকে তুলনা করার মতো কোনো পূরণ করা তথ্য পাওয়া যায়নি।"
                                if is_bn
                                else "OCR did not extract any populated fields to compare."
                            )

                found = sum(1 for _, v in tiles if v)
                badge_row(
                    badge(
                        f"{found}/{len(tiles)} "
                        + (
                            "ফিল্ড সফলভাবে ভেরিফাই হয়েছে"
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

    with tab_ownership:
        with st.expander(
            "মালিকানা পরিবর্তনের আবেদন" if is_bn else "Request an ownership change",
            expanded=True,
        ):
            st.caption(
                "শুধু অ্যাপে থাকা জমির দাগ ও খতিয়ান দিয়ে আবেদন করা যাবে।"
                if is_bn
                else "Applications are limited to plots and khatians already in this app."
            )
            st.caption(
                "আবেদন ও অনুমোদন শুধু অ্যাপের স্থানীয় রেকর্ডে প্রযোজ্য; সরকারি ভূমি-রেজিস্ট্রিতে পরিবর্তন হয় না।"
                if is_bn
                else "Applications and approvals apply only to this app's local records, not the government land registry."
            )
            with st.form("ownership_lookup_form"):
                lookup_plot_col, lookup_khatian_col = st.columns(2)
                lookup_plot = lookup_plot_col.text_input(
                    "দাগ নম্বর" if is_bn else "Plot / Dag number",
                    key="ownership_lookup_plot",
                )
                lookup_khatian = lookup_khatian_col.text_input(
                    "খতিয়ান নম্বর" if is_bn else "Khatian number",
                    key="ownership_lookup_khatian",
                )
                lookup_submitted = st.form_submit_button(
                    "জমি খুঁজুন" if is_bn else "Find existing land"
                )

            if lookup_submitted:
                try:
                    matched_properties = find_land_record(lookup_plot, lookup_khatian)
                    search_query = land_number_history_query(
                        lookup_plot,
                        lookup_khatian,
                    )
                    if search_query:
                        try:
                            record_search_history(
                                "ownership_lookup",
                                search_query,
                                1 if matched_properties else 0,
                            )
                        except DATABASE_ERRORS as exc:
                            st.error(
                                f"{'সার্চ ইতিহাস সংরক্ষণ করা যায়নি' if is_bn else 'Could not save search history'}: {exc}"
                            )
                    if matched_properties is None:
                        st.session_state.ownership_lookup = None
                        st.error(
                            "এই দাগ ও খতিয়ানের জমি রেকর্ডে পাওয়া যায়নি।"
                            if is_bn
                            else "No existing land record matches that plot and khatian."
                        )
                    else:
                        st.session_state.ownership_lookup = (
                            normalize_digits(lookup_plot).strip(),
                            normalize_digits(lookup_khatian).strip(),
                        )
                except (OSError, json.JSONDecodeError) as exc:
                    st.error(f"{'জমির রেকর্ড পড়া যায়নি' if is_bn else 'Could not read land records'}: {exc}")

            selected_land = st.session_state.get("ownership_lookup")
            if selected_land:
                try:
                    properties = find_land_record(*selected_land)
                    if properties is None:
                        st.session_state.ownership_lookup = None
                        st.error(
                            "জমির রেকর্ডটি আর পাওয়া যাচ্ছে না।"
                            if is_bn
                            else "The selected land record is no longer available."
                        )
                    else:
                        current_owner_en, current_owner_bn = get_current_owner(
                            selected_land[0],
                            selected_land[1],
                            str(properties.get("owner_name") or ""),
                            str(properties.get("owner_name_bn") or properties.get("owner_name") or ""),
                        )
                        st.info(
                            f"{'বর্তমান মালিক' if is_bn else 'Current owner'}: "
                            f"{current_owner_bn if is_bn else current_owner_en}"
                        )
                        with st.form("ownership_request_form"):
                            name_en_col, name_bn_col = st.columns(2)
                            new_owner_en = name_en_col.text_input(
                                "নতুন মালিকের নাম (English)" if is_bn else "New owner name (English)"
                            )
                            new_owner_bn = name_bn_col.text_input(
                                "নতুন মালিকের নাম (বাংলা)" if is_bn else "New owner name (Bangla)"
                            )
                            contact_col, deed_col = st.columns(2)
                            contact_number = contact_col.text_input(
                                "যোগাযোগ নম্বর" if is_bn else "Contact number"
                            )
                            deed_number = deed_col.text_input(
                                "দলিল নম্বর" if is_bn else "Deed number"
                            )
                            proof_upload = st.file_uploader(
                                "দলিল/পরিচয় যাচাইয়ের প্রমাণ (PDF, PNG, JPEG; সর্বোচ্চ ১০ MB)"
                                if is_bn
                                else "Supporting deed/identity evidence (PDF, PNG, JPEG; max 10 MB)",
                                type=["pdf", "png", "jpg", "jpeg"],
                                key=f"ownership-proof-{selected_land[0]}-{selected_land[1]}",
                                max_upload_size=10,
                            )
                            request_submitted = st.form_submit_button(
                                "আবেদন জমা দিন" if is_bn else "Submit application",
                                type="primary",
                            )

                        if request_submitted:
                            normalized_phone = normalize_digits(contact_number).strip()
                            phone_digit_count = len(re.sub(r"\D", "", normalized_phone))
                            if not all(
                                [
                                    new_owner_en.strip(),
                                    new_owner_bn.strip(),
                                    deed_number.strip(),
                                ]
                            ) or proof_upload is None:
                                st.error(
                                    "নতুন মালিকের দুই নাম, দলিল নম্বর ও প্রমাণপত্র দিন।"
                                    if is_bn
                                    else "Enter both new-owner names, the deed number, and a supporting document."
                                )
                            elif not (
                                re.fullmatch(r"[0-9+() -]{7,20}", normalized_phone)
                                and 7 <= phone_digit_count <= 15
                            ):
                                st.error(
                                    "বৈধ যোগাযোগ নম্বর দিন।"
                                    if is_bn
                                    else "Enter a valid contact number."
                                )
                            else:
                                try:
                                    create_ownership_request(
                                        properties,
                                        new_owner_en,
                                        new_owner_bn,
                                        normalized_phone,
                                        deed_number,
                                        proof_upload.name,
                                        proof_upload.getvalue(),
                                    )
                                    st.success(
                                        "আবেদন ও এনক্রিপ্ট করা প্রমাণপত্র জমা হয়েছে; দুইজন আলাদা কর্মকর্তা যাচাই করবেন।"
                                        if is_bn
                                        else "Application and encrypted evidence submitted. Two different staff members must review it."
                                    )
                                    st.session_state.ownership_lookup = None
                                except (ValueError, *DATABASE_ERRORS) as exc:
                                    st.error(
                                        f"{'আবেদন জমা দেওয়া যায়নি' if is_bn else 'Could not submit application'}: {exc}"
                                    )
                except DATABASE_ERRORS as exc:
                    st.error(f"{'মালিকানা তথ্য পড়া যায়নি' if is_bn else 'Could not read ownership data'}: {exc}")

        # GIS Map Viewer
    with tab_map:
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
                "প্লটের মানচিত্র"
                if is_bn
                else "Parcel map"
            )
            sec3_sub = "প্লটের সীমানা ও অবস্থান" if is_bn else "Parcel boundary and location"
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
                            ("খতিয়ান নং", fields.get("khatian")),
                            ("মালিকের নাম", fields.get("owner")),
                            ("মৌজা", fields.get("mouza")),
                            ("উপজেলা", fields.get("upazila")),
                            ("জমির পরিমাণ", fields.get("declared_area")),
                            ("অবস্থান", f"{lat:.5f}, {lon:.5f}"),
                        ]
                    else:
                        rows = [
                            ("Plot No", plot_no),
                            ("Khatian No", fields.get("khatian")),
                            ("Owner", fields.get("owner")),
                            ("Mouza", fields.get("mouza")),
                            ("Upazila", fields.get("upazila")),
                            ("Area", fields.get("declared_area")),
                            ("Position", f"{lat:.5f}, {lon:.5f}"),
                        ]
                    grid = "".join(
                        f'<div class="bj-tile"><div class="bj-tile-label">{k}</div><div class="bj-tile-value">{v or "—"}</div></div>'
                        for k, v in rows
                    )
                    html(
                        f'<div class="bj-grid" style="grid-template-columns:1fr;">{grid}</div>'
                    )
                    st.link_button(
                        "গুগল ম্যাপে লোকেশন দেখুন" if is_bn else "Open in Google Maps",
                        f"https://www.google.com/maps?q={lat},{lon}",
                        use_container_width=True,
                    )
                else:
                    st.info(
                        "রেকর্ড যাচাই হলে মানচিত্র দেখা যাবে।"
                        if is_bn
                        else "The map appears when a record is verified."
                    )

            with col_map:
                if has_coords:
                    if map_style == "satellite":
                        satellite_map = folium.Map(
                            location=[lat, lon],
                            zoom_start=18,
                            tiles=None,
                            control_scale=True,
                        )
                        folium.TileLayer(
                            tiles=(
                                "https://server.arcgisonline.com/ArcGIS/rest/services/"
                                "World_Imagery/MapServer/tile/{z}/{y}/{x}"
                            ),
                            attr=(
                                "Tiles © Esri — Source: Esri, Maxar, Earthstar "
                                "Geographics, and the GIS User Community"
                            ),
                            name="Esri World Imagery",
                            overlay=False,
                            control=False,
                            max_zoom=19,
                        ).add_to(satellite_map)
                        if show_boundary:
                            folium.Polygon(
                                locations=[
                                    [latitude, longitude]
                                    for longitude, latitude in polygon_coords
                                ],
                                color="#556b2f",
                                weight=3,
                                fill=True,
                                fill_color="#6b8e23",
                                fill_opacity=0.3,
                                tooltip=(
                                    f"{'দাগ' if is_bn else 'Plot'}: {plot_no}"
                                ),
                            ).add_to(satellite_map)
                        folium.Marker(
                            [lat, lon],
                            tooltip=(
                                f"{'দাগ' if is_bn else 'Plot'}: {plot_no}"
                            ),
                            popup=str(fields.get("owner", "")),
                        ).add_to(satellite_map)
                        st_folium(
                            satellite_map,
                            height=465,
                            use_container_width=True,
                            key=f"satellite-map-{plot_no}",
                        )
                        st.caption(
                            "Satellite imagery © Esri এবং অবদানকারী প্রতিষ্ঠানসমূহ।"
                            if is_bn
                            else "Satellite imagery © Esri and its data providers."
                        )

                    if map_style != "satellite":
                        layers = []
                        if show_boundary:
                            layers.append(
                                pdk.Layer(
                                    "PolygonLayer",
                                    data=[{"polygon": polygon_coords}],
                                    get_polygon="polygon",
                                    get_fill_color=[85, 107, 47, 85],
                                    get_line_color=[85, 107, 47, 255],
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
                                get_fill_color=[107, 142, 35, 240],
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
                                map_provider="carto",
                                map_style=map_style,
                                tooltip={
                                    "text": f"{'দাগ' if is_bn else 'Plot'}: {plot_no}\n"
                                    f"{'মালিক' if is_bn else 'Owner'}: "
                                    + str(fields.get("owner", ""))
                                },
                            ),
                            height=465,
                        )
                else:
                    empty_state(
                        "🗺️",
                        "ম্যাপ প্রস্তুত" if is_bn else "Map ready",
                        (
                            "ম্যাপ দেখতে একটি নথি যাচাই করুন।"
                            if is_bn
                            else "Verify a record to view its parcel map."
                        ),
                    )

        st.caption(f"Bhumi Prohori · v{APP_VERSION}")