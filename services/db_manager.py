import pymysql
from config import DB_HOST, DB_USER, DB_PASSWORD, DB_NAME
from utils.phone_utils import limpar_numero_telefone

def get_db_connection():
    try:
        conn = pymysql.connect(
            host=DB_HOST, user=DB_USER, password=DB_PASSWORD,
            database=DB_NAME, connect_timeout=10, charset='utf8mb4'
        )
        return conn
    except pymysql.Error as err:
        print(f"[DB MANAGER] Erro ao conectar ao MySQL: {err}")
        return None


def logar_envio_inicial_db(kommo_lead_id: int, kommo_contact_id: int, comprador_local_id: int, nome_contato: str,
        telefones_encontrados: list, telefone_usado: str, mensagem_enviada: str
):
    """Salva o lead, os números e a primeira mensagem no banco de dados."""
    print("[DB MANAGER] Logando envio inicial...")
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        if not conn:
            raise Exception("Falha ao obter conexão com o DB.")
        cursor = conn.cursor()

        sql_lead = """
        INSERT INTO leads (kommo_lead_id, kommo_contact_id, comprador_id, nome_contato, status)
        VALUES (%s, %s, %s, %s, 'Em tratativa')
        ON DUPLICATE KEY UPDATE 
            kommo_contact_id = VALUES(kommo_contact_id), 
            comprador_id = VALUES(comprador_id),
            nome_contato = VALUES(nome_contato),
            status = IF(status = 'Concluído', 'Concluído', VALUES(status))
        """
        cursor.execute(sql_lead, (kommo_lead_id, kommo_contact_id, comprador_local_id, nome_contato))

        cursor.execute("SELECT id FROM leads WHERE kommo_lead_id = %s", (kommo_lead_id,))
        local_lead_id = cursor.fetchone()[0]

        sql_numero = "INSERT IGNORE INTO contato_numeros (lead_id, numero) VALUES (%s, %s)"
        for numero in telefones_encontrados:
            cursor.execute(sql_numero, (local_lead_id, numero))

        cursor.execute("SELECT id FROM contato_numeros WHERE lead_id = %s AND numero = %s",
                       (local_lead_id, telefone_usado))
        local_numero_id = cursor.fetchone()[0]

        sql_mensagem = "INSERT INTO mensagens (numero_id, conteudo, remetente) VALUES (%s, %s, 'agente')"
        cursor.execute(sql_mensagem, (local_numero_id, mensagem_enviada))

        sql_status = "UPDATE contato_numeros SET status = 'aguardando resposta' WHERE id = %s"
        cursor.execute(sql_status, (local_numero_id,))

        conn.commit()
        print(f"[DB MANAGER] Log salvo com sucesso para o Lead {kommo_lead_id}.")

    except Exception as e:
        print(f"[DB MANAGER] ERRO CRÍTICO ao salvar log: {e}")
        if conn: conn.rollback()
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


def buscar_contexto_conversa(numero_remetente_limpo: str):
    """
    Busca contexto e o STATUS do número.
    """
    print(f"[DB MANAGER] Buscando contexto para o número: {numero_remetente_limpo}")
    conn = None
    cursor = None

    termo_busca_1 = f"+{numero_remetente_limpo}"
    termo_busca_2 = None
    if numero_remetente_limpo.startswith('55') and len(numero_remetente_limpo) == 12:
        termo_busca_2 = f"+{numero_remetente_limpo[0:4]}9{numero_remetente_limpo[4:]}"

    try:
        conn = get_db_connection()
        if not conn: raise Exception("Falha na conexão com DB.")
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        sql_find_lead = """
        SELECT 
            l.id as lead_id, 
            cn.id as numero_id,
            cn.numero as numero_encontrado,
            cn.status as status_atual  -- <--- NOVO CAMPO RECUPERADO
        FROM 
            contato_numeros cn
        JOIN 
            leads l ON cn.lead_id = l.id
        WHERE 
            TRIM(cn.numero) = %s OR TRIM(cn.numero) = %s
        LIMIT 1;
        """
        cursor.execute(sql_find_lead, (termo_busca_1, termo_busca_2))
        ids = cursor.fetchone()

        if not ids:
            raise Exception(f"Nenhum lead encontrado para {termo_busca_1}")

        lead_id = ids['lead_id']
        numero_id = ids['numero_id']
        status_atual = ids['status_atual']

        sql_find_history = "SELECT conteudo, remetente FROM mensagens WHERE numero_id = %s ORDER BY data_envio ASC;"
        cursor.execute(sql_find_history, (numero_id,))
        historico = cursor.fetchall()

        return {
            "lead_id": lead_id,
            "numero_id": numero_id,
            "status_atual": status_atual,
            "historico_chat": list(historico)
        }

    except Exception as e:
        print(f"[DB MANAGER] ERRO ao buscar contexto: {e}")
        return None
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


