from dotenv import load_dotenv
load_dotenv()
from flask import Flask, request, Response
import logging
import threading
import os

import json
from app_handler import processar_resposta_evolution, processar_disparo_kommo
from services.db_manager import resetar_banco_para_testes

DB_HOST = os.getenv("DB_HOST")

log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)
app = Flask(__name__)


@app.route("/webhook/kommo", methods=["POST"])
def receive_kommo_webhook():
    try:
        data = request.form

        print("\n--------------- WEBHOOK KOMMO ---------------")
        id_lead = None


        for key in data.keys():
            if 'leads[status]' in key and '[id]' in key:
                id_lead = data[key]
                break

        if not id_lead:
            for key in data.keys():
                if 'leads[add]' in key and '[id]' in key:
                    id_lead = data[key]
                    break

        if id_lead:
            print(f"[WEBHOOK KOMMO] Lead ID detectado: {id_lead}")
            print(f"[WEBHOOK KOMMO] Iniciando processamento em background...")

            params = {
                "id_lead": id_lead,
                "origem": "webhook_kommo"
            }

            thread = threading.Thread(target=processar_disparo_kommo, args=(params,))
            thread.start()

            return Response(status=200)
        else:
            print("[WEBHOOK KOMMO] Recebido, mas ID do lead não encontrado no payload.")
            return Response(status=200)

    except Exception as e:
        print(f"[WEBHOOK KOMMO] Erro no endpoint: {e}")
        return Response(status=500)

@app.route("/webhook/evolution", methods=["POST"])
def receive_evolution_webhook():
    try:
        data = request.json
        print("\n----------------- PAYLOAD RECEBIDO -----------------\n")
        print(json.dumps(data, indent=2))
        print("\n--- WEBHOOK RECEBIDO ---")

        if data.get("event") == "messages.upsert":
            thread = threading.Thread(target=processar_resposta_evolution, args=(data,))
            thread.start()

        return Response(status=200)
    except Exception as e:
        print(f"WEBHOOK Erro no endpoint: {e}")
        return Response(status=400)


@app.route("/webhook/reset", methods=["POST"])
def receive_reset_webhook():
    """
    Gatilho especial para LIMPAR o banco de dados e permitir testes.
    Acione ao mover o card para a fase 'REINICIAR BOT' no Kommo.
    """
    print("\n" + "☢️ " * 10 + " WEBHOOK RESET " + "☢️ " * 10)
    print("Recebido comando para limpar a base de dados...")

    try:
        sucesso = resetar_banco_para_testes()
        if sucesso:
            print("Base de dados limpa com sucesso.")
            return Response("Reset Realizado", status=200)
        else:
            return Response("Erro no Reset", status=500)
    except Exception as e:
        print(f"Erro no Reset: {e}")
        return Response(status=500)



if __name__ == "__main__":
    if not DB_HOST:
        print("ERRO: Credenciais do banco de dados")
    else:
        app.run(host="0.0.0.0", port=8000)