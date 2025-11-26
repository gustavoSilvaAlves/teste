from agents import agente_iniciador
import sys
from pathlib import Path
ROOT_DIR = Path(__file__).resolve().parent
sys.path.append(str(ROOT_DIR))

params_kommo = {
    "service": "chatbot",
    "id_template": "4",
    "no_proc_pagamento": "6008829-48.2025.4.06.9388",
    "ano_loa": "2027",
    "requerido": "INSS",
    "telefones": "+5532991749187, +5532998068067, +5532984041870, +5532987024577, +5532998289262",
    "primeiro_nome": "Francisca",
    "id_lead": "21500005",
    "id_contato": "24803037",
    "vl_meta_compra_liquido": "178.516,16",
    "tribunal": "TRF 6",
    "dt_autuacao": "03.10.2025"
}


def disparar_tarefa_chatbot():
    print(f"--- [DISPARADOR] ---")
    print(f"Disparando tarefa '{params_kommo['service']}' para Lead ID: {params_kommo['id_lead']}")

    try:
        agente_iniciador.iniciar_verificacao(params_kommo)
    except Exception as e:
        print(f"\n--- [DISPARADOR] ---")
        print(f"O agente relatou um erro crítico: {e}")


if __name__ == "__main__":
    disparar_tarefa_chatbot()