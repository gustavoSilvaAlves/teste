import json
from typing import TypedDict, Literal
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, END

from config import ID_STATUS_QUALIFICACAO_HUMANA

from utils.text_utils import verificar_match_nome_llm

from services.api_clients import (enviar_mensagem_evolution,
                                  enviar_midia_base64_evolution,
                                  atualizar_status_lead_kommo,
                                  criar_nota_lead_kommo)

from services.db_manager import (atualizar_status_contato,
                                 salvar_mensagem_agente,
                                 get_nome_responsavel_por_lead,
                                 get_kommo_id_from_local,
                                 get_nome_lead_por_id)

from utils.message_manager import (
    selecionar_mensagem_engano,
    get_texto_apresentacao,
    get_mensagem_parente,
    get_pdf_em_base64
)


# --- 1. Estado ---
class GraphState(TypedDict):
    lead_id: int
    numero_id: int
    numero_remetente: str
    mensagem_recebida: str
    historico_chat: list
    instance_id: str
    nome_perfil_whatsapp: str

    classificacao: Literal["confirmacao", "objecao", "negacao", "parente","neutro","nao_identificado"]


# --- 2. Classificador ---
class ClassificarResposta(BaseModel):
    categoria: Literal["confirmacao", "objecao", "negacao", "parente", "neutro", "nao_identificado"] = Field(...)


llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.0)
structured_llm = llm.with_structured_output(ClassificarResposta)

system_prompt = (
    "Você é um classificador responsável por analisar o histórico completo da conversa entre o cliente e o chatbot. "
    "Com base nesse histórico, sua tarefa é identificar **apenas uma** das categorias abaixo:\n\n"
    "1. 'confirmacao': O cliente é a pessoa procurada (ex: 'sou eu', 'sim').\n"
    "2. 'objecao': O cliente pergunta quem é ou do que se trata (ex: 'quem fala?', 'assunto?').\n"
    "3. 'negacao': O cliente diz que não é a pessoa ou número errado.\n"
    "4. 'parente': O cliente diz que é parente, filho, esposa, ou conhece a pessoa (ex: 'sou filho dele', 'ele morreu', 'é meu pai').\n"
    "5. 'neutro': O cliente apenas cumprimenta ou responde algo vago sem confirmar/negar (ex: 'olá', 'boa noite', 'tudo bem', 'oi').\n"
    "6. 'nao_identificado': Outros casos."
)
human_prompt = ("Histórico:\n{historico_formatado}\n\nAnálise com cuidado e classifique com base no histórico de mensagens em apenas uma categoria:")

classification_prompt = ChatPromptTemplate.from_messages([
    ("system", system_prompt),
    ("human", human_prompt)
])

classifier_chain = classification_prompt | structured_llm


def formatar_historico_para_nota(historico_chat: list, ultima_mensagem_usuario: str) -> str:
    texto = (
        "\n"
        "════ HISTÓRICO DA CONVERSA ════ \n"
        "\n"
    )

    if historico_chat:
        for msg in historico_chat:
            if msg['remetente'] == 'agente':
                texto += f"BOT: {msg['conteudo']}\n"
            else:
                texto += f"CLIENTE: {msg['conteudo']}\n"

            texto += "─" * 30 + "\n"
    texto += f"CLIENTE: {ultima_mensagem_usuario}\n"

    texto += "\n═══════════════════════════════"

    return texto



