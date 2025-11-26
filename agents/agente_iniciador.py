import threading
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT_DIR))

from services.api_clients import consultar_lead_kommo, consultar_contato_kommo, enviar_mensagem_evolution
from services.db_manager import logar_envio_inicial_db, find_comprador_local_id, find_outbound_number, sincronizar_numeros_lead, buscar_proximo_numero_sem_envio

# NOVO: Importa o gerenciador de mensagens
from utils.message_manager import selecionar_primeira_mensagem
from utils.phone_utils import limpar_numero_telefone


def iniciar_verificacao(params: dict):
    """Função principal que o disparador chama."""
    print(f"\n--- [AGENTE INICIADOR] ---")
    id_lead = params.get("id_lead")
    if not id_lead: return

    # 1. CONSULTA AO LEAD
    dados_do_lead = consultar_lead_kommo(id_lead)
    if not dados_do_lead: return

    # Lógica de UF (já ajustada antes)
    uf_cliente = None
    try:
        for campo in dados_do_lead.get('custom_fields_values', []):
            if campo.get('field_name') == 'uf':
                uf_cliente = campo['values'][0].get('value')
                break
    except:
        pass
    if not uf_cliente: uf_cliente = 'todos'

    # 2. ENCONTRAR COMPRADOR
    kommo_responsavel_id = dados_do_lead.get('responsible_user_id')
    comprador_local_id = find_comprador_local_id(kommo_responsavel_id)
    if not comprador_local_id:
        print(f"[AGENTE] Responsável {kommo_responsavel_id} não encontrado.")
        return

    # 3. SELECIONAR NÚMERO
    outbound = find_outbound_number(comprador_local_id, uf_cliente)
    if not outbound: return
    evolution_instance_id = outbound['instance_id']

    # 4. ENCONTRAR NOME E TELEFONE
    id_contato_principal = None

    for c in dados_do_lead.get('_embedded', {}).get('contacts', []):
        if c.get('is_main'): id_contato_principal = c.get('id'); break


    telefones_brutos_api = []
    nome_contato = params.get('primeiro_nome', 'Cliente')

    if id_contato_principal:
        dados_contato = consultar_contato_kommo(id_contato_principal)
        if dados_contato:
            # (Lógica de nome mantida...)
            nome_custom = None
            for cf in dados_contato.get('custom_fields_values', []):
                if cf.get('field_name') == 'primeiro_nome' and cf.get('values'):
                    nome_custom = cf['values'][0].get('value')
                    break
            nome_contato = nome_custom or dados_contato.get('first_name') or nome_contato

            # Extrai lista bruta para sincronizar
            for cf in dados_contato.get('custom_fields_values', []):
                if cf.get('field_code') == 'PHONE':
                    for v in cf.get('values', []):
                        # --- CORREÇÃO AQUI ---
                        num_sujo = str(v.get('value'))
                        num_limpo = limpar_numero_telefone(num_sujo)
                        # Só adiciona se for um número válido
                        if len(num_limpo) > 8:
                            telefones_brutos_api.append(num_limpo)
                        # ---------------------
                    break

    # --- A NOVA LÓGICA SIMPLIFICADA ---

    # 1. Sincroniza: Garante que o banco conhece todos os números desse lead
    sincronizar_numeros_lead(int(id_lead), telefones_brutos_api)

    # 2. Consulta: Pede ao banco o próximo elegível
    telefone_destino = buscar_proximo_numero_sem_envio(int(id_lead))

    if not telefone_destino:
        print("[AGENTE INICIADOR] Todos os números deste lead já foram contatados. Nada a fazer.")
        return

    # ----------------------------------

    # 5. ENVIAR
    mensagem_para_enviar = selecionar_primeira_mensagem(nome_contato)
    print(f"[AGENTE INICIADOR] Enviando msg para: {telefone_destino}")

    resultado = enviar_mensagem_evolution(
        numero_destino=telefone_destino,
        mensagem=mensagem_para_enviar,
        evolution_instance_id=evolution_instance_id
    )

    if resultado:
        # Passamos a lista completa 'telefones_brutos_api' apenas para manter o registro
        # mas a lógica de qual foi usado já foi resolvida antes
        log_thread = threading.Thread(
            target=logar_envio_inicial_db,
            args=(int(id_lead), int(id_contato_principal), comprador_local_id,
                  nome_contato, telefones_brutos_api, telefone_destino, mensagem_para_enviar)
        )
        log_thread.start()
    else:
        print("[AGENTE] Falha envio.")

    print("--- [AGENTE INICIADOR] --- Finalizado.")