def salvar_mensagem_usuario(numero_id: int, conteudo: str):
    """Salva a mensagem recebida do usuário e atualiza o status."""
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        if not conn:
            raise Exception("Falha na conexão com DB.")
        cursor = conn.cursor()

        sql_msg = "INSERT INTO mensagens (numero_id, conteudo, remetente) VALUES (%s, %s, 'usuario')"
        cursor.execute(sql_msg, (numero_id, conteudo))

        sql_status = "UPDATE contato_numeros SET status = 'em tratativa' WHERE id = %s AND status = 'aguardando resposta';"
        cursor.execute(sql_status, (numero_id,))

        conn.commit()
        print(f"[DB MANAGER] Mensagem do usuário salva no DB.")
    except Exception as e:
        print(f"[DB MANAGER] ERRO ao salvar msg do usuário: {e}")
        if conn: conn.rollback()
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


def atualizar_status_contato(numero_id: int, novo_status: str):
    """Função auxiliar para atualizar o status final no DB."""
    print(f"[DB MANAGER] Atualizando status para '{novo_status}'...")
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        sql = "UPDATE contato_numeros SET status = %s WHERE id = %s"
        cursor.execute(sql, (novo_status, numero_id))
        conn.commit()
    except Exception as e:
        print(f"[DB MANAGER] ERRO ao atualizar status: {e}")
        if conn: conn.rollback()
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


def salvar_mensagem_agente(numero_id: int, conteudo: str):
    """Salva a resposta do AGENTE no banco."""
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        if not conn:
            raise Exception("Falha na conexão com DB.")

        cursor = conn.cursor()
        sql = "INSERT INTO mensagens (numero_id, conteudo, remetente) VALUES (%s, %s, 'agente')"
        cursor.execute(sql, (numero_id, conteudo))
        conn.commit()
        print(f"[DB MANAGER] Mensagem do AGENTE salva no DB.")

    except Exception as e:
        print(f"[DB MANAGER] ERRO ao salvar msg do agente: {e}")
        if conn: conn.rollback()
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


def find_comprador_local_id(kommo_user_id: int):
    """Encontra o ID local do comprador a partir do ID do usuário Kommo."""
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        sql = "SELECT id FROM compradores WHERE kommo_user_id = %s LIMIT 1"
        cursor.execute(sql, (kommo_user_id,))
        resultado = cursor.fetchone()
        if resultado:
            return resultado[0]
    except Exception as e:
        print(f"[DB MANAGER] Erro ao buscar ID do comprador: {e}")
    finally:
        if cursor: cursor.close()
        if conn: conn.close()
    return None


def find_outbound_number(comprador_id: int, uf: str):
    """
    Encontra o melhor número de saída (outbound) para um comprador,
    baseado na UF do cliente. Faz rodízio (round-robin) pelo menos usado.
    """
    print(f"[DB MANAGER] Buscando número de saída para Comprador ID: {comprador_id}, UF: {uf}")
    conn = None
    cursor = None

    try:
        conn = get_db_connection()
        if not conn:
            raise Exception("Falha na conexão com DB.")
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        sql_find = """
        SELECT id, numero, evolution_instance_id 
        FROM numeros_outbound
        WHERE comprador_id = %s
          AND uf = %s
          AND status = 'ativo'
        ORDER BY contagem_uso ASC, data_ultimo_uso ASC
        LIMIT 1;
        """
        cursor.execute(sql_find, (comprador_id, uf))
        numero_encontrado = cursor.fetchone()

        if not numero_encontrado:
            print(f"[DB MANAGER] Nenhum número específico para UF '{uf}'. Procurando por 'todos'.")
            sql_find_coringa = """
            SELECT id, numero, evolution_instance_id 
            FROM numeros_outbound
            WHERE comprador_id = %s
              AND uf = 'todos'
              AND status = 'ativo'
            ORDER BY contagem_uso ASC, data_ultimo_uso ASC
            LIMIT 1;
            """
            cursor.execute(sql_find_coringa, (comprador_id,))
            numero_encontrado = cursor.fetchone()

        if not numero_encontrado:
            raise Exception(f"Nenhum número 'ativo' encontrado para o comprador {comprador_id} (UF: {uf} ou 'todos')")

        numero_outbound_id = numero_encontrado['id']

        sql_update_uso = """
        UPDATE numeros_outbound
        SET contagem_uso = contagem_uso + 1,
            data_ultimo_uso = CURRENT_TIMESTAMP
        WHERE id = %s;
        """
        cursor.execute(sql_update_uso, (numero_outbound_id,))
        conn.commit()

        print(
            f"[DB MANAGER] Número de saída selecionado: {numero_encontrado['numero']} (Instância: {numero_encontrado['evolution_instance_id']})")

        return {
            "numero_comprador": numero_encontrado['numero'],
            "instance_id": numero_encontrado['evolution_instance_id']
        }

    except Exception as e:
        print(f"[DB MANAGER] ERRO ao buscar número de saída: {e}")
        if conn: conn.rollback()
        return None
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


