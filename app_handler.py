from services.db_manager import buscar_contexto_conversa, salvar_mensagem_usuario
from agents.agente_iniciador import iniciar_verificacao as run_agente_iniciador
from agents.agente_responder_langgraph import iniciar_agente_resposta as run_agente_responder
from utils.debounce_manager import adicionar_mensagem_buffer


def extrair_conteudo_mensagem(msg_obj):
    """
    Função universal para extrair texto de mensagens do WhatsApp via Evolution API.
    Lida com mensagens normais, temporárias (ephemeral), visualização única, etc.
    """
    if not msg_obj: return None

    # --- FASE 1: DESEMBRULHAR CAMADAS (UNWRAPPING) ---
    # O WhatsApp aninha mensagens. Precisamos chegar no núcleo.
    # Usamos IFs sequenciais pois uma mensagem pode ser Temporária E Visualização Única ao mesmo tempo.

    # 1. Mensagens Temporárias
    if 'ephemeralMessage' in msg_obj:
        msg_obj = msg_obj['ephemeralMessage'].get('message', {})

    # 2. Visualização Única (View Once)
    if 'viewOnceMessage' in msg_obj:
        msg_obj = msg_obj['viewOnceMessage'].get('message', {})

    # 3. Visualização Única V2 e V2Extension
    if 'viewOnceMessageV2' in msg_obj:
        msg_obj = msg_obj['viewOnceMessageV2'].get('message', {})
    if 'viewOnceMessageV2Extension' in msg_obj:
        msg_obj = msg_obj['viewOnceMessageV2Extension'].get('message', {})

    # 4. Documento com Legenda (Às vezes o texto vem aqui dentro)
    if 'documentWithCaptionMessage' in msg_obj:
        msg_obj = msg_obj['documentWithCaptionMessage'].get('message', {})

    # 5. Mensagem Editada (Pega o conteúdo novo)
    if 'editedMessage' in msg_obj:
        msg_obj = msg_obj['editedMessage'].get('message', {})

    # --- FASE 2: EXTRAIR O TEXTO REAL ---
    texto = None

    # Caso A: Texto Simples (Antigo/Padrão)
    if 'conversation' in msg_obj:
        texto = msg_obj['conversation']

    # Caso B: Texto Estendido (O mais comum hoje, com link preview, formatação, etc)
    elif 'extendedTextMessage' in msg_obj:
        texto = msg_obj['extendedTextMessage'].get('text')

    # Caso C: Legendas de Mídia (Se o cliente mandar foto com texto)
    elif 'imageMessage' in msg_obj:
        texto = msg_obj['imageMessage'].get('caption', '')  # Retorna vazio se não tiver legenda
        if not texto: texto = "[Imagem enviada]"  # Opcional: marcador

    elif 'videoMessage' in msg_obj:
        texto = msg_obj['videoMessage'].get('caption', '')
        if not texto: texto = "[Vídeo enviado]"

    elif 'documentMessage' in msg_obj:
        texto = msg_obj['documentMessage'].get('caption', '')
        if not texto: texto = "[Documento enviado]"

    return texto

def processar_disparo_kommo(params: dict):
    """
    Ponto de entrada para o fluxo do Kommo (Agente 1).
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
    try:

        instancia_recebida = data.get("instance")
        mensagem_data = data.get('data', {})
        push_name = mensagem_data.get('pushName', '')
        key_data = mensagem_data.get('key', {})

        raw_remote_jid = key_data.get('remoteJid')
        raw_remote_jid_alt = data.get('data', {}).get('key', {}).get('remoteJidAlt')

        if raw_remote_jid and "@lid" in raw_remote_jid:
            if raw_remote_jid_alt and "@s.whatsapp.net" in raw_remote_jid_alt:
                remote_jid = raw_remote_jid_alt
            else:
                print("[APP HANDLER] ERRO CRÍTICO: Recebido LID sem JID alternativo.")
                return
        else:
            remote_jid = raw_remote_jid

        if key_data.get('fromMe') is True or not remote_jid:
            return

        numero_remetente_limpo = remote_jid.split('@')[0].lstrip('+')

        contexto = buscar_contexto_conversa(numero_remetente_limpo)
        if not contexto:
            print(f"[APP HANDLER] Ignorando msg. Lead não encontrado.")
            return

        status_atual = contexto.get('status_atual')
        status_permitidos = ['aguardando resposta', 'sem envio', 'em tratativa']
        if status_atual not in status_permitidos:
            print(f"[APP HANDLER] Bloqueio Ativo ({status_atual}). Ignorando.")
            return

        mensagem_recebida = None
        msg_obj = mensagem_data.get('message', {})

        # Chama a função que trata todas as possibilidades
        mensagem_recebida = extrair_conteudo_mensagem(msg_obj)

        if not mensagem_recebida:
            print("[APP HANDLER] Mensagem vazia ou tipo não suportado (Audio/Sticker sem legenda). Ignorando.")
            return

        print(f"[APP HANDLER] ✅ Mensagem processada com sucesso: '{mensagem_recebida}'")
        # ---------------------------------------

        # Salva no banco
        salvar_mensagem_usuario(contexto['numero_id'], mensagem_recebida)

        # Prepara dados para o buffer/agente
        input_data = {
            "lead_id": contexto['lead_id'],
            "numero_id": contexto['numero_id'],
            "historico_chat": contexto['historico_chat'],
            "numero_remetente": numero_remetente_limpo,
            "mensagem_recebida": mensagem_recebida,
            "instance_id": instancia_recebida,
            "nome_perfil_whatsapp": push_name
        }

        # Envia para o debounce (que chamará o agente_responder)
        adicionar_mensagem_buffer(
            remote_jid=remote_jid,
            input_data=input_data,
            callback_funcao=run_agente_responder
        )

    except Exception as e:
        print(f"[APP HANDLER] ❌ Erro ao processar resposta: {e}")