"""Páginas da interface do Manikas."""
import json
import logging
from datetime import date

import pandas as pd
import streamlit as st

import db
import ia
from planos import ORDEM, PLANOS, beneficios, preco_fmt

log = logging.getLogger("manikas")
COR = "#1F47D1"

P_CHAT, P_PLANO, P_EVOL, P_PLANOS, P_CONTA = "Chat", "Meu plano", "Evolução", "Planos", "Conta"

SEXOS = ["Feminino", "Masculino", "Prefiro não informar"]
OBJETIVOS = ["Emagrecer", "Ganhar massa muscular", "Condicionamento físico", "Saúde e bem-estar"]
NIVEIS = ["Iniciante", "Intermediário", "Avançado"]
LOCAIS = ["Academia", "Em casa, sem equipamentos", "Em casa, com equipamentos básicos", "Ao ar livre"]

COLS_TREINO = {"exercicio": "Exercício", "series": "Séries", "reps": "Reps", "descanso": "Descanso", "obs": "Observações"}
COLS_CARGA = {"data": "Data", "exercicio": "Exercício", "carga_kg": "Carga (kg)", "reps": "Reps"}
COLS_PESO = {"data": "Data", "kg": "Peso (kg)"}

TXT = {
    "treino": {
        "vazio": "Você ainda não gerou seu treino. O Manikas monta um com base no seu perfil.",
        "gerar": "Gerar meu treino",
        "novo": "Gerar novo treino",
        "espera": "Montando seu treino...",
    },
    "dieta": {
        "vazio": "Você ainda não gerou sua dieta. O Manikas monta uma com base no seu perfil.",
        "gerar": "Gerar minha dieta",
        "novo": "Gerar nova dieta",
        "espera": "Montando sua dieta...",
    },
}


# ---------- Utilidades ----------
def ir_para(pagina):
    st.session_state["menu"] = pagina


def avisar(mensagem):
    st.session_state["flash"] = mensagem


def _usuario():
    return db.usuario(st.session_state["uid"])


def _idx(opcoes, valor):
    return opcoes.index(valor) if valor in opcoes else 0


def _br(iso):
    return date.fromisoformat(iso).strftime("%d/%m/%Y")


def _kg(valor):
    return f"{valor:g}".replace(".", ",") + " kg"


def _bloqueado(recurso, plano_id):
    st.info(f"{recurso} a partir do plano {PLANOS[plano_id]['nome']}.")
    st.button("Ver planos", key=f"ver_{recurso}", on_click=ir_para, args=(P_PLANOS,))


# ---------- Acesso e perfil ----------
def tela_auth():
    _, centro, _ = st.columns([1, 2, 1])
    with centro:
        st.markdown("# Manikas")
        st.write("Treino e alimentação orientados por IA, ajustados ao seu progresso.")
        entrar, criar = st.tabs(["Entrar", "Criar conta"])

        with entrar, st.form("form_login"):
            email = st.text_input("E-mail", key="login_email")
            senha = st.text_input("Senha", type="password", key="login_senha")
            if st.form_submit_button("Entrar", type="primary"):
                uid = db.autenticar(email, senha)
                if uid:
                    st.session_state["uid"] = uid
                    st.rerun()
                st.error("E-mail ou senha incorretos. Confira os dados e tente de novo.")

        with criar, st.form("form_cadastro"):
            nome = st.text_input("Nome", key="cad_nome")
            email = st.text_input("E-mail", key="cad_email")
            senha = st.text_input("Senha (mínimo de 8 caracteres)", type="password", key="cad_senha")
            aceite = st.checkbox(
                "Tenho 18 anos ou mais e concordo com o uso dos meus dados de saúde "
                "(peso, altura, treino, fotos) para personalizar meu plano.",
                key="cad_aceite",
            )
            if st.form_submit_button("Criar conta", type="primary"):
                if not nome.strip():
                    st.error("Informe seu nome para criar a conta.")
                elif not aceite:
                    st.error("Marque a confirmação de idade e de uso dos dados para continuar.")
                else:
                    try:
                        st.session_state["uid"] = db.criar_usuario(nome, email, senha)
                        st.rerun()
                    except ValueError as erro:
                        st.error(str(erro))