def get_nome_responsavel_por_lead(lead_id: int):
    """Retorna o nome do comprador responsável pelo lead."""
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        sql = """
        SELECT c.nome 
        FROM leads l
        JOIN compradores c ON l.comprador_id = c.id
        WHERE l.id = %s
        LIMIT 1
        """
        cursor.execute(sql, (lead_id,))
        resultado = cursor.fetchone()

        if resultado:
            return resultado[0]

    except Exception as e:
        print(f"[DB MANAGER] Erro ao buscar nome do responsável: {e}")
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

    return None


def get_template_mensagem_balanceado(tipo: str):
    """
    Busca um template de mensagem ativo para o tipo especificado,
    usando lógica de load balance (menor uso primeiro).
    """
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        sql_select = """
        SELECT id, texto 
        FROM templates_mensagem 
        WHERE tipo = %s AND status = 'ativo'
        ORDER BY contagem_uso ASC, id ASC
        LIMIT 1
        """
        cursor.execute(sql_select, (tipo,))
        resultado = cursor.fetchone()

        if not resultado:
            print(f"[DB MANAGER] AVISO: Nenhum template encontrado para o tipo '{tipo}'")
            return None

        template_id = resultado['id']
        texto_raw = resultado['texto']

        sql_update = "UPDATE templates_mensagem SET contagem_uso = contagem_uso + 1 WHERE id = %s"
        cursor.execute(sql_update, (template_id,))
        conn.commit()

        return texto_raw

    except Exception as e:
        print(f"[DB MANAGER] Erro ao buscar template de mensagem: {e}")
        if conn: conn.rollback()
        return None
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


def buscar_proximo_lead_fila():
    """
    Busca o próximo número disponível para envio.
    Regra: Lead 'Em tratativa' E Número 'sem envio'.
    Prioridade: Leads mais antigos primeiro (FIFO).
    """
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        sql = """
        SELECT 
            l.kommo_lead_id,
            l.id as lead_id_local,
            cn.id as numero_id,
            cn.numero
        FROM 
            contato_numeros cn
        JOIN 
            leads l ON cn.lead_id = l.id
        WHERE 
            l.status = 'Em tratativa' 
            AND cn.status = 'sem envio'
        ORDER BY 
            l.data_criacao ASC -- Os mais antigos primeiro
        LIMIT 1;
        """
        cursor.execute(sql)
        resultado = cursor.fetchone()
        return resultado

    except Exception as e:
        print(f"[DB MANAGER] Erro ao buscar fila: {e}")
        return None
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


def sincronizar_numeros_lead(kommo_lead_id: int, lista_numeros_api: list):
    """
    Pega a lista de números vinda do Kommo e garante que todos
    estejam no banco. Se for novo, entra como 'sem envio'.
    """
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        sql_get_id = "SELECT id FROM leads WHERE kommo_lead_id = %s"
        cursor.execute(sql_get_id, (kommo_lead_id,))
        res = cursor.fetchone()

        local_lead_id = None
        if res:
            local_lead_id = res[0]
        else:
            cursor.execute("INSERT INTO leads (kommo_lead_id, kommo_contact_id) VALUES (%s, 0)", (kommo_lead_id,))
            local_lead_id = cursor.lastrowid

        sql_insert_num = """
        INSERT IGNORE INTO contato_numeros (lead_id, numero, status)
        VALUES (%s, %s, 'sem envio')
        """

        for num_raw in lista_numeros_api:
            num_limpo = limpar_numero_telefone(num_raw)

            if len(num_limpo) > 8:
                cursor.execute(sql_insert_num, (local_lead_id, num_limpo))

        conn.commit()
        print(f"[DB MANAGER] Sincronização de números concluída para o Lead {kommo_lead_id}.")
        return local_lead_id

    except Exception as e:
        print(f"[DB MANAGER] Erro ao sincronizar números: {e}")
        if conn: conn.rollback()
        return None
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


def buscar_proximo_numero_sem_envio(kommo_lead_id: int):
    """
    Retorna o primeiro número do lead que ainda está 'sem envio'.
    """
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        sql = """
        SELECT cn.numero 
        FROM contato_numeros cn
        JOIN leads l ON cn.lead_id = l.id
        WHERE l.kommo_lead_id = %s 
          AND cn.status = 'sem envio'
        ORDER BY cn.id ASC        
        LIMIT 1;
        """
        cursor.execute(sql, (kommo_lead_id,))
        res = cursor.fetchone()

        if res:
            return res[0]
        return None

    except Exception as e:
        print(f"[DB MANAGER] Erro ao buscar próximo número: {e}")
        return None
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


