import threading
from typing import Callable


buffers = {}


TEMPO_DE_ESPERA = 10.0


def processar_buffer(remote_jid: str, callback_funcao: Callable):
    """
    Chamado quando o timer estoura. Junta os textos e chama o Agente.
    """
    if remote_jid in buffers:
        conteudo = buffers[remote_jid]

        texto_completo = "\n".join(conteudo['textos'])

        dados_finais = conteudo['data']
        dados_finais['mensagem_recebida'] = texto_completo

        print(f"\n[DEBOUNCE] Tempo esgotado para {remote_jid}.")
        print(f"[DEBOUNCE] Processando texto acumulado: '{texto_completo}'")

        del buffers[remote_jid]

        callback_funcao(dados_finais)


def adicionar_mensagem_buffer(remote_jid: str, input_data: dict, callback_funcao: Callable):
    """
    Recebe uma mensagem, cancela o timer anterior e agenda um novo.
    """
    mensagem_nova = input_data['mensagem_recebida']

    if remote_jid in buffers:
        print(f"[DEBOUNCE] Nova mensagem de {remote_jid} recebida antes do tempo. Resetando timer...")
        buffers[remote_jid]['timer'].cancel()
        buffers[remote_jid]['textos'].append(mensagem_nova)
        buffers[remote_jid]['data'] = input_data
    else:
        print(f"[DEBOUNCE] Iniciando timer de {TEMPO_DE_ESPERA}s para {remote_jid}...")
        buffers[remote_jid] = {
            'textos': [mensagem_nova],
            'data': input_data,
            'timer': None
        }

    t = threading.Timer(
        TEMPO_DE_ESPERA,
        processar_buffer,
        args=[remote_jid, callback_funcao]
    )
    t.start()

    buffers[remote_jid]['timer'] = t