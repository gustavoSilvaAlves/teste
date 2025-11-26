import os
from dotenv import load_dotenv

load_dotenv()


# --- Configurações API ---
KOMMO_API_TOKEN = os.getenv("KOMMO_API_TOKEN")
KOMMO_API_SUBDOMAIN = os.getenv("KOMMO_API_SUBDOMAIN")
EVOLUTION_API_URL = os.getenv("EVOLUTION_API_URL")
EVOLUTION_API_KEY = os.getenv("EVOLUTION_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# --- Configurações DB ---
DB_HOST = os.getenv("DB_HOST")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")


ID_STATUS_QUALIFICACAO_HUMANA = 96744300