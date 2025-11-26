# 📁 /services/api_clients.py

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import os
from config import (
    KOMMO_API_TOKEN, KOMMO_API_SUBDOMAIN,
    EVOLUTION_API_URL, EVOLUTION_API_KEY
)


def recuperar_base64_media_evolution(instance_id: str, message_id: str, remote_jid: str, from_me: bool):
    """
    Solicita à Evolution o Base64 descifrado de uma mensagem de mídia.
    Endpoint: POST /chat/getBase64FromMessage/{instance}
    """
    if not EVOLUTION_API_URL or not EVOLUTION_API_KEY:
        print("[API CLIENTS] Erro: Configurações Evolution ausentes.")
        return None

    # Endpoint padrão da V2 para recuperar mídia
    url = f"{EVOLUTION_API_URL}/chat/getBase64FromMessage/{instance_id}"

    headers = {
        "Content-Type": "application/json",
        "apikey": EVOLUTION_API_KEY
    }

    # O payload precisa recriar a estrutura da chave da mensagem
    data = {
        "message": {
            "key": {
                "id": message_id,
                "fromMe": from_me,
                "remoteJid": remote_jid
            }
        },
        "convertToMp4": False
    }

    print(f"[API CLIENTS] Solicitando Base64 à Evolution (Msg ID: {message_id})...")

    try:
        session = get_robust_session()
        response = session.post(url, headers=headers, json=data, timeout=40)

        # Debug: Se der erro, imprime o que a API respondeu
        if response.status_code != 200:
            print(f"[API CLIENTS] Erro API ({response.status_code}): {response.text}")
            return None

        response.raise_for_status()

        # A Evolution V2 geralmente retorna: { "base64": "..." }
        resp_json = response.json()

        if isinstance(resp_json, dict):
            return resp_json.get('base64') or resp_json.get('data')

        # Fallback se retornar string pura
        return resp_json

    except Exception as e:
        print(f"[API CLIENTS] Exceção ao recuperar mídia: {e}")

    return None


# --- Configuração de Sessão Robusta ---
# Cria uma sessão que tenta de novo se o SSL falhar
def get_robust_session():
    session = requests.Session()
    retry_strategy = Retry(
        total=3,  # Tenta 3 vezes
        backoff_factor=1,  # Espera 1s, 2s, 4s entre tentativas
        status_forcelist=[429, 500, 502, 503, 504],  # Tenta de novo nesses erros
        allowed_methods=["POST", "GET"]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


# --- Cliente Evolution ---

def enviar_mensagem_evolution(
        numero_destino: str,
        mensagem: str,
        evolution_instance_id: str
):
    """Envia apenas TEXTO."""
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
        "delay": 1200  # Ajustado conforme documentação (na raiz)
    }

    print(f"[API CLIENTS] Enviando TEXTO (Instância: {evolution_instance_id}) para: {numero_formatado}...")

    try:
        session = get_robust_session()
        # Timeout de 30 segundos para evitar travar
        response = session.post(url, headers=headers, json=data, timeout=30)
        response.raise_for_status()
        # print(f"[API CLIENTS] Resposta: {response.json()}") # Descomente se quiser ver o log
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
    """Envia arquivo via Base64 com retries de conexão."""

    if not EVOLUTION_API_URL or not EVOLUTION_API_KEY:
        print("[API CLIENTS] Erro: Configurações Evolution ausentes.")
        return None

    url = f"{EVOLUTION_API_URL}/message/sendMedia/{evolution_instance_id}"
    numero_formatado = numero_destino.lstrip('+')

    headers = {
        "Content-Type": "application/json",
        "apikey": EVOLUTION_API_KEY
    }

    # Verifica se precisa adicionar o prefixo do Data URI
    # (Para PDF, a Evolution v2 geralmente gosta do prefixo)
    if not base64_data.startswith("data:"):
        media_payload = base64_data  # Tente enviar PURO primeiro se a doc pedir, ou com prefixo
        # Pela doc que você mandou, diz apenas "Url or base64".
        # Se falhar, tente: f"data:application/pdf;base64,{base64_data}"
    else:
        media_payload = base64_data

    # Payload ajustado exatamente conforme a documentação que você colou
    data = {
        "number": numero_formatado,
        "mediatype": "document",
        "mimetype": "application/pdf",
        "caption": caption,
        "media": media_payload,
        "fileName": nome_arquivo,
        "delay": 1200  # Na raiz
    }

    print(f"[API CLIENTS] Enviando PDF via Base64 (Instância: {evolution_instance_id})...")

    try:
        session = get_robust_session()
        # Aumentamos o timeout para 60s pois upload de arquivo demora mais
        response = session.post(url, headers=headers, json=data, timeout=60)

        response.raise_for_status()
        print("[API CLIENTS] PDF enviado com sucesso.")
        return response.json()

    except requests.exceptions.SSLError as ssl_err:
        print(f"[API CLIENTS] Erro CRÍTICO de SSL: {ssl_err}")
        print("Dica: Verifique se o base64 não está corrompido ou muito grande.")
    except Exception as e:
        print(f"[API CLIENTS] Erro envio Mídia Evolution: {e}")
        # Se der erro, tenta imprimir o corpo da resposta para ver o que a Evolution disse
        try:
            print(f"Resposta do servidor: {response.text}")
        except:
            pass

    return None


# --- Cliente Kommo ---
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

    # Payload para atualizar apenas o status_id
    data = {
        "status_id": novo_status_id
    }

    print(f"[API CLIENTS] Atualizando Lead {id_lead} no Kommo para status {novo_status_id}...")

    try:
        session = get_robust_session()
        # PATCH é o método para atualização parcial
        response = session.patch(url, headers=headers, json=data, timeout=20)
        response.raise_for_status()
        print("[API CLIENTS] Status do Lead atualizado com sucesso.")
        return response.json()
    except Exception as e:
        print(f"[API CLIENTS] Erro ao atualizar Lead no Kommo: {e}")
        # Tenta imprimir o erro detalhado da API se disponível
        try:
            print(response.text)
        except:
            pass

    return None


def criar_nota_lead_kommo(id_lead_kommo: int, texto_nota: str):
    """
    Cria uma nota de texto (common) dentro do Lead no Kommo.
    """
    if not KOMMO_API_TOKEN or not KOMMO_API_SUBDOMAIN:
        print("[API CLIENTS] Erro: Configurações do Kommo não carregadas.")
        return None

    # Endpoint para adicionar notas
    url = f"https://{KOMMO_API_SUBDOMAIN}.kommo.com/api/v4/leads/{id_lead_kommo}/notes"

    headers = {
        "Authorization": f"Bearer {KOMMO_API_TOKEN}",
        "Content-Type": "application/json"
    }

    # O Kommo espera uma lista de notas
    data = [
        {
            "note_type": "common",  # Nota de texto simples
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