def tela_perfil(u, primeiro_acesso=False):
    p = u["perfil"]
    if primeiro_acesso:
        _, centro, _ = st.columns([1, 3, 1])
        with centro:
            st.markdown("# Conte sobre você")
            st.write("Esses dados orientam o treino e a dieta. Você pode editá-los depois, na aba Conta.")
            _form_perfil(u, p, primeiro_acesso)
    else:
        _form_perfil(u, p, primeiro_acesso)


def _form_perfil(u, p, primeiro_acesso):
    with st.form("form_perfil"):
        c1, c2 = st.columns(2)
        idade = c1.number_input("Idade", 18, 100, int(p.get("idade", 25)))
        sexo = c2.selectbox("Sexo", SEXOS, index=_idx(SEXOS, p.get("sexo")))
        peso = c1.number_input("Peso (kg)", 30.0, 300.0, float(p.get("peso", 70.0)), 0.5)
        altura = c2.number_input("Altura (cm)", 100, 250, int(p.get("altura", 170)))
        objetivo = st.selectbox("Objetivo", OBJETIVOS, index=_idx(OBJETIVOS, p.get("objetivo")))
        nivel = st.selectbox("Nível de experiência", NIVEIS, index=_idx(NIVEIS, p.get("nivel")))
        dias = st.slider("Dias de treino por semana", 1, 7, int(p.get("dias", 3)))
        local = st.selectbox("Onde você treina?", LOCAIS, index=_idx(LOCAIS, p.get("local")))
        restricoes = st.text_area(
            "Lesões, condições de saúde ou restrições alimentares (opcional)",
            value=p.get("restricoes", ""),
            help="Ex.: dor no joelho direito, intolerância à lactose, vegetariano.",
        )
        if st.form_submit_button("Salvar perfil", type="primary"):
            db.salvar_perfil(
                u["id"],
                {
                    "idade": idade, "sexo": sexo, "peso": peso, "altura": altura, "objetivo": objetivo,
                    "nivel": nivel, "dias": dias, "local": local, "restricoes": restricoes.strip(),
                },
            )
            if peso != p.get("peso"):
                db.registrar_peso(u["id"], peso)
            if primeiro_acesso:
                st.rerun()
            st.success("Perfil salvo. Os próximos planos e respostas já usam os dados novos.")


# ---------- Chat ----------
SUGESTOES = [
    "Monte um treino para esta semana",
    "Sugira um cardápio para hoje",
    "Como melhorar minha execução do agachamento?",
]

# Funciona em tema claro e escuro: só o balão do usuário e o avatar têm cor fixa (cobalto com texto branco);
# o resto usa transparência e herda a cor do texto do tema.
ESTILO_CHAT = """
<style>
.block-container { max-width: 780px; }
.stApp [data-testid="stChatMessage"] { padding: 0.35rem 0; background: transparent; }
.stApp [data-testid="stChatMessageContent"] { margin: 0; flex: 0 1 auto; padding: 0.65rem 1rem; }
.stApp [data-testid="stChatMessageContent"] [data-testid="stMarkdownContainer"] > :last-child { margin-bottom: 0; }

/* Manikas: balão branco à esquerda, avatar em cobalto */
.stApp [data-testid="stChatMessage"]:has([aria-label="Chat message from assistant"]) [data-testid="stChatMessageContent"] {
    max-width: 92%; background: rgba(128, 128, 128, 0.12); border: 1px solid rgba(128, 128, 128, 0.30); border-radius: 18px 18px 18px 4px;
}
.stApp [data-testid="stChatMessageAvatarAssistant"] { background: #1F47D1 !important; color: #FFFFFF !important; }

/* Usuário: balão azul à direita, sem avatar */
.stApp [data-testid="stChatMessage"]:has([aria-label="Chat message from user"]) { flex-direction: row-reverse; }
.stApp [data-testid="stChatMessage"]:has([aria-label="Chat message from user"]) [data-testid^="stChatMessageAvatar"] { display: none; }
.stApp [data-testid="stChatMessage"]:has([aria-label="Chat message from user"]) [data-testid="stChatMessageContent"] {
    max-width: 85%; background: #1F47D1; border-radius: 18px 18px 4px 18px;
}
.stApp [data-testid="stChatMessage"]:has([aria-label="Chat message from user"]) [data-testid="stChatMessageContent"] * { color: #FFFFFF !important; }

/* Campo de mensagem */
.stApp [data-testid="stChatInput"] { border: 1px solid rgba(128, 128, 128, 0.45); border-radius: 14px; }
.stApp [data-testid="stChatInput"]:focus-within { border-color: #1F47D1; box-shadow: 0 0 0 3px rgba(31, 71, 209, 0.15); }
</style>
"""


