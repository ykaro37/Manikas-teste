"""Manikas: personal trainer e nutricionista com IA. Execute com: streamlit run app.py"""
import logging
import os

import streamlit as st
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

import db  # noqa: E402
import paginas  # noqa: E402
from planos import PLANOS  # noqa: E402

st.set_page_config(page_title="Manikas, treino e nutrição com IA", page_icon="💪", layout="wide")

# Títulos e números em Barlow Condensed (tipografia de placar/sinalização de academia).
# Se a fonte não carregar, cai para Arial Narrow ou a fonte padrão.
ESTILO = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600;700&display=swap');
.stApp h1, .stApp h2, .stApp h3, .stApp [data-testid="stMetricValue"] {
    font-family: 'Barlow Condensed', 'Arial Narrow', sans-serif !important;
    letter-spacing: -0.01em;
}
.stApp h1 { font-size: 3rem; font-weight: 700; }
.stApp h2, .stApp h3 { font-weight: 600; }
.stApp [data-testid="stMetricValue"] { font-size: 2.6rem; font-weight: 700; }
.block-container { max-width: 980px; padding-top: 2.5rem; }
.stButton > button, .stDownloadButton > button { border-radius: 8px; font-weight: 600; }
#MainMenu, footer { visibility: hidden; }
</style>
"""
st.markdown(ESTILO, unsafe_allow_html=True)


@st.cache_resource
def _iniciar_banco():
    db.iniciar()


if not os.getenv("OPENAI_API_KEY"):
    st.error("A chave da OpenAI não está configurada. Crie um arquivo .env com OPENAI_API_KEY=sua-chave e reinicie o app.")
    st.stop()
_iniciar_banco()

if "uid" not in st.session_state:
    paginas.tela_auth()
    st.stop()

usuario = db.usuario(st.session_state["uid"])
if usuario is None:  # conta removida
    st.session_state.clear()
    st.rerun()
if not usuario["perfil"]:
    paginas.tela_perfil(usuario, primeiro_acesso=True)
    st.stop()

with st.sidebar:
    st.markdown("## Manikas")
    st.caption(f"{usuario['nome']}  \nPlano {PLANOS[usuario['plano']]['nome']}")
    pagina = st.radio("Menu", list(paginas.ROTAS), key="menu", label_visibility="collapsed")
    st.divider()
    if st.button("Sair"):
        st.session_state.clear()
        st.rerun()
    st.caption("O Manikas é um assistente de IA. Ele não substitui médico, nutricionista ou educador físico.")

if aviso := st.session_state.pop("flash", None):
    st.toast(aviso)
paginas.ROTAS[pagina]()
