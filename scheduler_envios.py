import time
import random
import sys
from pathlib import Path
import config

ROOT_DIR = Path(__file__).resolve().parent
sys.path.append(str(ROOT_DIR))

from services.db_manager import (
    buscar_proximo_lead_fila,
    buscar_leads_para_finalizar_automaticamente,
    marcar_lead_como_concluido,
    buscar_leads_expirados_24h
)

from services.api_clients import (
    atualizar_status_lead_kommo,
    criar_nota_lead_kommo
)

from agents.agente_iniciador import iniciar_verificacao


def calcular_tempo_espera():
    """Retorna segundos aleatórios entre 3 e 6 minutos."""
    minutos = random.uniform(3, 6)
    segundos = int(minutos * 60)
    return segundos


def processar_leads_expirados():
    """
    Move leads com mais de 24h de criação para Qualificação Humana.
    """
    print("[SCHEDULER] Verificando leads expirados (+24h)...")
    leads_vencidos = buscar_leads_expirados_24h()

    if not leads_vencidos:
        return

    print(f"[SCHEDULER] Processando {len(leads_vencidos)} leads vencidos.")

    for lead in leads_vencidos:
        local_id = lead['id']
        kommo_id = lead['kommo_lead_id']

        print(f"[SCHEDULER] Expirando Lead {kommo_id}...")

        # 1. Atualiza no Kommo (Qualificação Humana)
        sucesso = atualizar_status_lead_kommo(kommo_id, config.ID_STATUS_QUALIFICACAO_HUMANA)

        if sucesso:
            # 2. Cria a Nota Explicativa
            texto_nota = (
                "TIMEOUT AUTOMÁTICO (24H)\n"
                "Passaram-se 24 horas desde a entrada do lead e não houve uma "
                "identificação positiva clara nos números testados.\n"
                "O Lead foi movido para Qualificação Humana para análise manual."
            )
            criar_nota_lead_kommo(kommo_id, texto_nota)

            # 3. Conclui no Banco Local (para sair da fila de envio)
            marcar_lead_como_concluido(local_id)
        else:
            print(f"[SCHEDULER] Falha ao atualizar Kommo para o lead {kommo_id}.")


def processar_leads_finalizados():
    """
    Verifica leads onde todos os números já foram processados
    e move eles para a próxima etapa no Kommo.
    """
    print("[SCHEDULER] Verificando leads para encerramento automático...")
    leads_esgotados = buscar_leads_para_finalizar_automaticamente()

    if not leads_esgotados:
        print("[SCHEDULER] Nenhum lead para encerrar.")
        return

    print(f"[SCHEDULER] Encontrados {len(leads_esgotados)} leads para encerrar.")

    for lead in leads_esgotados:
        local_id = lead['lead_id']
        kommo_id = lead['kommo_lead_id']

        print(f"[SCHEDULER] Encerrando Lead {kommo_id} (Todos os números processados).")

        # 1. Atualiza no Kommo
        sucesso_kommo = atualizar_status_lead_kommo(
            kommo_id,
            config.ID_STATUS_QUALIFICACAO_HUMANA
        )

        if sucesso_kommo:
            # Adiciona nota explicativa
            criar_nota_lead_kommo(
                kommo_id,
                "IDENTIFICAÇÃO FINALIZADA\nTodos os números vinculados a este lead foram contatados e finalizados."
            )
            marcar_lead_como_concluido(local_id)
        else:
            print(f"[SCHEDULER]Falha ao atualizar Kommo para o lead {kommo_id}. Tentará no próximo ciclo.")


def worker_loop():
    print("---INICIANDO SCHEDULER DE ENVIOS ---")
    print("Critérios: Lead 'Em tratativa' | Número 'sem envio'")
    print("Intervalo: Aleatório entre 3 a 6 minutos.")
    print("-" * 50)

    while True:
        tempo_espera = calcular_tempo_espera()


        minutos_display = tempo_espera // 60
        segundos_display = tempo_espera % 60
        print(f"\n[Aguardando {minutos_display}m {segundos_display}s para o próximo ciclo...")

        time.sleep(tempo_espera)

        try:
            processar_leads_finalizados()
            processar_leads_expirados()
        except Exception as e:
            print(f"[SCHEDULER] Erro na varredura: {e}")

        print("[SCHEDULER]Buscando próximo lead na fila...")

        try:
            proximo_item = buscar_proximo_lead_fila()

            if proximo_item:
                lead_id = proximo_item['kommo_lead_id']
                print(f"[SCHEDULER] Lead encontrado! ID Kommo: {lead_id}")
                payload = {
                    "id_lead": lead_id,
                    "service": "scheduler_autom",
                    "primeiro_nome": "Cliente"
                }

                print(f"[SCHEDULER] Executando Agente Iniciador...")
                iniciar_verificacao(payload)
                print(f"[SCHEDULER]Processamento do Lead {lead_id} finalizado.")

            else:
                print("[SCHEDULER] Fila vazia. Nenhum número pendente encontrado.")

        except Exception as e:
            print(f"[SCHEDULER]Erro crítico no loop: {e}")


if __name__ == "__main__":
    try:
        worker_loop()
    except KeyboardInterrupt:
        print("\n[SCHEDULER] Parando o robô...")