def _sugerir(texto):
    st.session_state["sugestao"] = texto


def _sem_espera(fluxo, espaco):
    """Remove o aviso 'digitando' quando chega o primeiro pedaço da resposta."""
    for i, parte in enumerate(fluxo):
        if i == 0:
            espaco.empty()
        yield parte


def pg_chat():
    st.markdown(ESTILO_CHAT, unsafe_allow_html=True)
    u = _usuario()
    uid, p = u["id"], PLANOS[u["plano"]]
    restantes = max(p["msgs_dia"] - db.uso_hoje(uid), 0)
    sugestao = st.session_state.pop("sugestao", None)
    historico = db.msgs(uid, 100)

    titulo, limpar = st.columns([3, 1], vertical_alignment="center")
    titulo.title("Chat")
    if historico:
        limpar.button("Limpar conversa", on_click=db.limpar_chat, args=(uid,))
    st.caption(f"Plano {p['nome']}. Restam {restantes} de {p['msgs_dia']} mensagens hoje.")

    if not historico:
        with st.chat_message("assistant"):
            st.markdown(
                f"Olá, {u['nome'].split()[0]}. Já tenho o seu perfil, então pode ir direto ao ponto: "
                "o que você quer ajustar no treino ou na alimentação?"
            )
        if restantes and not sugestao:
            st.caption("Toque em uma sugestão ou escreva a sua mensagem.")
            for coluna, texto in zip(st.columns(len(SUGESTOES)), SUGESTOES):
                coluna.button(texto, key=f"sug_{texto}", on_click=_sugerir, args=(texto,))
    for m in historico:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])

    if restantes == 0:
        st.warning("Suas mensagens de hoje acabaram. Elas voltam amanhã, ou você pode mudar de plano agora.")
        st.button("Ver planos", on_click=ir_para, args=(P_PLANOS,))
        return

    if prompt := (st.chat_input("Escreva sua mensagem") or sugestao):
        db.add_msg(uid, "user", prompt)
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.chat_message("assistant"):
            digitando = st.empty()
            digitando.caption("Manikas está digitando...")
            try:
                fluxo = ia.conversar(u["perfil"], db.progresso(uid)[-10:], db.msgs(uid, 20))
                resposta = st.write_stream(_sem_espera(fluxo, digitando))
            except Exception:
                log.exception("Falha ao responder no chat")
                digitando.empty()
                st.error("A resposta não foi gerada por uma falha na conexão com a IA. Envie a mensagem de novo.")
                return
        db.add_msg(uid, "assistant", resposta)
        db.registrar_uso(uid)
        st.rerun()


# ---------- Meu plano ----------
def _mostrar_treino(plano):
    st.markdown(plano.get("resumo", ""))
    dias = plano.get("dias", [])
    if dias:
        abas = st.tabs([d.get("nome", f"Dia {i}") for i, d in enumerate(dias, 1)])
        for aba, dia in zip(abas, dias):
            with aba:
                tabela = pd.DataFrame(dia.get("exercicios", [])).astype(str)
                st.dataframe(tabela.rename(columns=COLS_TREINO), hide_index=True)


def _mostrar_dieta(plano):
    st.markdown(plano.get("resumo", ""))
    macros = plano.get("macros", {})
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Calorias por dia", f"{plano.get('calorias', '-')} kcal")
    c2.metric("Proteína", f"{macros.get('proteina_g', '-')} g")
    c3.metric("Carboidratos", f"{macros.get('carboidrato_g', '-')} g")
    c4.metric("Gorduras", f"{macros.get('gordura_g', '-')} g")
    for refeicao in plano.get("refeicoes", []):
        with st.container(border=True):
            st.markdown(f"**{refeicao.get('nome', 'Refeição')}** às {refeicao.get('horario', '-')}")
            st.markdown("\n".join(f"- {item}" for item in refeicao.get("itens", [])))
            if refeicao.get("obs"):
                st.caption(refeicao["obs"])


