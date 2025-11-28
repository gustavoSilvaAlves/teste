import re

def limpar_numero_telefone(telefone_raw: str) -> str:
    if not telefone_raw:
        return ""

    apenas_digitos = re.sub(r'\D', '', str(telefone_raw))

    if not apenas_digitos:
        return ""

    return f"+{apenas_digitos}"