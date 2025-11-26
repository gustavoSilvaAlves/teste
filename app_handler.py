import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
sys.path.append(str(ROOT_DIR))

from services.api_clients import recuperar_base64_media_evolution
from services.db_manager import buscar_contexto_conversa, salvar_mensagem_usuario
from agents.agente_iniciador import iniciar_verificacao as run_agente_iniciador
from agents.agente_responder_langgraph import iniciar_agente_resposta as run_agente_responder
from utils.audio_manager import transcrever_audio_base64
import requests
import base64
from utils.debounce_manager import adicionar_mensagem_buffer


def processar_disparo_kommo(params: dict):
    """
    Ponto de entrada para o fluxo do Kommo (Agente 1).
    Roda em uma thread para não bloquear o disparador.
    """
    print("[APP HANDLER] Disparo do Kommo recebido. Iniciando Agente 1...")
    try:

        run_agente_iniciador(params)
    except Exception as e:
        print(f"[APP HANDLER] Erro crítico no Agente 1: {e}")


def processar_resposta_evolution(data: dict):
    """
    Ponto de entrada para o fluxo da Evolution (Agente 2).
    """
    print("[APP HANDLER] Resposta da Evolution recebida...") # Opcional: reduzir log
    try:
        # 1. Extrair dados básicos e chaves (MANTIDO)
        instancia_recebida = data.get("instance")
        mensagem_data = data.get('data', {})
        push_name = mensagem_data.get('pushName', '')

        key_data = mensagem_data.get('key', {})
        msg_id = key_data.get('id')

        # --- LÓGICA INTELIGENTE DE JID ---
        raw_remote_jid = key_data.get('remoteJid')
        raw_remote_jid_alt = data.get('data', {}).get('key', {}).get('remoteJidAlt')  # Às vezes vem aqui

        # Se for um LID (identificador oculto), tentamos pegar o alternativo
        if raw_remote_jid and "@lid" in raw_remote_jid:
            print(f"[APP HANDLER] JID Oculto (LID) detectado: {raw_remote_jid}")
            if raw_remote_jid_alt and "@s.whatsapp.net" in raw_remote_jid_alt:
                remote_jid = raw_remote_jid_alt
                print(f"[APP HANDLER] Usando JID Alternativo: {remote_jid}")
            else:
                # Fallback crítico: Se não tiver ALT, não temos o número.
                print("[APP HANDLER] ERRO CRÍTICO: Recebido LID sem JID alternativo. Impossível identificar o número.")
                return
        else:
            remote_jid = raw_remote_jid

        from_me = key_data.get('fromMe')

        if from_me is True: return

        # 2. Buscar Contexto no DB (MANTIDO)
        if not remote_jid: return
        numero_remetente_limpo = remote_jid.split('@')[0].lstrip('+')

        contexto = buscar_contexto_conversa(numero_remetente_limpo)
        if not contexto:
            print(f"[APP HANDLER] Ignorando msg. Lead não encontrado.")
            return

        # 3. Filtro de Status (MANTIDO)
        status_atual = contexto.get('status_atual')
        status_permitidos = ['aguardando resposta', 'sem envio', 'em tratativa']
        if status_atual not in status_permitidos:
            print(f"[APP HANDLER] Bloqueio Ativo ({status_atual}). Ignorando.")
            return

            # 4. Lógica de Extração e Áudio (MANTIDO)
        mensagem_recebida = None
        msg_obj = mensagem_data.get('message', {})

        if 'conversation' in msg_obj:
            mensagem_recebida = msg_obj['conversation']
        elif 'extendedTextMessage' in msg_obj:
            mensagem_recebida = msg_obj['extendedTextMessage'].get('text')
        elif 'speechToText' in msg_obj:
            mensagem_recebida = msg_obj['speechToText']

        # Áudio sem transcrição (MANTIDO)
        if not mensagem_recebida and msg_obj.get('audioMessage'):
            audio_msg = msg_obj.get('audioMessage')
            base64_audio = audio_msg.get('base64')
            if not base64_audio:
                base64_audio = recuperar_base64_media_evolution(
                    instancia_recebida, msg_id, remote_jid, from_me
                )
            if base64_audio:
                if "," in base64_audio: base64_audio = base64_audio.split(",")[1]
                mensagem_recebida = transcrever_audio_base64(base64_audio)

        if not mensagem_recebida:
            return

        # 5. SALVAR NO BANCO (Imediato, para não perder registro)
        # Salvamos o fragmento individualmente
        msg_para_salvar = mensagem_recebida
        if msg_obj.get('audioMessage') or msg_obj.get('speechToText'):
            msg_para_salvar = f"[Áudio Transcrito] {mensagem_recebida}"

        salvar_mensagem_usuario(contexto['numero_id'], msg_para_salvar)

        # 6. PREPARAR E ENVIAR PARA O DEBOUNCE (MUDANÇA AQUI)

        input_data = {
            "lead_id": contexto['lead_id'],
            "numero_id": contexto['numero_id'],
            "historico_chat": contexto['historico_chat'],
            "numero_remetente": numero_remetente_limpo,
            "mensagem_recebida": mensagem_recebida,  # Será acumulada no debounce
            "instance_id": instancia_recebida,
            "nome_perfil_whatsapp": push_name
        }

        # Em vez de chamar 'run_agente_responder' direto, chamamos o buffer
        # Passamos o ID do usuário (remote_jid) como chave única
        adicionar_mensagem_buffer(
            remote_jid=remote_jid,
            input_data=input_data,
            callback_funcao=run_agente_responder  # A função que será chamada no fim
        )

    except Exception as e:
        print(f"[APP HANDLER] Erro ao processar resposta: {e}")