"""Fase 4 (Tarea 2): dashboard Streamlit del radar de contrataciones.

Lee UNICAMENTE archivos precomputados (data/processed/*_clean.jsonl,
data/outputs/risk_indicator.json, data/processed/hybrid_index/) -- no
recalcula validacion, indexacion ni el indicador de riesgo al abrir la
app, como pide el enunciado ("Precomputed file reading, no real-time
rebuilding"). Para regenerarlos: python3 src/validation.py,
src/hybrid_index.py, src/risk_indicator.py.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from src.hybrid_engine import search  # noqa: E402

MONTHS = ["2026_06", "2026_07", "2026_08"]
SIMILARITY_THRESHOLD_DEFAULT = 0.35  # ver docs/tarea2_fase3_rag_hibrido.md, seccion 3


@st.cache_data
def load_processes() -> pd.DataFrame:
    rows = []
    for m in MONTHS:
        path = BASE_DIR / "data" / "processed" / f"{m}_clean.jsonl"
        with path.open(encoding="utf-8") as f:
            rows.extend(json.loads(line) for line in f)
    df = pd.DataFrame(rows)
    df["amount_pen"] = pd.to_numeric(df["amount_pen"], errors="coerce")
    df["date_published"] = pd.to_datetime(df["date_published"], errors="coerce", utc=True)
    return df


@st.cache_data
def load_quality_report() -> dict:
    return json.loads((BASE_DIR / "data" / "processed" / "quality_report.json").read_text(encoding="utf-8"))


@st.cache_data
def load_risk_indicator() -> dict:
    return json.loads((BASE_DIR / "data" / "outputs" / "risk_indicator.json").read_text(encoding="utf-8"))


@st.cache_data
def load_geojson() -> dict:
    return json.loads((BASE_DIR / "data" / "raw" / "geo" / "peru_departamentos.geojson").read_text(encoding="utf-8"))


st.set_page_config(page_title="Radar de Contrataciones (Perú)", page_icon="📊", layout="wide")
st.title("Radar de Contrataciones Públicas — Perú (jun-ago 2026)")
st.caption(
    "Datos reales del portal OECE (contratacionesabiertas.oece.gob.pe/api/v1/files), "
    "3 meses. Ver docs/tarea2_fase1_adquisicion.md."
)

df = load_processes()
quality = load_quality_report()
risk = load_risk_indicator()

# --- Sidebar: filtros ---
st.sidebar.header("Filtros")
departments = sorted(df["buyer_department"].dropna().unique())
sel_department = st.sidebar.selectbox("Departamento", ["(Todos)"] + departments)
categories = sorted(df["main_category"].dropna().unique())
sel_category = st.sidebar.multiselect("Categoría", categories, default=categories)
min_amt, max_amt = float(df["amount_pen"].min()), float(df["amount_pen"].max())
sel_amount = st.sidebar.slider("Rango de monto (PEN)", min_amt, max_amt, (min_amt, max_amt))
min_date, max_date = df["date_published"].min(), df["date_published"].max()
sel_dates = st.sidebar.date_input("Rango de fecha", (min_date.date(), max_date.date()))
sel_similarity = st.sidebar.slider("Umbral de similitud (búsqueda semántica)", 0.0, 1.0, SIMILARITY_THRESHOLD_DEFAULT, 0.01)

mask = df["main_category"].isin(sel_category)
if sel_department != "(Todos)":
    mask &= df["buyer_department"] == sel_department
mask &= df["amount_pen"].between(*sel_amount)
if isinstance(sel_dates, tuple) and len(sel_dates) == 2:
    d0, d1 = sel_dates
    mask &= df["date_published"].dt.date.between(d0, d1)
filtered = df[mask]

# --- KPI header ---
c1, c2, c3, c4 = st.columns(4)
c1.metric("Procesos (filtrados)", f"{len(filtered):,}")
c2.metric("Monto total (PEN)", f"S/ {filtered['amount_pen'].sum():,.0f}")
c3.metric("Departamentos representados", filtered["buyer_department"].nunique())
c4.metric("Tasa de postor único (global, 3 meses)", f"{risk['overall_single_bidder_share']*100:.1f}%")

# --- Mapa coroplético ---
st.subheader("Distribución de procesos por departamento")
by_dept = filtered.groupby("buyer_department").size().reset_index(name="n_procesos")
# Escala logaritmica: la distribucion esta muy sesgada (Lima ~5600 procesos
# vs. la mayoria de departamentos por debajo de 1700), y con escala lineal
# casi todo el mapa se ve del mismo tono oscuro salvo Lima. Verificado con
# los datos reales (data/processed/*_clean.jsonl) que el enlace geojson y
# los valores por departamento son correctos -- esto es una mejora visual,
# no la correccion de un bug de datos.
by_dept["log_n_procesos"] = by_dept["n_procesos"].apply(lambda x: 0 if x <= 0 else math.log10(x))
geojson = load_geojson()
fig_map = px.choropleth(
    by_dept,
    geojson=geojson,
    locations="buyer_department",
    featureidkey="properties.NOMBDEP",
    color="log_n_procesos",
    color_continuous_scale="Viridis",
    hover_data={"n_procesos": True, "log_n_procesos": False},
    scope=None,
)
fig_map.update_coloraxes(colorbar_title="n_procesos (escala log)")
fig_map.update_geos(fitbounds="locations", visible=False)
st.plotly_chart(fig_map, use_container_width=True)

# --- Caja de preguntas (RAG hibrido) ---
st.subheader("Buscar procesos por descripción (RAG híbrido)")
st.caption(
    "Búsqueda semántica + léxica (BM25) combinadas — ver docs/tarea2_fase3_rag_hibrido.md. "
    "Recall@5 medido en evaluación: 0.8 (mejoró de 0.3 al agregar BM25). **Importante**: escribir "
    "un departamento en el texto (ej. 'en Cusco') NO filtra los resultados a ese departamento — "
    "solo influye levemente en el ranking. Para filtrar de verdad por departamento, usa el "
    "selector de la barra lateral."
)
query = st.text_input("Describe lo que buscas (ej. 'obras de agua potable en Cusco'):")
if query.strip():
    filters = {}
    if sel_department != "(Todos)":
        filters["department"] = sel_department
    results = search(query, top_k=10, similarity_threshold=sel_similarity, **filters)
    if not results:
        st.warning("No se encontraron procesos por encima del umbral de similitud con los filtros actuales.")
    else:
        st.dataframe(
            pd.DataFrame(results)[["ocid", "buyer_name", "buyer_department", "tender_title", "amount_pen", "similarity"]],
            use_container_width=True,
        )

# --- Tabla clasificada ---
st.subheader("Procesos filtrados (tabla completa)")
st.dataframe(
    filtered[["ocid", "buyer_name", "buyer_department", "main_category", "tender_title", "amount_pen", "date_published", "number_of_tenderers"]]
    .sort_values("amount_pen", ascending=False),
    use_container_width=True,
)

# --- Distribuciones ---
st.subheader("Distribuciones")
col_a, col_b = st.columns(2)
with col_a:
    fig_cat = px.pie(filtered, names="main_category", title="Procesos por categoría")
    st.plotly_chart(fig_cat, use_container_width=True)
with col_b:
    fig_amt = px.histogram(filtered, x="amount_pen", nbins=40, title="Distribución de montos (PEN)")
    st.plotly_chart(fig_amt, use_container_width=True)

# --- Indicador de riesgo ---
st.subheader("Indicador de riesgo: adjudicaciones a postor único")
st.info(risk["advertencia"])
col_c, col_d = st.columns(2)
with col_c:
    st.markdown("**Por departamento**")
    st.dataframe(pd.DataFrame(risk["by_department"]), use_container_width=True)
with col_d:
    st.markdown(f"**Top 10 compradores** (mínimo {risk['min_processes_threshold_for_buyer_ranking']} procesos adjudicados)")
    st.dataframe(pd.DataFrame(risk["top10_buyers_single_bidder_share"]), use_container_width=True)

# --- Panel de calidad ---
st.subheader("Panel de calidad de datos")
st.caption("Ver docs/tarea2_fase2_validacion.md para el detalle y la corrección del bug de detección de codificación.")
st.dataframe(pd.DataFrame(quality["per_month"]), use_container_width=True)
