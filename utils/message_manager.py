import random
import datetime
import pytz
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
import base64
import os
from services.db_manager import get_template_mensagem_balanceado

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAMINHO_PDF = os.path.join(BASE_DIR, "RecebendoPrecatorioLogo.pdf")


def get_pdf_em_base64():
    """Lê o arquivo PDF local e retorna a string Base64 limpa."""
    if not os.path.exists(CAMINHO_PDF):
        print(f"[MESSAGE MANAGER] Erro Crítico: Arquivo não encontrado em {CAMINHO_PDF}")
        return None

    try:
        with open(CAMINHO_PDF, "rb") as pdf_file:
            # Lê, codifica e LIMPA quebras de linha
            encoded_bytes = base64.b64encode(pdf_file.read())
            encoded_string = encoded_bytes.decode('utf-8').replace('\n', '').replace('\r', '')
            return encoded_string
    except Exception as e:
        print(f"[MESSAGE MANAGER] Erro ao converter PDF: {e}")
        return None


def get_saudacao():
    """Retorna Bom dia ou Boa tarde baseado no horário de Brasília."""
    tz = pytz.timezone('America/Sao_Paulo')
    hora = datetime.datetime.now(tz).hour
    if 5 <= hora < 12:
        return "Bom dia"
    elif 12 <= hora < 18:
        return "Boa tarde"
    else:
        return "Boa noite"


def detectar_genero(nome: str) -> str:
    """Usa LLM barata para identificar se o nome é M ou F."""
    try:
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
        chain = ChatPromptTemplate.from_template(
            "Responda apenas com 'M' para masculino ou 'F' para feminino. Nome: {nome}"
        ) | llm | StrOutputParser()

        genero = chain.invoke({"nome": nome}).strip().upper()
        return genero if genero in ['M', 'F'] else 'M'  # Default M
    except:
        return 'M'


# --- TEMPLATES ---

def selecionar_primeira_mensagem(primeiro_nome: str):
    """Busca template no DB e preenche saudação e nome."""
    texto_raw = get_template_mensagem_balanceado('primeira_mensagem')

    if not texto_raw:
        return f"Olá, {primeiro_nome}. Tudo bem?"  # Fallback extremo

    saudacao = get_saudacao()

    # Preenche os placeholders {saudacao}, {saudacao_lower}, {nome_cliente}
    return texto_raw.format(
        saudacao=saudacao,
        saudacao_lower=saudacao.lower(),
        nome_cliente=primeiro_nome
    )


def selecionar_mensagem_engano():
    """Busca template de engano no DB."""
    texto_raw = get_template_mensagem_balanceado('engano')
    return texto_raw or "Desculpe o engano."


def get_mensagem_parente(nome_responsavel: str, nome_lead: str):
    """Busca template de parente e preenche pronomes de acordo com gênero."""
    texto_raw = get_template_mensagem_balanceado('parente')
    if not texto_raw: return "Poderia encaminhar para ele?"

    genero = detectar_genero(nome_lead)
    pronome_encaminhar = "encaminhá-lo" if genero == 'M' else "encaminhá-la"
    pronome_possesivo = "dele" if genero == 'M' else "dela"

    return texto_raw.format(
        nome_responsavel=nome_responsavel,
        pronome_encaminhar=pronome_encaminhar,
        pronome_possesivo=pronome_possesivo
    )

def get_texto_apresentacao(nome_responsavel: str):
    """Busca template de apresentação e preenche o nome do consultor."""
    texto_raw = get_template_mensagem_balanceado('apresentacao')
    if not texto_raw: return f"Olá, sou {nome_responsavel} da PrecNet."

    return texto_raw.format(
        nome_responsavel=nome_responsavel
    )