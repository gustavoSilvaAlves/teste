from flask import Flask, request, Response
import logging
import threading
import os
from dotenv import load_dotenv
import json
from app_handler import processar_resposta_evolution

load_dotenv()
DB_HOST = os.getenv("DB_HOST")

log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)
app = Flask(__name__)


@app.route("/webhook/evolution", methods=["POST"])
def receive_evolution_webhook():
    try:
        data = request.json

        # --- DEBUG: IMPRIMIR O JSON INTEIRO ---
        print("\n" + "" * 20 + " PAYLOAD RECEBIDO " + "" * 20)
        # Imprime tudo formatado para lermos a estrutura
        print(json.dumps(data, indent=2))
        print("" * 60 + "\n")

        print("\n--- [WEBHOOK RECEBIDO] ---")

        if data.get("event") == "messages.upsert":
            thread = threading.Thread(target=processar_resposta_evolution, args=(data,))
            thread.start()

        return Response(status=200)
    except Exception as e:
        print(f"WEBHOOK Erro no endpoint: {e}")
        return Response(status=400)


if __name__ == "__main__":
    if not DB_HOST:
        print("ERRO: Credenciais do banco de dados (DB_HOST) não encontradas no .env")
    else:
        PORTA = 8000
        print(f"Iniciando servidor Flask em http://localhost:{PORTA}")
        print("Ouvindo webhooks da Evolution em /webhook/evolution")
        app.run(host="0.0.0.0", port=PORTA)