def _bloco_plano(u, tipo):
    uid, p, txt = u["id"], PLANOS[u["plano"]], TXT[tipo]
    plano, atualizado = db.plano_ia(uid, tipo)
    if plano:
        st.caption(f"Atualizado em {_br(atualizado)}")
        (_mostrar_treino if tipo == "treino" else _mostrar_dieta)(plano)
        if plano.get("dicas"):
            with st.expander("Dicas"):
                st.markdown("\n".join(f"- {dica}" for dica in plano["dicas"]))
        rotulo = "Reajustar com base no meu progresso" if p["reajuste"] else txt["novo"]
    else:
        st.info(txt["vazio"])
        rotulo = txt["gerar"]

    if st.button(rotulo, key=f"gerar_{tipo}", type="primary"):
        with st.spinner(txt["espera"]):
            try:
                usar_progresso = p["reajuste"]
                novo = ia.gerar_plano(
                    tipo,
                    u["perfil"],
                    db.progresso(uid) if usar_progresso else None,
                    db.pesos(uid) if usar_progresso else None,
                )
            except Exception:
                log.exception("Falha ao gerar %s", tipo)
                st.error("Não foi possível gerar agora por uma falha na conexão com a IA. Clique de novo para tentar.")
                return
        db.salvar_plano_ia(uid, tipo, novo)
        st.rerun()


def pg_plano():
    u = _usuario()
    st.title("Meu plano")
    t_treino, t_dieta = st.tabs(["Treino", "Dieta"])
    with t_treino:
        _bloco_plano(u, "treino")
    with t_dieta:
        if PLANOS[u["plano"]]["dieta"]:
            _bloco_plano(u, "dieta")
        else:
            _bloqueado("A dieta personalizada está disponível", "pro")


# ---------- Evolução ----------
def pg_evolucao():
    u = _usuario()
    uid, p = u["id"], PLANOS[u["plano"]]
    st.title("Evolução")
    t_cargas, t_peso, t_fotos = st.tabs(["Cargas", "Peso", "Fotos"])

    with t_cargas:
        with st.form("form_carga", clear_on_submit=True):
            exercicio = st.text_input("Exercício")
            c1, c2 = st.columns(2)
            carga = c1.number_input("Carga (kg)", 0.0, 500.0, 0.0, 0.5)
            reps = c2.number_input("Repetições", 1, 200, 10)
            if st.form_submit_button("Registrar carga", type="primary"):
                if exercicio.strip():
                    db.add_progresso(uid, exercicio, carga, reps)
                    st.rerun()
                st.warning("Informe o nome do exercício para registrar a carga.")

        registros = db.progresso(uid)
        if not registros:
            st.info("Ainda não há registros. Anote suas cargas depois de cada treino para acompanhar a evolução.")
        else:
            df = pd.DataFrame(registros)
            if p["graficos"]:
                escolhido = st.selectbox("Exercício", sorted(df["exercicio"].unique()))
                d = df[df["exercicio"] == escolhido]
                m1, m2, m3 = st.columns(3)
                m1.metric("Recorde", _kg(d["carga_kg"].max()))
                m2.metric("Última carga", _kg(d["carga_kg"].iloc[-1]))
                m3.metric("Registros", len(d))
                st.line_chart(d.groupby("data")["carga_kg"].max(), color=COR)
            else:
                _bloqueado("Os gráficos de cargas estão disponíveis", "pro")
            st.dataframe(df.drop(columns="id").iloc[::-1].rename(columns=COLS_CARGA), hide_index=True)
            with st.expander("Excluir um registro"):
                opcoes = {
                    f"{_br(r['data'])}: {r['exercicio']}, {_kg(r['carga_kg'])} x {r['reps']}": r["id"]
                    for r in reversed(registros)
                }
                alvo = st.selectbox("Registro", list(opcoes))
                if st.button("Excluir registro"):
                    db.apagar_progresso(uid, opcoes[alvo])
                    st.rerun()

    with t_peso:
        with st.form("form_peso"):
            kg = st.number_input("Peso de hoje (kg)", 30.0, 300.0, float(u["perfil"].get("peso", 70.0)), 0.1)
            if st.form_submit_button("Registrar peso", type="primary"):
                db.registrar_peso(uid, kg)
                db.salvar_perfil(uid, {**u["perfil"], "peso": kg})
                st.rerun()
        pesos = db.pesos(uid)
        if pesos:
            df = pd.DataFrame(pesos)
            if p["graficos"] and len(df) > 1:
                variacao = df["kg"].iloc[-1] - df["kg"].iloc[0]
                st.metric(
                    "Peso atual",
                    _kg(df["kg"].iloc[-1]),
                    f"{variacao:+.1f} kg desde o primeiro registro".replace(".", ","),
                    delta_color="off",
                )
                st.line_chart(df.set_index("data")["kg"], color=COR)
            elif not p["graficos"]:
                _bloqueado("O gráfico de peso está disponível", "pro")
            st.dataframe(df.iloc[::-1].rename(columns=COLS_PESO), hide_index=True)

    with t_fotos:
        if not p["fotos"]:
            _bloqueado("A análise de fotos está disponível", "premium")
        else:
            st.caption(
                "Envie uma foto de frente, com boa iluminação. A foto vai para o provedor de IA só para esta "
                "análise e não é guardada pelo Manikas."
            )
            foto = st.file_uploader("Foto de evolução", type=["jpg", "jpeg", "png"])
            if foto and st.button("Analisar foto", type="primary"):
                if db.uso_hoje(uid) >= p["msgs_dia"]:
                    st.warning("Suas mensagens de hoje acabaram. A análise de foto conta como uma mensagem.")
                elif foto.size > 5_000_000:
                    st.warning("A imagem passa de 5 MB. Envie uma foto menor.")
                else:
                    with st.spinner("Analisando a foto..."):
                        try:
                            analise = ia.analisar_foto(u["perfil"], foto.getvalue(), foto.type)
                        except Exception:
                            log.exception("Falha na análise de foto")
                            st.error("A foto não foi analisada por uma falha na conexão com a IA. Tente de novo.")
                            return
                    db.add_msg(uid, "user", "Enviei uma foto de evolução para análise.")
                    db.add_msg(uid, "assistant", analise)
                    db.registrar_uso(uid)
                    st.markdown(analise)


