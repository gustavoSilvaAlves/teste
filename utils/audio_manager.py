import base64
import tempfile
import os
from openai import OpenAI
from config import OPENAI_API_KEY

# Inicializa o cliente
client = OpenAI(api_key=OPENAI_API_KEY)


def transcrever_audio_base64(base64_string: str) -> str:
    """
    Recebe uma string Base64 de áudio, salva em arquivo temporário,
    envia para o Whisper (OpenAI) e retorna o texto transcrito.
    """
    if not base64_string:
        return ""

    temp_path = None
    try:
        # 1. Cria um arquivo temporário .mp3 ou .ogg
        # (O Whisper aceita vários formatos, mp3 é seguro)
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as temp_file:
            temp_file.write(base64.b64decode(base64_string))
            temp_path = temp_file.name

        print("[AUDIO MANAGER] Enviando áudio para transcrição (Whisper)...")

        # 2. Envia para a OpenAI
        with open(temp_path, "rb") as audio_file:
            transcription = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                response_format="text"  # Queremos apenas o texto puro
            )

        texto_transcrito = transcription.strip()
        print(f"[AUDIO MANAGER] Transcrição: '{texto_transcrito}'")

        return texto_transcrito

    except Exception as e:
        print(f"[AUDIO MANAGER] Erro na transcrição: {e}")
        return ""

    finally:
        # 3. Limpeza: Apaga o arquivo temporário
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)