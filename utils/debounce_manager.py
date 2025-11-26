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

        # 1. Junta todas as mensagens acumuladas
        texto_completo = "\n".join(conteudo['textos'])

        # 2. Atualiza o input_data com o texto completo
        dados_finais = conteudo['data']
        dados_finais['mensagem_recebida'] = texto_completo

        print(f"\n[DEBOUNCE] Tempo esgotado para {remote_jid}.")
        print(f"[DEBOUNCE] Processando texto acumulado: '{texto_completo}'")

        # 3. Limpa o buffer
        del buffers[remote_jid]

        # 4. Executa a função do Agente (callback)
        callback_funcao(dados_finais)


def adicionar_mensagem_buffer(remote_jid: str, input_data: dict, callback_funcao: Callable):
    """
    Recebe uma mensagem, cancela o timer anterior e agenda um novo.
    """
    mensagem_nova = input_data['mensagem_recebida']

    # Se já existe um timer rodando para esse número, cancela ele!
    if remote_jid in buffers:
        print(f"[DEBOUNCE] Nova mensagem de {remote_jid} recebida antes do tempo. Resetando timer...")
        buffers[remote_jid]['timer'].cancel()
        buffers[remote_jid]['textos'].append(mensagem_nova)
        # Atualizamos o 'data' para ter o contexto mais recente (instancia, etc)
        buffers[remote_jid]['data'] = input_data
    else:
        print(f"[DEBOUNCE] Iniciando timer de {TEMPO_DE_ESPERA}s para {remote_jid}...")
        buffers[remote_jid] = {
            'textos': [mensagem_nova],
            'data': input_data,
            'timer': None
        }

    # Cria um novo timer
    t = threading.Timer(
        TEMPO_DE_ESPERA,
        processar_buffer,
        args=[remote_jid, callback_funcao]
    )
    t.start()

    buffers[remote_jid]['timer'] = t