# ---------- Planos ----------
def pg_planos():
    u = _usuario()
    st.title("Planos")
    st.write("Escolha o plano que acompanha o seu ritmo. Você pode trocar quando quiser.")
    st.info("Modo de demonstração: a troca de plano é simulada e nenhuma cobrança é feita.")
    for coluna, pid in zip(st.columns(3), ORDEM):
        p = PLANOS[pid]
        with coluna, st.container(border=True):
            st.subheader(p["nome"])
            st.markdown(f"## {preco_fmt(p)}")
            st.caption("por mês" if p["preco"] else "sem cobrança")
            st.markdown("\n".join(f"- {b}" for b in beneficios(pid)))
            if pid == u["plano"]:
                st.button("Seu plano atual", key=f"plano_{pid}", disabled=True)
            elif st.button(f"Escolher {p['nome']}", key=f"plano_{pid}", type="primary" if p.get("destaque") else "secondary"):
                db.definir_plano(u["id"], pid)
                avisar(f"Plano {p['nome']} ativado.")
                st.rerun()


# ---------- Conta ----------
def _exportar(u):
    uid = u["id"]
    return json.dumps(
        {
            "email": u["email"],
            "plano": u["plano"],
            "perfil": u["perfil"],
            "treino": db.plano_ia(uid, "treino")[0],
            "dieta": db.plano_ia(uid, "dieta")[0],
            "progresso": db.progresso(uid),
            "peso": db.pesos(uid),
            "mensagens": db.msgs(uid, 100_000),
        },
        ensure_ascii=False,
        indent=2,
    )


def pg_conta():
    u = _usuario()
    st.title("Conta")
    st.caption(f"{u['nome']}  \n{u['email']}")
    st.subheader("Perfil")
    tela_perfil(u)
    st.subheader("Seus dados")
    st.download_button("Baixar meus dados (JSON)", _exportar(u), "meus_dados_manikas.json", "application/json")
    with st.expander("Excluir minha conta"):
        st.warning("Isso apaga para sempre seu perfil, conversas, planos e registros de evolução.")
        if st.checkbox("Entendo que não é possível desfazer") and st.button("Excluir conta", type="primary"):
            db.apagar_conta(u["id"])
            st.session_state.clear()
            st.rerun()


ROTAS = {P_CHAT: pg_chat, P_PLANO: pg_plano, P_EVOL: pg_evolucao, P_PLANOS: pg_planos, P_CONTA: pg_conta}
