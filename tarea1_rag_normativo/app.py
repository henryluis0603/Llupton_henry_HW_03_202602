"""Fase 5 (Tarea 1): interfaz Streamlit.

Correr con: streamlit run app.py
Muestra: respuesta, fragmentos citados, estado de abstencion y costo de
la consulta, como pide el enunciado.
"""
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))
from src import engine  # noqa: E402

st.set_page_config(page_title="RAG Normativo — Contrataciones Públicas", page_icon="📜")

st.title("Asistente normativo de contratación pública (Perú)")
st.caption(
    "Responde solo con base en la Ley N.° 32069 y el D.S. N.° 001-2026-EF. "
    "Si la pregunta está fuera de estos documentos, el sistema lo indica en vez de inventar."
)

with st.sidebar:
    st.markdown("### Corpus indexado")
    st.markdown("- Ley N.° 32069 (Ley General de Contrataciones Públicas)")
    st.markdown("- D.S. N.° 001-2026-EF (modifica el Reglamento)")
    st.markdown("---")
    st.markdown(
        "**Limitación conocida** (ver `docs/fase4_evaluacion.md`): el filtro de similitud solo "
        "abstiene el 40% de las preguntas fuera de dominio; una segunda capa en la generación "
        "cubre el resto, verificada con pruebas reales."
    )

question = st.text_input("Escribe tu pregunta sobre contratación pública:")

if st.button("Consultar") and question.strip():
    with st.spinner("Buscando en el corpus y generando la respuesta..."):
        try:
            result = engine.answer_query(question)
        except Exception as exc:  # noqa: BLE001 - se muestra el error real al usuario, no se oculta
            st.error(f"Error al procesar la consulta: {exc}")
            result = None

    if result:
        if result["abstained"]:
            st.warning(result["answer"])
        else:
            st.success(result["answer"])
            st.markdown("#### Fragmentos citados")
            for c in result["citations"]:
                st.markdown(
                    f"- **{c['doc_id']} — {c['unit_label']}** "
                    f"({c.get('section') or 'cuerpo principal'}, pág. {c['page']}, "
                    f"{c['version_label']}) — similitud: `{c['similarity']}`"
                )

        col1, col2, col3 = st.columns(3)
        col1.metric("Similitud máxima", result["top_similarity"])
        col2.metric("Costo de la consulta (USD)", f"${result['cost_usd']:.4f}")
        col3.metric("Latencia (s)", result["latency_s"])
