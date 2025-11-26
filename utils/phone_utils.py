import re

def limpar_numero_telefone(telefone_raw: str) -> str:
    """
    Recebe qualquer string (ex: '+55 61 9999-8888', '(11) 99999 8888')
    e retorna apenas o formato padrão: +5511999998888
    """
    if not telefone_raw:
        return ""

    apenas_digitos = re.sub(r'\D', '', str(telefone_raw))

    if not apenas_digitos:
        return ""

    return f"+{apenas_digitos}"