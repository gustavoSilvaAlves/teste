from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from dotenv import load_dotenv

load_dotenv()


def verificar_match_nome_llm(nome_lead: str, nome_whatsapp: str) -> bool:
    """
    Usa uma LLM para determinar se o nome do WhatsApp é compatível com o nome do Lead.
    Identifica apelidos (Eduarda/Duda), abreviações e variações comuns no Brasil.
    Retorna True ou False.
    """
    if not nome_lead or not nome_whatsapp:
        return False

    # Se for idêntico, nem gasta token
    if nome_lead.strip().lower() == nome_whatsapp.strip().lower():
        return True

    print(f"[TEXT UTILS] Validando match de nome via LLM: '{nome_lead}' vs '{nome_whatsapp}'")

    system_prompt = (
        "Você é um especialista em nomes e apelidos culturais do Brasil. "
        "Sua tarefa é comparar o 'Nome no CRM' com o 'Nome no Perfil do WhatsApp' "
        "e dizer se é PROVÁVEL que sejam a mesma pessoa.\n\n"
        "Regras de Match (Verdadeiro):\n"
        "- Apelidos comuns (ex: Eduardo/Dudu, Francisca/Chica, Antonio/Tony).\n"
        "- Abreviações (ex: Gustavo Silva/Gustavo, Ana Maria/Ana).\n"
        "- Sobrenomes (ex: Roberto Carlos/Carlos).\n\n"
        "Regras de Não Match (Falso):\n"
        "- Nomes totalmente diferentes (ex: João/Maria).\n"
        "- Nomes de empresas genéricos no WhatsApp (ex: 'Loja de Peças' vs 'João').\n\n"
        "Responda APENAS com 'TRUE' ou 'FALSE'. Sem explicações."
    )

    human_prompt = (
        "Nome no CRM: {nome_lead}\n"
        "Nome no WhatsApp: {nome_whatsapp}\n\n"
        "É a mesma pessoa?"
    )

    try:
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.0)

        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", human_prompt)
        ])

        chain = prompt | llm | StrOutputParser()

        resultado = chain.invoke({
            "nome_lead": nome_lead,
            "nome_whatsapp": nome_whatsapp
        })

        resultado_limpo = resultado.strip().upper()
        print(f"[TEXT UTILS] Veredito da LLM: {resultado_limpo}")

        return "TRUE" in resultado_limpo

    except Exception as e:
        print(f"[TEXT UTILS] Erro na validação LLM: {e}")
        return False