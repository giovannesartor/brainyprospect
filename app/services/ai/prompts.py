"""Prompts em português usados pelos serviços de IA — sensíveis a modo e contexto."""
from __future__ import annotations

SYSTEM_SDR = (
    "Você é um SDR e estrategista comercial sênior brasileiro especializado em prospecção B2B. "
    "Você raciocina sobre dois modelos comerciais: (1) VENDA DIRETA — encontrar clientes "
    "finais que precisam do serviço; e (2) PARCEIROS — encontrar canais/multiplicadores "
    "(contabilidades, advogados, consultorias, assessorias) capazes de indicar muitos clientes. "
    "Você analisa negócios, identifica ICP por modelo, prioriza leads, calcula match comercial, "
    "estima ticket potencial e sugere abordagens, canais e follow-ups. "
    "Suas respostas SEMPRE são objetivas, em português. "
    "Quando solicitado JSON, responda APENAS com JSON válido, sem markdown nem comentários."
)


def prompt_analyze_site(url: str, site_text: str) -> str:
    return f"""Analise o negócio abaixo a partir do site informado. Pense como um SDR estratégico.

URL: {url}

CONTEÚDO EXTRAÍDO (texto puro, pode estar truncado):
\"\"\"{site_text[:9000]}\"\"\"

ANTES DE RESPONDER, FAÇA ESTA ANÁLISE OBRIGATÓRIA:
1. Releia o conteúdo e LISTE MENTALMENTE todos os serviços/produtos distintos
   mencionados (procure em: títulos, headings H1/H2/H3, menus, seções "Serviços",
   "Soluções", "O que fazemos", "Produtos", botoes de CTA, planos, pacotes).
2. Cada serviço com NOME PRÓPRIO ou que possa ser vendido SEPARADAMENTE é um produto
   distinto. Exemplos de produtos distintos:
   - "Valuation" e "Pitch Deck" → 2 produtos (compradores diferentes)
   - "Contabilidade", "Departamento Pessoal" e "Fiscal" → 3 produtos
   - "SEO", "Tráfego Pago" e "Social Media" → 3 produtos
   - Apenas "Software de gestão para clínicas" → 1 produto
3. NUNCA agrupe produtos diferentes em um único item só porque são do mesmo nicho.
   Se o site oferece 3 serviços com nomes distintos, devolva 3 itens em "products".

Retorne JSON com schema EXATO:
{{
  "business_type": "string curta (ex: 'Valuation Empresarial')",
  "summary": "resumo do negócio em 2-3 frases",
  "ideal_clients": ["até 8 segmentos genéricos de cliente final"],
  "keywords": ["até 12 palavras-chave gerais de prospecção"],
  "pain_points": ["até 5 dores que esse negócio resolve"],
  "commercial_score": 0,

  "recommended_mode": "direct_sale OU partners",
  "recommended_reason": "1-2 frases justificando qual modelo tende a converter melhor",

  "direct_clients": ["até 8 segmentos de CLIENTE FINAL ideais para VENDA DIRETA"],
  "direct_keywords": ["até 10 termos prontos para Google Maps/Bing focados em CLIENTE FINAL"],

  "partner_segments": ["até 8 tipos de PARCEIRO/canal de indicação"],
  "partner_keywords": ["até 10 termos prontos para buscar PARCEIROS no Google Maps/Bing"],

  "products": [
    {{
      "name": "Nome curto do produto/serviço (ex: 'Valuation', 'Pitch Deck')",
      "description": "1 frase explicando o que é e para quem",
      "recommended_mode": "direct_sale OU partners OU both",
      "direct_clients": ["até 6 segmentos de CLIENTE FINAL que precisam ESPECIFICAMENTE deste produto"],
      "direct_keywords": ["até 8 termos de busca focados em quem PRECISA COMPRAR este produto (Google Maps/Bing)"],
      "partner_segments": ["até 6 tipos de PARCEIRO que atendem o mesmo público e podem INDICAR clientes deste produto"],
      "partner_keywords": ["até 8 termos de busca focados em PARCEIROS deste produto (contabilidades, assessorias, consultorias do mesmo segmento)"]
    }}
  ]
}}

Regras:
- "direct_*" devem mirar QUEM PAGA pelo serviço diretamente.
- "partner_*" devem mirar QUEM ATENDE empresários e pode INDICAR clientes recorrentes.
- "recommended_mode" reflete qual modelo tende a gerar maior LTV/escala.
- "products": liste TODOS os produtos/serviços distintos que o site oferece (até 6).
  Se o site vende UM ÚNICO produto, devolva uma lista com 1 item. Se vende vários
  (ex: 'Valuation' + 'Pitch Deck'), devolva um item POR PRODUTO com keywords
  específicas para cada — NUNCA misture os públicos de produtos diferentes.
- Para cada produto: direct_keywords devem mirar quem precisa COMPRAR aquele produto
  exato; partner_keywords devem mirar profissionais/empresas do MESMO SEGMENTO que
  atendem o público-alvo (contabilidades, assessorias, consultorias, etc.) e que
  podem INDICAR ou REVENDER aquele produto específico.
- Não invente dados; baseie-se no conteúdo do site.
"""