def get_kommo_id_from_local(local_lead_id: int):
    """
    Recebe o ID local (PK) e retorna o ID original do Kommo.
    """
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        sql = "SELECT kommo_lead_id FROM leads WHERE id = %s"
        cursor.execute(sql, (local_lead_id,))
        resultado = cursor.fetchone()

        if resultado:
            return resultado[0]

    except Exception as e:
        print(f"[DB MANAGER] Erro ao buscar Kommo ID: {e}")
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

    return None


def buscar_leads_para_finalizar_automaticamente():
    """
    Busca leads que estão 'Em tratativa' mas TODOS os seus números
    já atingiram um status final (confirmado, objeção, negado, parente).
    """
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        sql = """
        SELECT 
            l.id as lead_id,
            l.kommo_lead_id
        FROM leads l
        JOIN contato_numeros cn ON l.id = cn.lead_id
        WHERE l.status = 'Em tratativa'
        GROUP BY l.id, l.kommo_lead_id
        HAVING SUM(
            CASE 
                WHEN cn.status IN ('sem envio', 'aguardando resposta', 'em tratativa') THEN 1 
                ELSE 0 
            END
        ) = 0;
        """
        cursor.execute(sql)
        leads_para_fechar = cursor.fetchall()
        return leads_para_fechar

    except Exception as e:
        print(f"[DB MANAGER] Erro ao buscar leads para finalizar: {e}")
        return []
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


def marcar_lead_como_concluido(local_lead_id: int):
    """Atualiza apenas o status do lead local para Concluído."""
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        sql = "UPDATE leads SET status = 'Concluído' WHERE id = %s"
        cursor.execute(sql, (local_lead_id,))
        conn.commit()
        print(f"[DB MANAGER] Lead ID {local_lead_id} marcado como Concluído localmente.")
    except Exception as e:
        print(f"[DB MANAGER] Erro ao concluir lead local: {e}")
        if conn: conn.rollback()
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


def get_nome_lead_por_id(local_lead_id: int):
    """Retorna o nome do contato (cliente) do lead."""
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        sql = "SELECT nome_contato FROM leads WHERE id = %s"
        cursor.execute(sql, (local_lead_id,))
        resultado = cursor.fetchone()

        if resultado:
            return resultado[0]

    except Exception as e:
        print(f"[DB MANAGER] Erro ao buscar nome do lead: {e}")
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

    return None


def buscar_leads_expirados_24h():
    """
    Busca leads que foram criados há mais de 24 horas
    e ainda NÃO estão com status 'Concluído'.
    """
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        sql = """
        SELECT id, kommo_lead_id 
        FROM leads 
        WHERE status != 'Concluído' 
          AND data_criacao < (NOW() - INTERVAL 1 DAY);
        """
        cursor.execute(sql)
        resultados = cursor.fetchall()

        if resultados:
            print(f"[DB MANAGER] Encontrados {len(resultados)} leads expirados (+24h).")

        return resultados

    except Exception as e:
        print(f"[DB MANAGER] Erro ao buscar leads expirados: {e}")
        return []
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


def resetar_banco_para_testes():
    """
    LIMPA TODAS AS TABELAS DE DADOS (LEADS, NÚMEROS, MENSAGENS).
    USADO APENAS PARA TESTES/RESET.
    """
    print("\n[DB MANAGER] ⚠️ INICIANDO RESET COMPLETO DAS TABELAS... ⚠️")
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Desativa chaves estrangeiras para permitir truncar/deletar em qualquer ordem
        cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")
        cursor.execute("SET SQL_SAFE_UPDATES = 0;")  # Conforme solicitado

        # Limpa as tabelas (Ordem ideal: Filho -> Pai, mas com check=0 tanto faz)
        print("[DB MANAGER] Deletando Mensagens...")
        cursor.execute("DELETE FROM mensagens;")

        print("[DB MANAGER] Deletando Números...")
        cursor.execute("DELETE FROM contato_numeros;")

        print("[DB MANAGER] Deletando Leads...")
        cursor.execute("DELETE FROM leads;")

        # Restaura configurações de segurança
        cursor.execute("SET SQL_SAFE_UPDATES = 1;")
        cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")

        conn.commit()
        print("[DB MANAGER] ✅ RESET CONCLUÍDO! O BANCO ESTÁ LIMPO.\n")
        return True

    except Exception as e:
        print(f"[DB MANAGER] ❌ ERRO AO RESETAR BANCO: {e}")
        if conn: conn.rollback()
        return False
    finally:
        if cursor: cursor.close()
        if conn: conn.close()