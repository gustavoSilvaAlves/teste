import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config import (
    KOMMO_API_TOKEN, KOMMO_API_SUBDOMAIN,
    EVOLUTION_API_URL, EVOLUTION_API_KEY
)

def get_robust_session():
    session = requests.Session()
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["POST", "GET"]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session



def enviar_mensagem_evolution(
        numero_destino: str,
        mensagem: str,
        evolution_instance_id: str
):
    if not EVOLUTION_API_URL or not EVOLUTION_API_KEY:
        print("[API CLIENTS] Erro: Configurações da Evolution API não carregadas.")
        return None

    url = f"{EVOLUTION_API_URL}/message/sendText/{evolution_instance_id}"
    numero_formatado = numero_destino.lstrip('+')

    headers = {
        "Content-Type": "application/json",
        "apikey": EVOLUTION_API_KEY
    }

    data = {
        "number": numero_formatado,
        "text": mensagem,
        "delay": 1200
    }

    print(f"[API CLIENTS] Enviando TEXTO (Instância: {evolution_instance_id}) para: {numero_formatado}...")

    try:
        session = get_robust_session()
        response = session.post(url, headers=headers, json=data, timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"[API CLIENTS] Erro envio Evolution: {e}")
    return None


def enviar_midia_base64_evolution(
        numero_destino: str,
        evolution_instance_id: str,
        base64_data: str,
        nome_arquivo: str,
        caption: str = ""
):

    if not EVOLUTION_API_URL or not EVOLUTION_API_KEY:
        print("[API CLIENTS] Erro: Configurações Evolution ausentes.")
        return None

    url = f"{EVOLUTION_API_URL}/message/sendMedia/{evolution_instance_id}"
    numero_formatado = numero_destino.lstrip('+')

    headers = {
        "Content-Type": "application/json",
        "apikey": EVOLUTION_API_KEY
    }

    if not base64_data.startswith("data:"):
        media_payload = base64_data

    else:
        media_payload = base64_data

    data = {
        "number": numero_formatado,
        "mediatype": "document",
        "mimetype": "application/pdf",
        "caption": caption,
        "media": media_payload,
        "fileName": nome_arquivo,
        "delay": 1200
    }

    print(f"[API CLIENTS] Enviando PDF via Base64 (Instância: {evolution_instance_id})...")

    try:
        session = get_robust_session()
        response = session.post(url, headers=headers, json=data, timeout=60)

        response.raise_for_status()
        print("[API CLIENTS] PDF enviado com sucesso.")
        return response.json()

    except requests.exceptions.SSLError as ssl_err:
        print(f"[API CLIENTS] Erro CRÍTICO de SSL: {ssl_err}")
        print("Dica: Verifique se o base64 não está corrompido ou muito grande.")
    except Exception as e:
        print(f"[API CLIENTS] Erro envio Mídia Evolution: {e}")
        try:
            print(f"Resposta do servidor: {response.text}")
        except:
            pass

    return None

def _fazer_requisicao_kommo(url: str):
    if not KOMMO_API_TOKEN or not KOMMO_API_SUBDOMAIN:
        return None
    headers = {"Authorization": f"Bearer {KOMMO_API_TOKEN}"}
    try:
        session = get_robust_session()
        response = session.get(url, headers=headers, timeout=20)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"[API CLIENTS] Erro Kommo: {e}")
    return None


def consultar_lead_kommo(id_lead: str):
    url = f"https://{KOMMO_API_SUBDOMAIN}.kommo.com/api/v4/leads/{id_lead}?with=contacts"
    return _fazer_requisicao_kommo(url)


def consultar_contato_kommo(id_contato: str):
    url = f"https://{KOMMO_API_SUBDOMAIN}.kommo.com/api/v4/contacts/{id_contato}"
    return _fazer_requisicao_kommo(url)


def atualizar_status_lead_kommo(id_lead: int, novo_status_id: int):
    """
    Atualiza o status (estágio do pipeline) de um lead no Kommo CRM.
    """
    if not KOMMO_API_TOKEN or not KOMMO_API_SUBDOMAIN:
        print("[API CLIENTS] Erro: Configurações do Kommo não carregadas.")
        return None

    url = f"https://{KOMMO_API_SUBDOMAIN}.kommo.com/api/v4/leads/{id_lead}"

    headers = {
        "Authorization": f"Bearer {KOMMO_API_TOKEN}",
        "Content-Type": "application/json"
    }

    data = {
        "status_id": novo_status_id
    }

    print(f"[API CLIENTS] Atualizando Lead {id_lead} no Kommo para status {novo_status_id}...")

    try:
        session = get_robust_session()
        response = session.patch(url, headers=headers, json=data, timeout=20)
        response.raise_for_status()
        print("[API CLIENTS] Status do Lead atualizado com sucesso.")
        return response.json()
    except Exception as e:
        print(f"[API CLIENTS] Erro ao atualizar Lead no Kommo: {e}")
        try:
            print(response.text)
        except:
            pass

    return None


def criar_nota_lead_kommo(id_lead_kommo: int, texto_nota: str):

    if not KOMMO_API_TOKEN or not KOMMO_API_SUBDOMAIN:
        print("[API CLIENTS] Erro: Configurações do Kommo não carregadas.")
        return None

    url = f"https://{KOMMO_API_SUBDOMAIN}.kommo.com/api/v4/leads/{id_lead_kommo}/notes"

    headers = {
        "Authorization": f"Bearer {KOMMO_API_TOKEN}",
        "Content-Type": "application/json"
    }

    data = [
        {
            "note_type": "common",
            "params": {
                "text": texto_nota
            }
        }
    ]

    print(f"[API CLIENTS] Criando nota no Lead {id_lead_kommo}...")

    try:
        session = get_robust_session()
        response = session.post(url, headers=headers, json=data, timeout=20)
        response.raise_for_status()
        print("[API CLIENTS] Nota criada com sucesso.")
        return response.json()
    except Exception as e:
        print(f"[API CLIENTS] Erro ao criar nota no Kommo: {e}")
        try:
            print(response.text)
        except:
            pass

    return None