def prompt_generate_product(product_name: str, business_summary: str) -> str:
    """Gera o detalhamento de UM produto isolado (usado no '+ Adicionar produto')."""
    return f"""Você é um SDR estratégico. O usuário tem o seguinte negócio:

NEGÓCIO:
{business_summary or '(não informado)'}

Ele acabou de informar manualmente que TAMBÉM vende o produto/serviço:
PRODUTO: "{product_name}"

Gere o detalhamento desse produto. Retorne JSON EXATO:
{{
  "name": "{product_name}",
  "description": "1 frase explicando o que é e para quem",
  "recommended_mode": "direct_sale OU partners OU both",
  "direct_clients": ["até 6 segmentos de CLIENTE FINAL que precisam ESPECIFICAMENTE deste produto"],
  "direct_keywords": ["até 8 termos de busca focados em quem PRECISA COMPRAR este produto"],
  "partner_segments": ["até 6 tipos de PARCEIRO que podem INDICAR clientes deste produto"],
  "partner_keywords": ["até 8 termos de busca focados em PARCEIROS deste produto"]
}}

Regras:
- direct_keywords miram quem COMPRA o produto.
- partner_keywords miram quem ATENDE o mesmo público e pode INDICAR.
- Seja específico ao produto, não genérico.
"""


def _mode_block(mode: str) -> str:
    if mode == "partners":
        return (
            "MODO: PARCEIROS\n"
            "Avalie o lead como POTENCIAL PARCEIRO/CANAL DE INDICAÇÃO. "
            "Priorize: autoridade no nicho, presença digital, posicionamento consultivo, "
            "tamanho da carteira potencial, atendimento a empresários, capacidade de "
            "indicar múltiplos clientes recorrentes. NÃO trate como cliente final.\n"
            "O pitch deve falar de PARCERIA / INDICAÇÃO / RECEITA RECORRENTE para o parceiro."
        )
    return (
        "MODO: VENDA DIRETA\n"
        "Avalie o lead como CLIENTE FINAL. Priorize: porte, sinais de crescimento, captação, "
        "expansão, múltiplos sócios, fusão/aquisição, reorganização societária, "
        "necessidade provável do serviço.\n"
        "O pitch deve falar diretamente da DOR e do BENEFÍCIO ao cliente."
    )


def prompt_qualify_lead(business_summary: str, mode: str, lead: dict) -> str:
    """Prompt avançado: SDR + estrategista — gera score, match, why, oferta, ticket, follow-up."""
    mode_block = _mode_block(mode)
    signals = ", ".join(lead.get("buying_signals") or []) or "—"
    techs = lead.get("technologies") or "—"
    decisors = lead.get("decision_makers") or []
    decisors_str = (
        ", ".join(f"{d.get('name')} ({d.get('role')})" for d in decisors) or "—"
    )
    return f"""Você é o SDR + estrategista comercial. Avalie o lead abaixo PROFUNDAMENTE.

NEGÓCIO DO USUÁRIO:
{business_summary}

{mode_block}

LEAD:
- Nome: {lead.get('name', '')}
- Nicho: {lead.get('niche', '')}
- Cidade/UF: {lead.get('city', '')}/{lead.get('state', '')}
- Site: {lead.get('website', '')}
- Telefone: {lead.get('phone', '')}
- Email: {lead.get('email', '')}
- Avaliação Google: {lead.get('google_rating', '')} ({lead.get('google_reviews', '')} reviews)
- CNPJ: {lead.get('cnpj', '') or '—'}
- Porte estimado: {lead.get('company_size', '') or '—'}
- Funcionários estimados: {lead.get('employees_estimate') or '—'}
- Tempo de mercado (anos): {lead.get('years_in_market') or '—'}
- Tecnologias detectadas: {techs}
- Sinais de compra detectados: {signals}
- Decisores identificados: {decisors_str}
- Trecho do site: {(lead.get('site_excerpt') or '')[:1200]}

Retorne JSON EXATO:
{{
  "score": 0,
  "reason": "1-2 frases justificando o score, alinhadas ao MODO acima",
  "match_score": 0,
  "why_matters": "POR QUE ESSE LEAD IMPORTA: 2-3 frases explicando dor provável, encaixe estratégico e probabilidade de conversão",
  "pitch": "mensagem comercial curta (máx 380 caracteres) PT-BR consultiva sem clichê sem emoji ALINHADA AO MODO",
  "follow_up_text": "mensagem curta de follow-up (máx 280 caracteres) caso o lead não responda em 5-7 dias, tom diferente do pitch",
  "opportunity_when": "quando abordar (ex: 'Imediato', 'Esta semana', 'Aguardar sinal X')",
  "opportunity_channel": "melhor canal: WhatsApp / Email / LinkedIn / Telefone",
  "opportunity_offer": "oferta inicial recomendada em 1 frase",
  "ticket_estimate": "ticket potencial estimado (ex: 'R$ 8k a R$ 25k', 'R$ 2k/mês recorrente')",
  "revenue_year_estimate": "potencial anual estimado (ex: 'R$ 60k–120k', '5–10 indicações/ano')",
  "tags": ["1 a 5 tags curtas: ex 'Parceiro Premium', 'Alto Potencial', 'Cliente Ideal', 'Holding', 'Startup', 'Crescimento Acelerado', 'Empresa Familiar', 'Alto Ticket', 'Baixo Fit', 'Multiplicador Comercial', 'Parceiro Estratégico'"]
}}

Regras:
- score (0-100) reflete força absoluta do lead no MODO escolhido.
- match_score (0-100) reflete COMPATIBILIDADE com o NEGÓCIO DO USUÁRIO.
- Use sinais detectados como evidência objetiva quando existirem.
- No MODO PARCEIROS leads consultivos com autoridade pontuam mais (carteira/networking).
- No MODO VENDA DIRETA leads com demanda real (expansão, captação, M&A) pontuam mais.
- Seja realista; não infle scores.
"""