# --- 3. Nó de Classificação ---
def classificar_entrada(state: GraphState):
    """Nó de entrada. Formata o histórico e classifica a mensagem do usuário."""
    print(f"\n--- [AGENTE RESPONDER] ---")
    print(f"[AGENTE RESPONDER] Classificando mensagem para Lead ID: {state['lead_id']}")

    historico_formatado = []
    msg_usuario_atual = state['mensagem_recebida'].strip()

    if state['historico_chat']:
        for msg in state['historico_chat']:
            conteudo_msg = msg['conteudo'].strip()
            remetente = msg['remetente']

            if remetente == 'usuario' and conteudo_msg in msg_usuario_atual and len(conteudo_msg) > 0:
                continue

            prefixo = "AI: " if remetente == 'agente' else "Cliente: "
            historico_formatado.append(f"{prefixo}{msg['conteudo']}")

    linhas_atuais = msg_usuario_atual.split('\n')
    for linha in linhas_atuais:
        if linha.strip():
            historico_formatado.append(f"Cliente: {linha.strip()}")

    historico_str = "\n".join(historico_formatado)

    print("--- [DEBUG] PROMPT ENVIADO PARA A LLM (CLASSIFICADOR) ---")
    print(f"Histórico Formatado (enviado para LLM):\n{historico_str}")

    print("\n------------ DEBUG: PROMPT COMPLETO (RAIO-X) ------------ ")

    try:
        mensagens_renderizadas = classification_prompt.format_messages(
            historico_formatado=historico_str
        )

        for i, m in enumerate(mensagens_renderizadas):
            role = m.type.upper()
            print(f"\n--- MENSAGEM {i + 1}: {role} ---")
            print(m.content)

    except Exception as e_debug:
        print(f"Erro ao imprimir debug: {e_debug}")

    try:
        resultado = classifier_chain.invoke({
            "historico_formatado": historico_str
        })

        classificacao = resultado.categoria
        print(f"[AGENTE RESPONDER] Classificação da LLM: {classificacao}")

    except Exception as e:
        print(f"[AGENTE RESPONDER] Erro na LLM: {e}")

        classificacao = "nao_identificado"

    return {"classificacao": classificacao}


def tool_confirmacao(state: GraphState):
    print(f"\n[TOOL - CONFIRMAÇÃO]")
    print("O usuário confirmou. Atualizando status para 'confirmado' e encerrando.")
    atualizar_status_contato(state['numero_id'], 'confirmado')

    kommo_id = get_kommo_id_from_local(state['lead_id'])

    atualizar_status_lead_kommo(kommo_id, ID_STATUS_QUALIFICACAO_HUMANA)

    numero_cliente = state['numero_remetente']

    history_log = formatar_historico_para_nota(state['historico_chat'], state['mensagem_recebida'])

    texto_nota = (
        f"IDENTIFICAÇÃO POSITIVA VIA CHATBOT\n"
        f"\n"
        f"O número +{numero_cliente} confirmou ser o titular do processo.\n"
        f"{history_log}"
    )
    criar_nota_lead_kommo(kommo_id, texto_nota)

    return {}


def tool_objecao(state: GraphState):
    print(f"\n[TOOL - OBJEÇÃO]")
    print("O usuário tem uma objeção. Enviando material de apresentação...")

    numero_id = state['numero_id']
    numero_remetente = state['numero_remetente']
    instance_id = state['instance_id']
    lead_id = state['lead_id']

    nome_responsavel = get_nome_responsavel_por_lead(lead_id)
    texto = get_texto_apresentacao(nome_responsavel)
    pdf_base64 = get_pdf_em_base64()
    resultado_envio = None

    if pdf_base64:
        resultado_envio = enviar_midia_base64_evolution(
            numero_destino=numero_remetente,
            evolution_instance_id=instance_id,
            base64_data=pdf_base64,
            nome_arquivo="Apresentacao_PrecNet.pdf",
            caption=texto
        )

    if not resultado_envio:
        if pdf_base64: print("[AGENTE RESPONDER] Falha no PDF. Tentando texto puro...")
        resultado_envio = enviar_mensagem_evolution(numero_remetente, texto, instance_id)

    if resultado_envio:
        salvar_mensagem_agente(numero_id, texto)
        atualizar_status_contato(numero_id, 'objeção')

        kommo_id = get_kommo_id_from_local(lead_id)

        atualizar_status_lead_kommo(kommo_id, ID_STATUS_QUALIFICACAO_HUMANA)

        numero_cliente = state['numero_remetente']

        history_log = formatar_historico_para_nota(state['historico_chat'], state['mensagem_recebida'])

        texto_nota = (
            f"IDENTIFICAÇÃO DE OBJEÇÃO VIA CHATBOT\n"
            f"O número +{numero_cliente} apresentou uma objeção durante a interação automática\n"
            f"{history_log}"
        )
        criar_nota_lead_kommo(kommo_id, texto_nota)

    return {}


