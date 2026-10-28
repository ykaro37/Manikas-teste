"""Camada de dados do Manikas (SQLite)."""
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone

SCHEMA = """
CREATE TABLE IF NOT EXISTS usuarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    nome TEXT NOT NULL,
    salt TEXT NOT NULL,
    senha_hash TEXT NOT NULL,
    plano TEXT NOT NULL DEFAULT 'basico',
    perfil TEXT NOT NULL DEFAULT '{}',
    criado_em TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS mensagens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id INTEGER NOT NULL,
    role TEXT NOT NULL,
    conteudo TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_mensagens ON mensagens (usuario_id, id);
CREATE TABLE IF NOT EXISTS uso (
    usuario_id INTEGER NOT NULL,
    dia TEXT NOT NULL,
    n INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (usuario_id, dia)
);
CREATE TABLE IF NOT EXISTS planos_ia (
    usuario_id INTEGER NOT NULL,
    tipo TEXT NOT NULL,
    conteudo TEXT NOT NULL,
    atualizado_em TEXT NOT NULL,
    PRIMARY KEY (usuario_id, tipo)
);
CREATE TABLE IF NOT EXISTS progresso (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id INTEGER NOT NULL,
    data TEXT NOT NULL,
    exercicio TEXT NOT NULL,
    carga_kg REAL NOT NULL,
    reps INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_progresso ON progresso (usuario_id, data);
CREATE TABLE IF NOT EXISTS peso (
    usuario_id INTEGER NOT NULL,
    data TEXT NOT NULL,
    kg REAL NOT NULL,
    PRIMARY KEY (usuario_id, data)
);
"""

FUSO = timezone(timedelta(hours=-3))  # Brasília (sem horário de verão)


def hoje():
    return datetime.now(FUSO).date().isoformat()


def _con():
    con = sqlite3.connect(os.getenv("DB_PATH", "manikas.db"))
    con.row_factory = sqlite3.Row
    return con


def _exec(sql, params=()):
    with closing(_con()) as con, con:
        return con.execute(sql, params).lastrowid


def _all(sql, params=()):
    with closing(_con()) as con:
        return [dict(r) for r in con.execute(sql, params)]


def _one(sql, params=()):
    rows = _all(sql, params)
    return rows[0] if rows else None


def iniciar():
    with closing(_con()) as con, con:
        con.executescript(SCHEMA)


# ---------- Contas ----------
def _hash(senha, salt):
    return hashlib.pbkdf2_hmac("sha256", senha.encode(), salt, 200_000).hex()


def criar_usuario(nome, email, senha):
    email = email.strip().lower()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise ValueError("Informe um e-mail válido.")
    if len(senha) < 8:
        raise ValueError("A senha precisa ter pelo menos 8 caracteres.")
    salt = secrets.token_bytes(16)
    try:
        return _exec(
            "INSERT INTO usuarios (email, nome, salt, senha_hash, criado_em) VALUES (?, ?, ?, ?, ?)",
            (email, nome.strip(), salt.hex(), _hash(senha, salt), hoje()),
        )
    except sqlite3.IntegrityError:
        raise ValueError("Este e-mail já tem uma conta. Use a aba Entrar.") from None


def autenticar(email, senha):
    u = _one("SELECT id, salt, senha_hash FROM usuarios WHERE email = ?", (email.strip().lower(),))
    if u and hmac.compare_digest(_hash(senha, bytes.fromhex(u["salt"])), u["senha_hash"]):
        return u["id"]
    return None


def usuario(uid):
    u = _one("SELECT id, email, nome, plano, perfil FROM usuarios WHERE id = ?", (uid,))
    if u:
        u["perfil"] = json.loads(u["perfil"])
    return u


def salvar_perfil(uid, perfil):
    _exec("UPDATE usuarios SET perfil = ? WHERE id = ?", (json.dumps(perfil, ensure_ascii=False), uid))


def definir_plano(uid, plano):
    """Ativa um plano. Ao integrar pagamento real, chame esta função a partir do webhook."""
    _exec("UPDATE usuarios SET plano = ? WHERE id = ?", (plano, uid))


def apagar_conta(uid):
    with closing(_con()) as con, con:
        for tabela in ("mensagens", "uso", "planos_ia", "progresso", "peso"):
            con.execute(f"DELETE FROM {tabela} WHERE usuario_id = ?", (uid,))
        con.execute("DELETE FROM usuarios WHERE id = ?", (uid,))


# ---------- Chat e uso diário ----------
def add_msg(uid, role, conteudo):
    _exec("INSERT INTO mensagens (usuario_id, role, conteudo) VALUES (?, ?, ?)", (uid, role, conteudo))


def msgs(uid, limite=100):
    rows = _all(
        "SELECT role, conteudo AS content FROM mensagens WHERE usuario_id = ? ORDER BY id DESC LIMIT ?",
        (uid, limite),
    )
    return rows[::-1]


def limpar_chat(uid):
    _exec("DELETE FROM mensagens WHERE usuario_id = ?", (uid,))


def registrar_uso(uid):
    _exec(
        "INSERT INTO uso (usuario_id, dia, n) VALUES (?, ?, 1) "
        "ON CONFLICT (usuario_id, dia) DO UPDATE SET n = n + 1",
        (uid, hoje()),
    )


def uso_hoje(uid):
    r = _one("SELECT n FROM uso WHERE usuario_id = ? AND dia = ?", (uid, hoje()))
    return r["n"] if r else 0


# ---------- Treino e dieta gerados ----------
def salvar_plano_ia(uid, tipo, conteudo):
    _exec(
        "INSERT INTO planos_ia (usuario_id, tipo, conteudo, atualizado_em) VALUES (?, ?, ?, ?) "
        "ON CONFLICT (usuario_id, tipo) DO UPDATE SET "
        "conteudo = excluded.conteudo, atualizado_em = excluded.atualizado_em",
        (uid, tipo, json.dumps(conteudo, ensure_ascii=False), hoje()),
    )


def plano_ia(uid, tipo):
    r = _one("SELECT conteudo, atualizado_em FROM planos_ia WHERE usuario_id = ? AND tipo = ?", (uid, tipo))
    return (json.loads(r["conteudo"]), r["atualizado_em"]) if r else (None, None)


# ---------- Progresso e peso ----------
def add_progresso(uid, exercicio, carga, reps):
    _exec(
        "INSERT INTO progresso (usuario_id, data, exercicio, carga_kg, reps) VALUES (?, ?, ?, ?, ?)",
        (uid, hoje(), exercicio.strip().capitalize(), carga, reps),
    )


def progresso(uid):
    return _all(
        "SELECT id, data, exercicio, carga_kg, reps FROM progresso WHERE usuario_id = ? ORDER BY data, id",
        (uid,),
    )


def apagar_progresso(uid, registro_id):
    _exec("DELETE FROM progresso WHERE id = ? AND usuario_id = ?", (registro_id, uid))


def registrar_peso(uid, kg):
    _exec("INSERT OR REPLACE INTO peso (usuario_id, data, kg) VALUES (?, ?, ?)", (uid, hoje(), kg))


def pesos(uid):
    return _all("SELECT data, kg FROM peso WHERE usuario_id = ? ORDER BY data", (uid,))
