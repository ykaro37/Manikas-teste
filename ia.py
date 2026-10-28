"""Integração com a OpenAI: chat, geração de planos e análise de fotos."""
import base64
import json
import os

from openai import OpenAI

SISTEMA = (
    "Você é o Manikas, assistente virtual de treino e alimentação, com o apoio de um personal trainer "
    "e de um nutricionista. Responda em português do Brasil, de forma curta, clara e acolhedora. "
    "Use os dados do cliente abaixo e não pergunte o que ele já informou. "
    "Faça no máximo 2 perguntas por vez, apenas quando faltar uma informação essencial. "
    "Segurança: não prescreva dietas extremas, jejuns prolongados, medicamentos nem suplementos controlados. "
    "Se houver lesão, doença, gravidez, uso de medicamentos ou menor de 18 anos, oriente a procurar "
    "médico, nutricionista ou educador físico. Você não faz diagnósticos."
)

FORMATOS = {
    "treino": (
        '{"resumo": "texto curto", "dias": [{"nome": "Dia 1 - Peito e tríceps", "exercicios": '
        '[{"exercicio": "nome", "series": 3, "reps": "8-12", "descanso": "60s", "obs": "dica de execução"}]}], '
        '"dicas": ["texto"]}'
    ),
    "dieta": (
        '{"resumo": "texto curto", "calorias": 2200, "macros": {"proteina_g": 150, "carboidrato_g": 250, '
        '"gordura_g": 70}, "refeicoes": [{"nome": "Café da manhã", "horario": "07:30", '
        '"itens": ["alimento e quantidade"], "obs": "texto"}], "dicas": ["texto"]}'
    ),
}
CHAVE_OBRIGATORIA = {"treino": "dias", "dieta": "refeicoes"}

_cliente = None


def _api():
    global _cliente
    if _cliente is None:
        _cliente = OpenAI(api_key=os.getenv("OPENAI_API_KEY"), timeout=60, max_retries=2)
    return _cliente


def _modelo():
    return os.getenv("OPENAI_MODEL", "gpt-4o-mini")


def _sistema(perfil, progresso=None):
    texto = f"{SISTEMA}\n\nDados do cliente: {json.dumps(perfil, ensure_ascii=False)}"
    if progresso:
        texto += f"\nProgresso recente: {json.dumps(progresso, ensure_ascii=False)}"
    return texto


def conversar(perfil, progresso, historico):
    """Gera a resposta do chat em streaming (as últimas 20 mensagens entram no contexto)."""
    mensagens = [{"role": "system", "content": _sistema(perfil, progresso)}, *historico[-20:]]
    for parte in _api().chat.completions.create(model=_modelo(), messages=mensagens, stream=True):
        if parte.choices and parte.choices[0].delta.content:
            yield parte.choices[0].delta.content


def gerar_plano(tipo, perfil, progresso=None, pesos=None):
    """Gera treino ou dieta como dicionário. Se houver progresso, o plano é reajustado com base nele."""
    pedido = (
        f"Monte um plano de {tipo} personalizado para este cliente. Respeite o objetivo, o nível, "
        "os dias de treino por semana, o local de treino e as restrições informadas. "
        f"Responda SOMENTE com um JSON válido neste formato: {FORMATOS[tipo]}"
    )
    if progresso or pesos:
        pedido += (
            "\nReajuste o plano considerando a evolução do cliente. "
            f"Cargas registradas: {json.dumps((progresso or [])[-30:], ensure_ascii=False)}. "
            f"Histórico de peso: {json.dumps((pesos or [])[-10:], ensure_ascii=False)}."
        )
    resposta = _api().chat.completions.create(
        model=_modelo(),
        temperature=0.4,
        response_format={"type": "json_object"},
        messages=[{"role": "system", "content": _sistema(perfil)}, {"role": "user", "content": pedido}],
    )
    plano = json.loads(resposta.choices[0].message.content)
    if not plano.get(CHAVE_OBRIGATORIA[tipo]):
        raise ValueError("A IA devolveu um plano incompleto.")
    return plano


def analisar_foto(perfil, imagem, mime):
    """Analisa uma foto de evolução. A imagem não é guardada: segue direto para a API."""
    url = f"data:{mime};base64,{base64.b64encode(imagem).decode()}"
    pedido = (
        "Esta é uma foto de acompanhamento da evolução física do cliente. Faça uma análise respeitosa e "
        "objetiva: 3 observações (postura, simetria, pontos de atenção) e 3 ajustes sugeridos para treino "
        "ou alimentação. Não estime percentual de gordura, não faça diagnósticos e não emita julgamentos "
        "sobre a aparência. Seja breve."
    )
    resposta = _api().chat.completions.create(
        model=_modelo(),
        messages=[
            {"role": "system", "content": _sistema(perfil)},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": pedido},
                    {"type": "image_url", "image_url": {"url": url}},
                ],
            },
        ],
    )
    return resposta.choices[0].message.content