def tool_negacao(state: GraphState):
    print("\n[TOOL - NEGAÇÃO]")
    numero_id = state['numero_id']
    numero_remetente = state['numero_remetente']
    instance_id = state['instance_id']
    lead_id = state['lead_id']

    nome_wpp = state.get('nome_perfil_whatsapp', '')

    nome_lead_banco = get_nome_lead_por_id(lead_id)

    eh_engano_fake = False
    if nome_wpp and nome_lead_banco:
        eh_engano_fake = verificar_match_nome_llm(nome_lead_banco, nome_wpp)

    history_log = formatar_historico_para_nota(state['historico_chat'], state['mensagem_recebida'])
    kommo_id = get_kommo_id_from_local(lead_id)

    if eh_engano_fake:
        print(f"DETECTADO: ENGANO FAKE! Lead='{nome_lead_banco}' vs Wpp='{nome_wpp}'")

        atualizar_status_contato(numero_id, 'engano_fake')

        if kommo_id:

            texto_nota = (
                f"ALERTA DE ENGANO FAKE\n"
                f"O número +{numero_remetente} negou ser a pessoa.\n"
                f"PORÉM, a IA identificou que o nome no WhatsApp ('{nome_wpp}') bate com o nome do lead ('{nome_lead_banco}').\n"
                f"AÇÃO: Ligar pessoalmente ou investigar."
                f"{history_log}"
            )
            criar_nota_lead_kommo(kommo_id, texto_nota)
    else:
        print("Negação legítima (Nomes não batem ou sem nome no Wpp). Enviando desculpas.")
        msg = selecionar_mensagem_engano()
        res = enviar_mensagem_evolution(numero_remetente, msg, instance_id)

        if res:
            salvar_mensagem_agente(numero_id, msg)
            atualizar_status_contato(numero_id, 'negado')

            if kommo_id:
                texto_nota = (
                    f"IDENTIFICAÇÃO DE ENGANO (NÚMERO ERRADO)\n"
                    f"O número +{numero_remetente} informou que não pertence ao titular.\n"
                    f"Bot pediu desculpas e encerrou.\n"
                    f"Verificar se há outros telefones disponíveis."
                    f"{history_log}"
                )
                criar_nota_lead_kommo(kommo_id, texto_nota)

    return {}


