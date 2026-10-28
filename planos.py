"""Planos de assinatura do Manikas. Edite preços, limites e benefícios aqui."""

PLANOS = {
    "basico": {
        "nome": "Básico",
        "preco": 0.0,
        "msgs_dia": 10,
        "dieta": False,
        "graficos": False,
        "fotos": False,
        "reajuste": False,
        "extras": ["Treino personalizado", "Registro de cargas e de peso"],
    },
    "pro": {
        "nome": "Pro",
        "preco": 29.90,
        "msgs_dia": 50,
        "destaque": True,
        "dieta": True,
        "graficos": True,
        "fotos": False,
        "reajuste": False,
        "extras": ["Treino e dieta personalizados", "Gráficos e métricas de evolução"],
    },
    "premium": {
        "nome": "Premium",
        "preco": 59.90,
        "msgs_dia": 200,
        "dieta": True,
        "graficos": True,
        "fotos": True,
        "reajuste": True,
        "extras": [
            "Tudo do plano Pro",
            "Análise de fotos de evolução",
            "Reajuste do treino e da dieta com base no seu progresso",
        ],
    },
}
ORDEM = list(PLANOS)


def preco_fmt(plano):
    if not plano["preco"]:
        return "Grátis"
    return f"R$ {plano['preco']:.2f}".replace(".", ",")


def beneficios(plano_id):
    p = PLANOS[plano_id]
    return [f"{p['msgs_dia']} mensagens por dia no chat", *p["extras"]]