def tool_parente(state: GraphState):
    print("\n[TOOL - PARENTE]")
    print("O usuário indicou ser parente/conhecido. Gerando resposta personalizada...")

    lead_id = state['lead_id']
    numero_id = state['numero_id']
    numero_remetente = state['numero_remetente']
    instance_id = state['instance_id']

    nome_banco_resp = get_nome_responsavel_por_lead(lead_id)
    nome_responsavel = nome_banco_resp if nome_banco_resp else "Consultor PrecNet"

    nome_banco_lead = get_nome_lead_por_id(lead_id)
    nome_lead = nome_banco_lead if nome_banco_lead else "o Senhor(a)"

    msg = get_mensagem_parente(nome_responsavel, nome_lead)


    pdf_base64 = get_pdf_em_base64()
    resultado_envio = None

    if pdf_base64:
        resultado_envio = enviar_midia_base64_evolution(
            numero_destino=numero_remetente,
            evolution_instance_id=instance_id,
            base64_data=pdf_base64,
            nome_arquivo="Apresentacao_PrecNet.pdf",
            caption=msg
        )

    if not resultado_envio:
        if pdf_base64: print("[AGENTE RESPONDER] Falha no PDF. Tentando texto puro...")
        resultado_envio = enviar_mensagem_evolution(numero_remetente, msg, instance_id)

    if resultado_envio:
        salvar_mensagem_agente(numero_id, msg)
        atualizar_status_contato(numero_id, 'parente')

        kommo_id = get_kommo_id_from_local(lead_id)
        if kommo_id:
            atualizar_status_lead_kommo(kommo_id, ID_STATUS_QUALIFICACAO_HUMANA)

            history_log = formatar_historico_para_nota(state['historico_chat'], state['mensagem_recebida'])

            texto_nota = (
                f"INTERAÇÃO COM PARENTE/CONHECIDO\n"
                f"O número +{numero_remetente} informou conhecer o titular ({nome_lead}).\n"
                f"O Bot enviou a solicitação de encaminhamento."
                f"{history_log}"
            )
            criar_nota_lead_kommo(kommo_id, texto_nota)
        else:
            print("[AGENTE RESPONDER] ERRO: ID Kommo não encontrado.")

    return {}


def tool_neutra(state: GraphState):
    print("\n[TOOL - NEUTRA]")
    print("Mensagem fática/saudação. Nenhuma ação tomada. Mantendo 'em tratativa'.")

    atualizar_status_contato(state['numero_id'], 'em tratativa')

    return {}

def tool_nao_identificado(state: GraphState):
    print("LLM Não identificou uma ação clara que deveria tomar")
    atualizar_status_contato(state['numero_id'], 'em tratativa')
    return {}


# --- 5. Grafo ---
def should_route(state: GraphState):
    """Define para qual nó o grafo deve seguir."""
    classificacao = state.get("classificacao")

    if classificacao == "confirmacao":
        return "tool_confirmacao"
    elif classificacao == "objecao":
        return "tool_objecao"
    elif classificacao == "negacao":
        return "tool_negacao"
    elif classificacao == "parente":
        return "tool_parente"
    elif classificacao == "neutro":
        return "tool_neutra"
    else:
        return "tool_nao_identificado"


# --- Montagem do Grafo ---
workflow = StateGraph(GraphState)

workflow.add_node("classificar_entrada", classificar_entrada)
workflow.add_node("tool_confirmacao", tool_confirmacao)
workflow.add_node("tool_objecao", tool_objecao)
workflow.add_node("tool_negacao", tool_negacao)
workflow.add_node("tool_parente", tool_parente)
workflow.add_node("tool_neutra", tool_neutra)
workflow.add_node("tool_nao_identificado", tool_nao_identificado)

workflow.set_entry_point("classificar_entrada")

# Mapeamento das decisões
workflow.add_conditional_edges(
    "classificar_entrada",
    should_route,
    {
        "tool_confirmacao": "tool_confirmacao",
        "tool_objecao": "tool_objecao",
        "tool_negacao": "tool_negacao",
        "tool_parente": "tool_parente",
        "tool_neutra": "tool_neutra",
        "tool_nao_identificado": "tool_nao_identificado",
    }
)

workflow.add_edge("tool_confirmacao", END)
workflow.add_edge("tool_objecao", END)
workflow.add_edge("tool_negacao", END)
workflow.add_edge("tool_parente", END)
workflow.add_edge("tool_neutra", END)
workflow.add_edge("tool_nao_identificado", END)

app = workflow.compile()


def iniciar_agente_resposta(input_data: dict):
    try:
        input_data['classificacao'] = None

        print("\n------------ INPUT DO AGENTE ------------")
        print(json.dumps(input_data, indent=2, default=str))

        print("\n------------ OUTPUT DO AGENTE ------------")
        print(json.dumps(app.invoke(input_data), indent=2, default=str))
    except Exception as e:
        print(f"[AGENTE RESPONDER] Erro: {e}")