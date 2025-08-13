import os
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
import traceback

# Tentar importar psycopg2, mas continuar mesmo se não estiver disponível
try:
    import psycopg2
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False
    print("AVISO: psycopg2 não está instalado. A conexão com o banco de dados não estará disponível.")
    print("Para instalar, execute: pip install psycopg2-binary")

# Tentar importar openai para integração com ChatGPT
try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    print("AVISO: openai não está instalado. Para usar ChatGPT, execute: pip install openai")

# Carregar variáveis de ambiente
load_dotenv()

# Configuração da aplicação Flask
app = Flask(__name__)

# Configuração do OpenAI
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
if OPENAI_AVAILABLE and OPENAI_API_KEY:
    openai.api_key = OPENAI_API_KEY

# Descrição das colunas da tabela a_receber_turbo para o ChatGPT
TABELA_DESCRICAO = """
Tabela: a_receber_turbo
Colunas:
- status: indica o status do pagamento (ACQUITTED=paga, OVERDUE=inadimplente, LOST=perda, PENDING=pendente)
- total: valor total da parcela
- descricao: descrição sobre o que se refere a parcela
- data_vencimento: data de vencimento da parcela
- nao_pago: quanto deixou de ser pago da parcela
- pago: quanto foi pago da parcela
- cliente_nome: nome do cliente que pagará a parcela
- cnpj: CNPJ do cliente
- telefone: número de celular do cliente
- status_clickup: status operacional do cliente
- link_pagamento: link de pagamento da parcela

Tabela: clientes_turbo
Colunas:
- nome: nome do cliente
- cnpj: CNPJ do cliente

Tabela: clientes_clickup
Colunas:
- responsavel: responsável pelo cliente
- segmento: segmento do cliente
- cluster: cluster do cliente
- status_conta: status da conta do cliente
- atividade: atividade do cliente
- telefone: telefone do cliente
"""

# Rota principal - TurboX Dashboard
@app.route('/turbox')
def turbox_dashboard():
    """Página principal do TurboX - Central de Ferramentas"""
    return render_template('turbox.html')

# Função para conectar ao banco de dados
def get_db_connection():
    if not PSYCOPG2_AVAILABLE:
        return None
        
    try:
        # Verificar se estamos no Railway/Heroku (DATABASE_URL estará disponível)
        database_url = os.environ.get('DATABASE_URL')
        
        if database_url:
            # Formato esperado: postgresql://user:password@host:port/dbname
            # Heroku usa postgres:// que precisa ser convertido para postgresql://
            if database_url.startswith('postgres://'):
                database_url = database_url.replace('postgres://', 'postgresql://', 1)
            
            # Conectar usando a URL do banco de dados
            conn = psycopg2.connect(database_url)
        else:
            # Conectar usando variáveis de ambiente individuais
            host = os.getenv("PG_HOST")
            dbname = os.getenv("PG_DBNAME")
            user = os.getenv("PG_USER")
            password = os.getenv("PG_PASSWORD")
            port = os.getenv("PG_PORT", "5432")
            
            # Verificar se as variáveis essenciais estão definidas
            if not all([host, dbname, user, password]):
                app.logger.warning("Variáveis de ambiente do banco de dados não configuradas")
                return None
                
            conn = psycopg2.connect(
                host=host,
                dbname=dbname,
                user=user,
                password=password,
                port=port
            )
        conn.autocommit = True
        return conn
    except Exception as e:
        app.logger.error(f"Erro ao conectar ao banco de dados: {str(e)}")
        return None

def interpretar_consulta_com_chatgpt(mensagem_usuario):
    """Usar ChatGPT para interpretar a consulta do usuário e gerar SQL"""
    if not OPENAI_AVAILABLE or not OPENAI_API_KEY:
        return None, "ChatGPT não está configurado. Configure OPENAI_API_KEY."
    
    try:
        prompt = f"""
Você é um assistente especializado em consultas SQL para um sistema financeiro.

{TABELA_DESCRICAO}

Consulta do usuário: "{mensagem_usuario}"

Gere uma query SQL PostgreSQL para responder à consulta do usuário. 
Retorne APENAS o SQL, sem explicações.
Use JOINs quando necessário entre as tabelas.
Para consultas de valores, use SUM() para somar valores.
Para datas, use CURRENT_DATE para data atual.
Para filtros de status, use os valores exatos: ACQUITTED, OVERDUE, LOST, PENDING.

Exemplos:
- "Quanto recebemos em 2024?" -> SELECT SUM(pago) FROM a_receber_turbo WHERE EXTRACT(YEAR FROM data_vencimento) = 2024
- "Clientes inadimplentes" -> SELECT cliente_nome, SUM(nao_pago) FROM a_receber_turbo WHERE status = 'OVERDUE' GROUP BY cliente_nome
- "Top 5 clientes" -> SELECT cliente_nome, SUM(pago) FROM a_receber_turbo GROUP BY cliente_nome ORDER BY SUM(pago) DESC LIMIT 5

SQL:
"""
        
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Você é um especialista em SQL para sistemas financeiros. Retorne apenas o código SQL, sem explicações."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=500,
            temperature=0.1
        )
        
        sql_query = response.choices[0].message.content.strip()
        # Remover possíveis marcadores de código
        sql_query = sql_query.replace('```sql', '').replace('```', '').strip()
        
        return sql_query, None
        
    except Exception as e:
        return None, f"Erro ao consultar ChatGPT: {str(e)}"

def executar_consulta_chatgpt(mensagem_usuario):
    """Executar consulta interpretada pelo ChatGPT"""
    if not PSYCOPG2_AVAILABLE:
        return jsonify({
            'response': '❌ Módulo de banco de dados não disponível.',
            'type': 'error'
        })
    
    # Interpretar consulta com ChatGPT
    sql_query, erro = interpretar_consulta_com_chatgpt(mensagem_usuario)
    
    if erro:
        return jsonify({
            'response': f'🤖 {erro}\n\n💡 Usando interpretação básica...',
            'type': 'warning'
        })
    
    if not sql_query:
        return jsonify({
            'response': '❌ Não foi possível interpretar sua consulta.',
            'type': 'error'
        })
    
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({
                'response': '❌ Não foi possível conectar ao banco de dados.',
                'type': 'error'
            })
            
        from psycopg2.extras import RealDictCursor
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Executar query gerada pelo ChatGPT
        cursor.execute(sql_query)
        resultados = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        # Formatar resposta
        if not resultados:
            response = "❌ Nenhum resultado encontrado para sua consulta."
        else:
            response = "🤖 **Consulta interpretada pelo ChatGPT:**\n\n"
            
            # Formatar resultados de forma inteligente
            if len(resultados) == 1 and len(resultados[0]) == 1:
                # Resultado único (ex: soma, contagem)
                valor = list(resultados[0].values())[0]
                if isinstance(valor, (int, float)):
                    response += f"💰 **Resultado**: R$ {float(valor):,.2f}\n"
                else:
                    response += f"📊 **Resultado**: {valor}\n"
            else:
                # Múltiplos resultados
                for i, row in enumerate(resultados[:10], 1):  # Limitar a 10 resultados
                    response += f"{i}. "
                    for key, value in row.items():
                        if isinstance(value, (int, float)) and 'total' in key.lower() or 'pago' in key.lower() or 'valor' in key.lower():
                            response += f"**{key}**: R$ {float(value):,.2f} "
                        else:
                            response += f"**{key}**: {value} "
                    response += "\n"
                
                if len(resultados) > 10:
                    response += f"\n... e mais {len(resultados) - 10} resultados\n"
            
            response += f"\n🔍 **Query executada**: `{sql_query}`"
        
        return jsonify({
            'response': response,
            'type': 'success',
            'sql_query': sql_query,
            'data': [dict(row) for row in resultados]
        })
        
    except Exception as e:
        return jsonify({
            'response': f'❌ Erro ao executar consulta: {str(e)}\n\n🔍 **Query**: `{sql_query}`',
            'type': 'error'
        })

# Rota principal - página de consulta
@app.route('/')
def index():
    """Rota principal - Redireciona para TurboX Dashboard"""
    return render_template('turbox.html')

@app.route('/health')
def health_check():
    """Rota de healthcheck para Railway"""
    return {'status': 'healthy', 'message': 'API ContaAzul está funcionando!'}, 200

@app.route('/sin')
def sin_module():
    """Módulo SIN - Sistema Integrado ClickUp + Conta Azul"""
    return render_template('index.html')

@app.route('/turbochat')
def turbochat():
    """TurboChat - Interface de Chat para consultas"""
    return render_template('turbochat.html')

# Rota para verificar a conexão com o banco de dados
@app.route('/check-db')
def check_db():
    import sys
    print("=== DEBUG: Endpoint /check-db chamado ===", file=sys.stderr)
    
    # Verificar se psycopg2 está disponível
    if not PSYCOPG2_AVAILABLE:
        return jsonify({
            'status': 'error', 
            'message': 'O módulo psycopg2 não está instalado. Por favor, instale-o com: pip install psycopg2-binary'
        }), 500
    
    # Verificar variáveis de ambiente
    database_url = os.environ.get('DATABASE_URL')
    pg_vars = {
        'PG_HOST': os.environ.get('PG_HOST'),
        'PG_DBNAME': os.environ.get('PG_DBNAME'),
        'PG_USER': os.environ.get('PG_USER'),
        'PG_PASSWORD': os.environ.get('PG_PASSWORD')
    }
    
    if not database_url and not all(pg_vars.values()):
        missing_vars = [k for k, v in pg_vars.items() if not v] if not database_url else []
        return jsonify({
            'status': 'error',
            'message': f'Variáveis de ambiente do banco não configuradas. Configure DATABASE_URL ou as variáveis: {", ".join(missing_vars)}',
            'config_needed': True
        }), 500
        
    try:
        conn = get_db_connection()
        if conn:
            conn.close()
            print("=== DEBUG: Conexão com banco bem-sucedida ===", file=sys.stderr)
            return jsonify({'status': 'success', 'message': 'Conexão com o banco de dados estabelecida com sucesso!'})
        else:
            print("=== DEBUG: Falha na conexão com banco ===", file=sys.stderr)
            return jsonify({'status': 'error', 'message': 'Não foi possível conectar ao banco de dados. Verifique as credenciais.'}), 500
    except Exception as e:
        print(f"=== DEBUG: Erro na conexão: {str(e)} ===", file=sys.stderr)
        return jsonify({'status': 'error', 'message': f'Erro ao verificar conexão: {str(e)}'}), 500

@app.route('/test-post', methods=['POST'])
def test_post():
    import sys
    print("=== DEBUG: Endpoint /test-post chamado ===", file=sys.stderr)
    print(f"=== DEBUG: request.form = {request.form} ===", file=sys.stderr)
    print(f"=== DEBUG: request.method = {request.method} ===", file=sys.stderr)
    return jsonify({'status': 'success', 'form_data': dict(request.form)})

# Rota para buscar dados por CNPJ
@app.route('/buscar', methods=['POST'])
def buscar():
    import sys
    print("=== DEBUG: Endpoint /buscar chamado ===", file=sys.stderr)
    print(f"=== DEBUG: request.form = {request.form} ===", file=sys.stderr)
    
    cnpj = request.form.get('cnpj')
    print(f"=== DEBUG: CNPJ recebido: {cnpj} ===", file=sys.stderr)
    
    if not cnpj:
        print("=== DEBUG: CNPJ não fornecido ===", file=sys.stderr)
        return jsonify({'error': 'CNPJ é obrigatório'}), 400
    
    if not PSYCOPG2_AVAILABLE:
        return jsonify({
            'error': 'O módulo psycopg2 não está instalado. Por favor, instale-o com: pip install psycopg2-binary'
        }), 500
    
    # Verificar se o banco está configurado
    database_url = os.environ.get('DATABASE_URL')
    pg_vars = [os.environ.get('PG_HOST'), os.environ.get('PG_DBNAME'), os.environ.get('PG_USER'), os.environ.get('PG_PASSWORD')]
    
    if not database_url and not all(pg_vars):
        return jsonify({
            'error': '❌ Banco de dados não configurado no Railway. Configure as variáveis DATABASE_URL ou PG_HOST, PG_DBNAME, PG_USER, PG_PASSWORD.',
            'demo_mode': True,
            'message': 'Para configurar o banco, acesse o painel do Railway e adicione um banco PostgreSQL.'
        }), 500
    
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': '❌ Não foi possível conectar ao banco de dados. Verifique as credenciais.'}), 500
            
        cursor = conn.cursor()
        
        # Usar RealDictCursor para facilitar o manuseio dos dados
        from psycopg2.extras import RealDictCursor
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Primeiro, verificar se o cliente existe
        cursor.execute("""
        SELECT c.nome, c.cnpj,
               COUNT(a.id) as total_faturas,
               SUM(a.total) as total_geral,
               SUM(a.pago) as total_pago,
               SUM(a.nao_pago) as total_pendente
        FROM clientes_turbo c
        LEFT JOIN a_receber_turbo a ON c.nome = a.cliente_nome
        WHERE c.cnpj = %s
        GROUP BY c.nome, c.cnpj
        """, (cnpj,))
        
        cliente_info = cursor.fetchone()
        
        if not cliente_info or not cliente_info['nome']:
            cursor.close()
            conn.close()
            print(f"DEBUG: Cliente com CNPJ {cnpj} não encontrado")
            return jsonify({'message': f'Cliente com CNPJ {cnpj} não encontrado na base de dados.', 'cliente_existe': False})
        
        print(f"DEBUG: Cliente encontrado: {cliente_info['nome']}")
        
        # Consulta para buscar TODO o histórico de contas a receber pelo CNPJ do cliente
        # Incluindo: pagas, pendentes, vencidas e futuras
        cursor.execute("""
        SELECT a.id, a.status, a.total, a.descricao, a.data_vencimento, 
               a.nao_pago, a.pago, a.data_criacao, a.data_alteracao, 
               a.cliente_id, a.cliente_nome, a.link_pagamento,
               a.status_clickup,
               ck.responsavel, ck.segmento, ck.cluster, ck.status_conta, 
               ck.atividade, ck.telefone as telefone_clickup,
               ltv.total_pago as ltv_total,
               ltv.total_faturas,
               ltv.valor_inadimplente_total,
               CASE 
                   WHEN a.nao_pago = 0 THEN 'pago'
                   WHEN a.nao_pago > 0 AND a.data_vencimento < CURRENT_DATE THEN 'vencido'
                   WHEN a.nao_pago > 0 AND a.data_vencimento = CURRENT_DATE THEN 'vence_hoje'
                   WHEN a.nao_pago > 0 AND a.data_vencimento > CURRENT_DATE THEN 'futuro'
                   ELSE 'indefinido'
               END as status_cobranca,
               CASE 
                   WHEN a.nao_pago > 0 AND a.data_vencimento < CURRENT_DATE THEN 1  -- Vencidos primeiro
                   WHEN a.nao_pago > 0 AND a.data_vencimento = CURRENT_DATE THEN 2   -- Vence hoje
                   WHEN a.nao_pago > 0 AND a.data_vencimento > CURRENT_DATE THEN 3   -- Futuros
                   WHEN a.nao_pago = 0 THEN 4                                        -- Pagos por último
                   ELSE 5
               END as ordem_prioridade
        FROM a_receber_turbo a
        JOIN clientes_turbo c ON a.cliente_nome = c.nome
        LEFT JOIN (
            SELECT DISTINCT ON (cnpj) cnpj, responsavel, segmento, cluster, status_conta, atividade, telefone
            FROM clientes_clickup
            ORDER BY cnpj, id DESC
        ) ck ON c.cnpj = ck.cnpj
        LEFT JOIN (
            SELECT cliente_nome,
                   SUM(pago) as total_pago,
                   COUNT(*) as total_faturas,
                   SUM(CASE WHEN nao_pago > 0 AND data_vencimento < CURRENT_DATE THEN nao_pago ELSE 0 END) as valor_inadimplente_total
            FROM a_receber_turbo
            GROUP BY cliente_nome
        ) ltv ON a.cliente_nome = ltv.cliente_nome
        WHERE c.cnpj = %s
        ORDER BY ordem_prioridade, a.data_vencimento DESC
        """, (cnpj,))
        
        # Converter resultados para dicionário (usando RealDictCursor)
        rows = cursor.fetchall()
        result = []
        
        print(f"DEBUG: Encontrados {len(rows)} registros pendentes para CNPJ {cnpj}")
        
        # Se não há registros pendentes, mas o cliente existe, retornar informação
        if not rows:
            total_faturas = cliente_info['total_faturas'] or 0
            total_pago = float(cliente_info['total_pago'] or 0)
            total_pendente = float(cliente_info['total_pendente'] or 0)
            
            # Buscar informações do ClickUp mesmo sem faturas vencidas
            cursor.execute("""
            SELECT DISTINCT ck.responsavel, ck.segmento, ck.cluster, ck.status_conta, 
                   ck.atividade, ck.telefone as telefone_clickup,
                   ltv.total_pago as ltv_total,
                   ltv.total_faturas,
                   ltv.valor_inadimplente_total
            FROM clientes_turbo c
            LEFT JOIN (
                SELECT DISTINCT ON (cnpj) cnpj, responsavel, segmento, cluster, status_conta, atividade, telefone
                FROM clientes_clickup
                ORDER BY cnpj, id DESC
            ) ck ON c.cnpj = ck.cnpj
            LEFT JOIN (
                SELECT cliente_nome,
                       SUM(pago) as total_pago,
                       COUNT(*) as total_faturas,
                       SUM(CASE WHEN nao_pago > 0 AND data_vencimento < CURRENT_DATE THEN nao_pago ELSE 0 END) as valor_inadimplente_total
                FROM a_receber_turbo
                GROUP BY cliente_nome
            ) ltv ON c.nome = ltv.cliente_nome
            WHERE c.cnpj = %s
            """, (cnpj,))
            
            clickup_data = cursor.fetchone()
            
            cursor.close()
            conn.close()
            
            response_data = {
                'message': f'Cliente {cliente_info["nome"]} encontrado, mas não possui faturas vencidas.',
                'cliente_existe': True,
                'cliente_nome': cliente_info['nome'],
                'total_faturas': total_faturas,
                'total_pago': total_pago,
                'total_pendente': total_pendente,
                'faturas_vencidas': 0
            }
            
            # Adicionar informações do ClickUp se disponível
            if clickup_data:
                response_data['clickup'] = {
                    'responsavel': clickup_data['responsavel'],
                    'segmento': clickup_data['segmento'],
                    'cluster': clickup_data['cluster'],
                    'status_conta': clickup_data['status_conta'],
                    'atividade': clickup_data['atividade'],
                    'telefone': clickup_data['telefone_clickup']
                }
                response_data['ltv'] = {
                    'total_pago': float(clickup_data['ltv_total']) if clickup_data['ltv_total'] else 0,
                    'total_faturas': clickup_data['total_faturas'] if clickup_data['total_faturas'] else 0,
                    'valor_inadimplente_total': float(clickup_data['valor_inadimplente_total']) if clickup_data['valor_inadimplente_total'] else 0
                }
            
            return jsonify(response_data)
        
        for row in rows:
            # RealDictCursor já retorna um dict-like object
            row_dict = dict(row)
            # Tratar valores None para evitar erros de formatação
            for key, value in row_dict.items():
                if value is None:
                    row_dict[key] = None
                elif isinstance(value, (int, float)) and key in ['ltv_total', 'total_faturas', 'valor_inadimplente_total']:
                    row_dict[key] = float(value) if value is not None else 0.0
            
            # Debug: imprimir dados do ClickUp para verificação
            print(f"DEBUG ClickUp para {row_dict.get('cliente_nome')}: responsavel={row_dict.get('responsavel')}, segmento={row_dict.get('segmento')}, cluster={row_dict.get('cluster')}, status_conta={row_dict.get('status_conta')}")
            
            result.append(row_dict)
        
        print(f"DEBUG: Resultado processado: {len(result)} registros")
        
        # Fechar conexão
        cursor.close()
        conn.close()
        
        return jsonify(result)
    
    except Exception as e:
        app.logger.error(f"Erro ao buscar por CNPJ: {str(e)}\n{traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

# Rota alternativa para buscar por nome do cliente
@app.route('/buscar_por_nome', methods=['POST'])
def buscar_por_nome():
    nome = request.form.get('nome')
    
    if not nome:
        return jsonify({'error': 'Nome não fornecido'}), 400
    
    if not PSYCOPG2_AVAILABLE:
        return jsonify({
            'error': 'O módulo psycopg2 não está instalado. Por favor, instale-o com: pip install psycopg2-binary'
        }), 500
    
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Não foi possível conectar ao banco de dados'}), 500
            
        # Usar RealDictCursor para facilitar o manuseio dos dados
        from psycopg2.extras import RealDictCursor
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Consulta para buscar contas a receber pelo nome do cliente
        # Mostrando registros com saldo pendente (nao_pago > 0)
        # Usando status_clickup diretamente da tabela a_receber_turbo
        cursor.execute("""
        SELECT DISTINCT a.id, a.status, a.total, a.descricao, a.data_vencimento, 
               a.nao_pago, a.pago, a.data_criacao, a.data_alteracao, 
               a.cliente_id, a.cliente_nome, a.link_pagamento,
               a.status_clickup,
               ck.responsavel, ck.segmento, ck.cluster, ck.status_conta, 
               ck.atividade, ck.telefone as telefone_clickup,
               ltv.total_pago as ltv_total,
               ltv.total_faturas,
               ltv.valor_inadimplente_total
        FROM a_receber_turbo a
        LEFT JOIN clientes_turbo c ON a.cliente_nome = c.nome
        LEFT JOIN (
            SELECT DISTINCT ON (cnpj) cnpj, responsavel, segmento, cluster, status_conta, atividade, telefone
            FROM clientes_clickup
            ORDER BY cnpj, id DESC
        ) ck ON c.cnpj = ck.cnpj
        LEFT JOIN (
            SELECT cliente_nome,
                   SUM(pago) as total_pago,
                   COUNT(*) as total_faturas,
                   SUM(CASE WHEN nao_pago > 0 AND data_vencimento < CURRENT_DATE THEN nao_pago ELSE 0 END) as valor_inadimplente_total
            FROM a_receber_turbo
            GROUP BY cliente_nome
        ) ltv ON a.cliente_nome = ltv.cliente_nome
        WHERE a.cliente_nome ILIKE %s
          AND a.nao_pago > 0
          AND a.data_vencimento <= CURRENT_DATE
        ORDER BY a.data_vencimento DESC
        """, (f'%{nome}%',))
        
        # Converter resultados para dicionário (usando RealDictCursor)
        rows = cursor.fetchall()
        result = []
        
        print(f"DEBUG: Encontrados {len(rows)} registros para nome {nome}")
        
        for row in rows:
            # RealDictCursor já retorna um dict-like object
            row_dict = dict(row)
            # Tratar valores None para evitar erros de formatação
            for key, value in row_dict.items():
                if value is None:
                    row_dict[key] = None
                elif isinstance(value, (int, float)) and key in ['ltv_total', 'total_faturas', 'valor_inadimplente_total']:
                    row_dict[key] = float(value) if value is not None else 0.0
            
            # Debug: imprimir dados do ClickUp para verificação
            print(f"DEBUG ClickUp para {row_dict.get('cliente_nome')}: responsavel={row_dict.get('responsavel')}, segmento={row_dict.get('segmento')}, cluster={row_dict.get('cluster')}, status_conta={row_dict.get('status_conta')}")
            
            result.append(row_dict)
        
        # Fechar conexão
        cursor.close()
        conn.close()
        
        return jsonify(result)
    
    except Exception as e:
        app.logger.error(f"Erro ao buscar por nome: {str(e)}\n{traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

# Rota para listar todos os clientes
@app.route('/listar-clientes', methods=['GET'])
def listar_clientes():
    import sys
    print("=== DEBUG: Endpoint /listar-clientes chamado ===", file=sys.stderr)
    
    if not PSYCOPG2_AVAILABLE:
        return jsonify({
            'error': 'O módulo psycopg2 não está instalado. Por favor, instale-o com: pip install psycopg2-binary'
        }), 500
    
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Não foi possível conectar ao banco de dados'}), 500
            
        # Usar RealDictCursor para facilitar o manuseio dos dados
        from psycopg2.extras import RealDictCursor
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Consulta para buscar todos os clientes únicos com informações do ClickUp
        cursor.execute("""
        SELECT DISTINCT c.nome, c.cnpj,
               ck.responsavel, ck.segmento, ck.cluster, ck.status_conta, 
               ck.atividade, ck.telefone as telefone_clickup,
               a.status_clickup,
               CASE 
                   WHEN COUNT(a.id) FILTER (WHERE a.nao_pago > 0 AND a.data_vencimento <= CURRENT_DATE) > 0 THEN true
                   ELSE false
               END as tem_pendencias
        FROM clientes_turbo c
        LEFT JOIN clientes_clickup ck ON c.cnpj = ck.cnpj
        LEFT JOIN a_receber_turbo a ON c.nome = a.cliente_nome
        GROUP BY c.nome, c.cnpj, ck.responsavel, ck.segmento, ck.cluster, ck.status_conta, ck.atividade, ck.telefone, a.status_clickup
        ORDER BY c.nome
        """)
        
        # Converter resultados para dicionário
        rows = cursor.fetchall()
        result = []
        
        print(f"DEBUG: Encontrados {len(rows)} clientes")
        
        for row in rows:
            row_dict = dict(row)
            # Tratar valores None
            for key, value in row_dict.items():
                if value is None:
                    row_dict[key] = None
            
            result.append(row_dict)
        
        # Fechar conexão
        cursor.close()
        conn.close()
        
        return jsonify(result)
    
    except Exception as e:
        app.logger.error(f"Erro ao listar clientes: {str(e)}\n{traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

# Rota para TurboChat - processar mensagens do chat
@app.route('/turbochat/message', methods=['POST'])
def turbochat_message():
    import sys
    print("=== DEBUG: Endpoint /turbochat/message chamado ===", file=sys.stderr)
    
    data = request.get_json()
    message_original = data.get('message', '').strip()
    message = message_original.lower()
    
    if not message:
        return jsonify({'error': 'Mensagem é obrigatória'}), 400
    
    # Processar diferentes tipos de consulta baseado na mensagem
    try:
        # Detectar CNPJ primeiro (prioridade alta)
        import re
        cnpj_match = re.search(r'\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}|\d{14}', message)
        if cnpj_match:
            cnpj = re.sub(r'\D', '', cnpj_match.group())
            return buscar_por_cnpj_chat(cnpj)
        
        # Tentar interpretar com ChatGPT primeiro (se disponível)
        if OPENAI_AVAILABLE and OPENAI_API_KEY:
            try:
                resultado_chatgpt = executar_consulta_chatgpt(message_original)
                resultado_json = resultado_chatgpt.get_json()
                
                # Se o ChatGPT retornou sucesso, usar sua resposta
                if resultado_json.get('type') == 'success':
                    return resultado_chatgpt
                # Se retornou warning, continuar com interpretação básica
                elif resultado_json.get('type') == 'warning':
                    pass  # Continua para interpretação básica
            except Exception as e:
                print(f"Erro ChatGPT: {e}", file=sys.stderr)
                # Em caso de erro, continuar com interpretação básica
                pass
        
        # Fallback: Interpretação básica (sistema atual)
        # Consultas analíticas sobre receitas e valores
        if any(word in message for word in ['quanto', 'valor', 'total', 'receita', 'recebemos', 'arrecadamos']):
            return processar_consulta_analitica(message)
        
        # Consultas sobre clientes específicos (ranking, comparações)
        elif any(word in message for word in ['cliente que mais', 'maior cliente', 'melhor cliente', 'ranking', 'top']):
            return processar_consulta_ranking(message)
        
        # Consultas sobre status e inadimplência
        elif any(word in message for word in ['inadimplente', 'vencido', 'pendente', 'atraso', 'devendo']):
            return processar_consulta_inadimplencia(message)
        
        # Listar todos os clientes (verificar ANTES de buscar por nome)
        elif any(word in message for word in ['listar', 'todos', 'lista']) and 'cliente' in message:
            return listar_clientes_chat()
        
        # Buscar por nome de cliente
        elif any(word in message for word in ['cliente', 'empresa', 'buscar', 'procurar']):
            # Extrair nome da mensagem (remover palavras de comando)
            nome_words = message.split()
            stop_words = ['cliente', 'empresa', 'buscar', 'procurar', 'por', 'o', 'a', 'da', 'do', 'de', 'listar', 'todos', 'lista']
            nome_parts = [word for word in nome_words if word not in stop_words and len(word) > 2]
            if nome_parts:
                nome = ' '.join(nome_parts)
                return buscar_por_nome_chat(nome)
        
        # Ajuda
        elif any(word in message for word in ['ajuda', 'help', 'como', 'usar']):
            chatgpt_status = "🤖 **ChatGPT**: Ativo - Faça perguntas em linguagem natural!" if (OPENAI_AVAILABLE and OPENAI_API_KEY) else "🤖 **ChatGPT**: Não configurado"
            return jsonify({
                'response': 'Olá! Eu sou o TurboChat Inteligente! 🤖\n\n' +
                           f'{chatgpt_status}\n\n' +
                           '**📊 Consultas Analíticas:**\n' +
                           '• "Quanto recebemos em 2025?"\n' +
                           '• "Qual o total de receitas este mês?"\n' +
                           '• "Valor total pendente"\n\n' +
                           '**🏆 Rankings e Comparações:**\n' +
                           '• "Qual cliente mais nos pagou?"\n' +
                           '• "Top 5 clientes por receita"\n' +
                           '• "Ranking de inadimplentes"\n\n' +
                           '**🔍 Consultas Tradicionais:**\n' +
                           '• Digite o CNPJ do cliente\n' +
                           '• "Buscar cliente [nome]"\n' +
                           '• "Listar todos os clientes"\n\n' +
                           '**⚠️ Status e Inadimplência:**\n' +
                           '• "Clientes inadimplentes"\n' +
                           '• "Faturas vencidas hoje"\n\n' +
                           '💡 **Com ChatGPT ativo, você pode fazer perguntas complexas em linguagem natural!**',
                'type': 'help'
            })
        
        # Resposta padrão
        else:
            chatgpt_status = "🤖 **ChatGPT**: Ativo" if (OPENAI_AVAILABLE and OPENAI_API_KEY) else "🤖 **ChatGPT**: Não configurado"
            return jsonify({
                'response': f'Não entendi sua solicitação. Digite "ajuda" para ver todos os comandos disponíveis! 🤖\n\n{chatgpt_status}\n\n💡 **Dica**: Com ChatGPT ativo, você pode fazer perguntas em linguagem natural!',
                'type': 'error'
            })
            
    except Exception as e:
        app.logger.error(f"Erro no TurboChat: {str(e)}\n{traceback.format_exc()}")
        return jsonify({'error': f'Erro interno: {str(e)}'}), 500

def resumir_atividade(atividade):
    """Resumir a atividade do cliente para exibição no chat"""
    if not atividade or len(atividade.strip()) == 0:
        return None
    
    # Limitar o tamanho e extrair informações principais
    atividade = atividade.strip()
    
    # Se a atividade for muito longa, pegar apenas os primeiros 200 caracteres
    if len(atividade) > 200:
        # Tentar cortar em uma frase completa
        resumo = atividade[:200]
        ultimo_ponto = resumo.rfind('.')
        ultimo_pipe = resumo.rfind('|')
        
        if ultimo_ponto > 100:  # Se há um ponto após 100 caracteres
            resumo = resumo[:ultimo_ponto + 1]
        elif ultimo_pipe > 100:  # Se há um pipe após 100 caracteres
            resumo = resumo[:ultimo_pipe]
        
        resumo += "..."
    else:
        resumo = atividade
    
    # Extrair informações específicas se disponíveis
    info_extras = []
    
    # Procurar por status
    if "Status:" in atividade:
        status_match = atividade.split("Status:")[1].split("\n")[0].split("|")[0].strip()
        if status_match:
            info_extras.append(f"Status: {status_match}")
    
    # Procurar por relação com cliente
    if "Relação com o cliente:" in atividade:
        relacao_match = atividade.split("Relação com o cliente:")[1].split("\n")[0].split("|")[0].strip()
        if relacao_match and relacao_match != "-":
            info_extras.append(f"Relação: {relacao_match}/10")
    
    # Combinar resumo com informações extras
    if info_extras:
        return f"{resumo}\n📊 {' | '.join(info_extras)}"
    
    return resumo

def processar_consulta_analitica(message):
    """Processar consultas analíticas sobre receitas e valores"""
    if not PSYCOPG2_AVAILABLE:
        return jsonify({
            'response': '❌ Módulo de banco de dados não disponível.',
            'type': 'error'
        })
    
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({
                'response': '❌ Não foi possível conectar ao banco de dados.',
                'type': 'error'
            })
            
        from psycopg2.extras import RealDictCursor
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Detectar período na mensagem
        import re
        from datetime import datetime, date
        
        ano_match = re.search(r'\b(20\d{2})\b', message)
        mes_atual = 'mês' in message or 'mes' in message
        ano_atual = 'ano' in message and not ano_match
        
        response = "📊 **Análise Financeira**\n\n"
        
        if ano_match:
            # Consulta por ano específico
            ano = ano_match.group(1)
            cursor.execute("""
            SELECT 
                SUM(pago) as total_recebido,
                SUM(nao_pago) as total_pendente,
                SUM(total) as total_geral,
                COUNT(*) as total_faturas,
                COUNT(CASE WHEN nao_pago = 0 THEN 1 END) as faturas_pagas,
                COUNT(CASE WHEN nao_pago > 0 THEN 1 END) as faturas_pendentes
            FROM a_receber_turbo 
            WHERE EXTRACT(YEAR FROM data_vencimento) = %s
            """, (ano,))
            
            resultado = cursor.fetchone()
            
            if resultado and resultado['total_geral']:
                total_recebido = float(resultado['total_recebido'] or 0)
                total_pendente = float(resultado['total_pendente'] or 0)
                total_geral = float(resultado['total_geral'] or 0)
                
                response += f"**📅 Ano {ano}:**\n"
                response += f"💰 **Total Recebido**: R$ {total_recebido:,.2f}\n"
                response += f"⏳ **Total Pendente**: R$ {total_pendente:,.2f}\n"
                response += f"📊 **Total Geral**: R$ {total_geral:,.2f}\n"
                response += f"📋 **Faturas**: {resultado['total_faturas']} ({resultado['faturas_pagas']} pagas, {resultado['faturas_pendentes']} pendentes)\n"
                
                if total_geral > 0:
                    percentual_recebido = (total_recebido / total_geral) * 100
                    response += f"📈 **Taxa de Recebimento**: {percentual_recebido:.1f}%\n"
            else:
                response += f"❌ Nenhum dado encontrado para o ano {ano}.\n"
                
        elif mes_atual:
            # Consulta do mês atual
            cursor.execute("""
            SELECT 
                SUM(pago) as total_recebido,
                SUM(nao_pago) as total_pendente,
                SUM(total) as total_geral,
                COUNT(*) as total_faturas,
                COUNT(CASE WHEN nao_pago = 0 THEN 1 END) as faturas_pagas,
                COUNT(CASE WHEN nao_pago > 0 THEN 1 END) as faturas_pendentes
            FROM a_receber_turbo 
            WHERE EXTRACT(YEAR FROM data_vencimento) = EXTRACT(YEAR FROM CURRENT_DATE)
            AND EXTRACT(MONTH FROM data_vencimento) = EXTRACT(MONTH FROM CURRENT_DATE)
            """)
            
            resultado = cursor.fetchone()
            
            if resultado and resultado['total_geral']:
                total_recebido = float(resultado['total_recebido'] or 0)
                total_pendente = float(resultado['total_pendente'] or 0)
                total_geral = float(resultado['total_geral'] or 0)
                
                response += f"**📅 Mês Atual ({datetime.now().strftime('%B/%Y')}):**\n"
                response += f"💰 **Total Recebido**: R$ {total_recebido:,.2f}\n"
                response += f"⏳ **Total Pendente**: R$ {total_pendente:,.2f}\n"
                response += f"📊 **Total Geral**: R$ {total_geral:,.2f}\n"
                response += f"📋 **Faturas**: {resultado['total_faturas']} ({resultado['faturas_pagas']} pagas, {resultado['faturas_pendentes']} pendentes)\n"
                
                if total_geral > 0:
                    percentual_recebido = (total_recebido / total_geral) * 100
                    response += f"📈 **Taxa de Recebimento**: {percentual_recebido:.1f}%\n"
            else:
                response += f"❌ Nenhum dado encontrado para o mês atual.\n"
                
        else:
            # Consulta geral (todos os tempos)
            cursor.execute("""
            SELECT 
                SUM(pago) as total_recebido,
                SUM(nao_pago) as total_pendente,
                SUM(total) as total_geral,
                COUNT(*) as total_faturas,
                COUNT(CASE WHEN nao_pago = 0 THEN 1 END) as faturas_pagas,
                COUNT(CASE WHEN nao_pago > 0 THEN 1 END) as faturas_pendentes,
                COUNT(CASE WHEN nao_pago > 0 AND data_vencimento < CURRENT_DATE THEN 1 END) as faturas_vencidas
            FROM a_receber_turbo
            """)
            
            resultado = cursor.fetchone()
            
            if resultado and resultado['total_geral']:
                total_recebido = float(resultado['total_recebido'] or 0)
                total_pendente = float(resultado['total_pendente'] or 0)
                total_geral = float(resultado['total_geral'] or 0)
                
                response += f"**📅 Resumo Geral (Todos os Tempos):**\n"
                response += f"💰 **Total Recebido**: R$ {total_recebido:,.2f}\n"
                response += f"⏳ **Total Pendente**: R$ {total_pendente:,.2f}\n"
                response += f"📊 **Total Geral**: R$ {total_geral:,.2f}\n"
                response += f"📋 **Faturas**: {resultado['total_faturas']} ({resultado['faturas_pagas']} pagas, {resultado['faturas_pendentes']} pendentes)\n"
                response += f"⚠️ **Faturas Vencidas**: {resultado['faturas_vencidas']}\n"
                
                if total_geral > 0:
                    percentual_recebido = (total_recebido / total_geral) * 100
                    response += f"📈 **Taxa de Recebimento**: {percentual_recebido:.1f}%\n"
            else:
                response += f"❌ Nenhum dado encontrado no sistema.\n"
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'response': response,
            'type': 'success'
        })
        
    except Exception as e:
        return jsonify({
            'response': f'❌ Erro ao processar consulta analítica: {str(e)}',
            'type': 'error'
        })

def processar_consulta_ranking(message):
    """Processar consultas sobre rankings de clientes"""
    if not PSYCOPG2_AVAILABLE:
        return jsonify({
            'response': '❌ Módulo de banco de dados não disponível.',
            'type': 'error'
        })
    
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({
                'response': '❌ Não foi possível conectar ao banco de dados.',
                'type': 'error'
            })
            
        from psycopg2.extras import RealDictCursor
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Detectar tipo de ranking
        if any(word in message for word in ['mais', 'maior', 'melhor', 'top']):
            # Ranking por valor pago
            cursor.execute("""
            SELECT 
                c.nome,
                c.cnpj,
                SUM(a.pago) as total_pago,
                SUM(a.nao_pago) as total_pendente,
                COUNT(a.id) as total_faturas,
                ck.responsavel,
                ck.segmento
            FROM clientes_turbo c
            LEFT JOIN a_receber_turbo a ON c.nome = a.cliente_nome
            LEFT JOIN (
                SELECT DISTINCT ON (cnpj) cnpj, responsavel, segmento
                FROM clientes_clickup
                ORDER BY cnpj, id DESC
            ) ck ON c.cnpj = ck.cnpj
            GROUP BY c.nome, c.cnpj, ck.responsavel, ck.segmento
            HAVING SUM(a.pago) > 0
            ORDER BY total_pago DESC
            LIMIT 10
            """)
            
            resultados = cursor.fetchall()
            
            if resultados:
                response = "🏆 **Top 10 Clientes por Receita**\n\n"
                
                for i, cliente in enumerate(resultados, 1):
                    total_pago = float(cliente['total_pago'] or 0)
                    total_pendente = float(cliente['total_pendente'] or 0)
                    
                    emoji = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
                    
                    response += f"{emoji} **{cliente['nome']}**\n"
                    response += f"   💰 Total Pago: R$ {total_pago:,.2f}\n"
                    if total_pendente > 0:
                        response += f"   ⏳ Pendente: R$ {total_pendente:,.2f}\n"
                    response += f"   📋 Faturas: {cliente['total_faturas']}\n"
                    if cliente['responsavel']:
                        response += f"   👤 Responsável: {cliente['responsavel']}\n"
                    if cliente['segmento']:
                        response += f"   🏢 Segmento: {cliente['segmento']}\n"
                    response += "\n"
                    
                # Adicionar total geral
                total_geral = sum(float(c['total_pago'] or 0) for c in resultados)
                response += f"💎 **Total Geral (Top 10)**: R$ {total_geral:,.2f}"
            else:
                response = "❌ Nenhum cliente com receitas encontrado."
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'response': response,
            'type': 'success'
        })
        
    except Exception as e:
        return jsonify({
            'response': f'❌ Erro ao processar ranking: {str(e)}',
            'type': 'error'
        })

def processar_consulta_inadimplencia(message):
    """Processar consultas sobre inadimplência e status"""
    if not PSYCOPG2_AVAILABLE:
        return jsonify({
            'response': '❌ Módulo de banco de dados não disponível.',
            'type': 'error'
        })
    
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({
                'response': '❌ Não foi possível conectar ao banco de dados.',
                'type': 'error'
            })
            
        from psycopg2.extras import RealDictCursor
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Consulta de inadimplência
        cursor.execute("""
        SELECT 
            c.nome,
            c.cnpj,
            SUM(a.nao_pago) as total_inadimplente,
            COUNT(a.id) as faturas_vencidas,
            MIN(a.data_vencimento) as vencimento_mais_antigo,
            MAX(a.data_vencimento) as vencimento_mais_recente,
            ck.responsavel,
            ck.telefone,
            ck.segmento
        FROM clientes_turbo c
        JOIN a_receber_turbo a ON c.nome = a.cliente_nome
        LEFT JOIN (
            SELECT DISTINCT ON (cnpj) cnpj, responsavel, telefone, segmento
            FROM clientes_clickup
            ORDER BY cnpj, id DESC
        ) ck ON c.cnpj = ck.cnpj
        WHERE a.nao_pago > 0 AND a.data_vencimento < CURRENT_DATE
        GROUP BY c.nome, c.cnpj, ck.responsavel, ck.telefone, ck.segmento
        ORDER BY total_inadimplente DESC
        LIMIT 15
        """)
        
        resultados = cursor.fetchall()
        
        if resultados:
            response = "⚠️ **Clientes Inadimplentes**\n\n"
            
            total_inadimplencia = 0
            total_faturas_vencidas = 0
            
            for i, cliente in enumerate(resultados, 1):
                valor_inadimplente = float(cliente['total_inadimplente'] or 0)
                total_inadimplencia += valor_inadimplente
                total_faturas_vencidas += cliente['faturas_vencidas']
                
                # Calcular dias em atraso
                from datetime import date
                vencimento_antigo = cliente['vencimento_mais_antigo']
                dias_atraso = (date.today() - vencimento_antigo).days if vencimento_antigo else 0
                
                # Emoji baseado na gravidade
                if valor_inadimplente > 10000:
                    emoji = "🔴"  # Crítico
                elif valor_inadimplente > 5000:
                    emoji = "🟡"  # Alto
                else:
                    emoji = "🟠"  # Médio
                
                response += f"{emoji} **{cliente['nome']}**\n"
                response += f"   💸 Valor em Atraso: R$ {valor_inadimplente:,.2f}\n"
                response += f"   📋 Faturas Vencidas: {cliente['faturas_vencidas']}\n"
                response += f"   ⏰ Maior Atraso: {dias_atraso} dias\n"
                if cliente['responsavel']:
                    response += f"   👤 Responsável: {cliente['responsavel']}\n"
                if cliente['telefone']:
                    response += f"   📞 Telefone: {cliente['telefone']}\n"
                response += "\n"
            
            # Resumo geral
            response += f"📊 **Resumo da Inadimplência:**\n"
            response += f"💸 **Total em Atraso**: R$ {total_inadimplencia:,.2f}\n"
            response += f"📋 **Total de Faturas Vencidas**: {total_faturas_vencidas}\n"
            response += f"👥 **Clientes Inadimplentes**: {len(resultados)}\n\n"
            response += f"💡 *Digite o CNPJ de um cliente para ver detalhes específicos*"
        else:
            response = "🎉 **Parabéns!** Nenhum cliente inadimplente encontrado no momento."
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'response': response,
            'type': 'success' if not resultados else 'warning'
        })
        
    except Exception as e:
        return jsonify({
            'response': f'❌ Erro ao processar consulta de inadimplência: {str(e)}',
            'type': 'error'
        })

def buscar_por_cnpj_chat(cnpj):
    """Buscar dados por CNPJ para o chat"""
    if not PSYCOPG2_AVAILABLE:
        return jsonify({
            'response': '❌ Módulo de banco de dados não disponível.',
            'type': 'error'
        })
    
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({
                'response': '❌ Não foi possível conectar ao banco de dados.',
                'type': 'error'
            })
            
        from psycopg2.extras import RealDictCursor
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Primeiro, verificar se o cliente existe
        cursor.execute("""
        SELECT c.nome, c.cnpj,
               COUNT(a.id) as total_faturas,
               SUM(a.total) as total_geral,
               SUM(a.pago) as total_pago,
               SUM(a.nao_pago) as total_pendente,
               COUNT(CASE WHEN a.nao_pago > 0 AND a.data_vencimento <= CURRENT_DATE THEN 1 END) as faturas_vencidas
        FROM clientes_turbo c
        LEFT JOIN a_receber_turbo a ON c.nome = a.cliente_nome
        WHERE c.cnpj = %s
        GROUP BY c.nome, c.cnpj
        """, (cnpj,))
        
        cliente_info = cursor.fetchone()
        
        if not cliente_info or not cliente_info['nome']:
            cursor.close()
            conn.close()
            return jsonify({
                'response': f'❌ Cliente com CNPJ {cnpj} não encontrado na base de dados.',
                'type': 'not_found'
            })
        
        # Se o cliente existe, buscar TODO o histórico de cobranças
        cursor.execute("""
        SELECT a.id, a.status, a.total, a.descricao, a.data_vencimento, 
               a.nao_pago, a.pago, a.data_criacao, a.data_alteracao, 
               a.cliente_id, a.cliente_nome, a.link_pagamento,
               ck.responsavel, ck.segmento, ck.cluster, ck.status_conta, 
               ck.atividade, ck.telefone as telefone_clickup,
               a.status_clickup,
               ltv.total_pago as ltv_total,
               ltv.total_faturas,
               ltv.valor_inadimplente_total,
               CASE 
                   WHEN a.nao_pago = 0 THEN 'pago'
                   WHEN a.nao_pago > 0 AND a.data_vencimento < CURRENT_DATE THEN 'vencido'
                   WHEN a.nao_pago > 0 AND a.data_vencimento = CURRENT_DATE THEN 'vence_hoje'
                   WHEN a.nao_pago > 0 AND a.data_vencimento > CURRENT_DATE THEN 'futuro'
                   ELSE 'indefinido'
               END as status_cobranca,
               CASE 
                   WHEN a.nao_pago > 0 AND a.data_vencimento < CURRENT_DATE THEN 1  -- Vencidos primeiro
                   WHEN a.nao_pago > 0 AND a.data_vencimento = CURRENT_DATE THEN 2   -- Vence hoje
                   WHEN a.nao_pago > 0 AND a.data_vencimento > CURRENT_DATE THEN 3   -- Futuros
                   WHEN a.nao_pago = 0 THEN 4                                        -- Pagos por último
                   ELSE 5
               END as ordem_prioridade
        FROM a_receber_turbo a
        JOIN clientes_turbo c ON a.cliente_nome = c.nome
        LEFT JOIN (
            SELECT DISTINCT ON (cnpj) cnpj, responsavel, segmento, cluster, status_conta, atividade, telefone
            FROM clientes_clickup
            ORDER BY cnpj, id DESC
        ) ck ON c.cnpj = ck.cnpj
        LEFT JOIN (
            SELECT cliente_nome,
                   SUM(pago) as total_pago,
                   COUNT(*) as total_faturas,
                   SUM(CASE WHEN nao_pago > 0 AND data_vencimento < CURRENT_DATE THEN nao_pago ELSE 0 END) as valor_inadimplente_total
            FROM a_receber_turbo
            GROUP BY cliente_nome
        ) ltv ON a.cliente_nome = ltv.cliente_nome
        WHERE c.cnpj = %s
        ORDER BY ordem_prioridade, a.data_vencimento DESC
        """, (cnpj,))
        
        rows = cursor.fetchall()
        
        # Se não há registros pendentes, mas o cliente existe
        if not rows:
            cliente_nome = cliente_info['nome']
            total_faturas = cliente_info['total_faturas'] or 0
            total_pago = float(cliente_info['total_pago'] or 0)
            total_pendente = float(cliente_info['total_pendente'] or 0)
            
            # Buscar informações do ClickUp mesmo sem faturas vencidas
            cursor.execute("""
            SELECT DISTINCT ck.responsavel, ck.segmento, ck.cluster, ck.status_conta, 
                   ck.atividade, ck.telefone as telefone_clickup,
                   ltv.total_pago as ltv_total,
                   ltv.total_faturas,
                   ltv.valor_inadimplente_total
            FROM clientes_turbo c
            LEFT JOIN (
                SELECT DISTINCT ON (cnpj) cnpj, responsavel, segmento, cluster, status_conta, atividade, telefone
                FROM clientes_clickup
                ORDER BY cnpj, id DESC
            ) ck ON c.cnpj = ck.cnpj
            LEFT JOIN (
                SELECT cliente_nome,
                       SUM(pago) as total_pago,
                       COUNT(*) as total_faturas,
                       SUM(CASE WHEN nao_pago > 0 AND data_vencimento < CURRENT_DATE THEN nao_pago ELSE 0 END) as valor_inadimplente_total
                FROM a_receber_turbo
                GROUP BY cliente_nome
            ) ltv ON c.nome = ltv.cliente_nome
            WHERE c.cnpj = %s
            """, (cnpj,))
            
            clickup_data = cursor.fetchone()
            
            response = f"✅ **{cliente_nome}** (CNPJ: {cnpj})\n\n"
            
            if total_faturas == 0:
                response += "📋 Este cliente não possui faturas registradas no sistema.\n\n"
            elif total_pendente == 0:
                response += f"🎉 **Cliente em dia!** Todas as faturas estão quitadas.\n\n"
                response += f"💰 **Total Pago**: R$ {total_pago:,.2f}\n"
                response += f"📊 **Total de Faturas**: {total_faturas}\n\n"
            else:
                response += f"📋 **Total de Faturas**: {total_faturas}\n"
                response += f"💰 **Total Pago**: R$ {total_pago:,.2f}\n"
                response += f"⏳ **Saldo Pendente**: R$ {total_pendente:,.2f}\n"
                response += f"ℹ️ Não há faturas vencidas até hoje.\n\n"
            
            # Adicionar informações do ClickUp se disponível
            if clickup_data:
                # Informações de LTV se disponível
                if clickup_data['ltv_total'] is not None:
                    response += f"💎 **LTV Total Pago**: R$ {float(clickup_data['ltv_total']):,.2f}\n"
                if clickup_data['total_faturas'] is not None:
                    response += f"📊 **Total de Faturas (LTV)**: {clickup_data['total_faturas']}\n"
                if clickup_data['valor_inadimplente_total'] is not None:
                    response += f"⚠️ **Valor Inadimplente Total**: R$ {float(clickup_data['valor_inadimplente_total']):,.2f}\n"
                
                # Informações do ClickUp
                if clickup_data['responsavel']:
                    response += f"\n👤 **Responsável**: {clickup_data['responsavel']}\n"
                if clickup_data['segmento']:
                    response += f"🏢 **Segmento**: {clickup_data['segmento']}\n"
                if clickup_data['cluster']:
                    response += f"🎯 **Cluster**: {clickup_data['cluster']}\n"
                if clickup_data['status_conta']:
                    response += f"📊 **Status da Conta**: {clickup_data['status_conta']}\n"
                if clickup_data['atividade']:
                    response += f"🔄 **Atividade**: {clickup_data['atividade']}\n"
                if clickup_data['telefone_clickup']:
                    response += f"📞 **Telefone**: {clickup_data['telefone_clickup']}\n"
            
            cursor.close()
            conn.close()
            
            return jsonify({
                'response': response,
                'type': 'success'
            })
        
        cursor.close()
        conn.close()
        
        # Formatar resposta para chat com histórico completo categorizado
        cliente_nome = rows[0]['cliente_nome']
        
        # Categorizar faturas por status
        vencidas = [row for row in rows if row['status_cobranca'] == 'vencido']
        vence_hoje = [row for row in rows if row['status_cobranca'] == 'vence_hoje']
        futuras = [row for row in rows if row['status_cobranca'] == 'futuro']
        pagas = [row for row in rows if row['status_cobranca'] == 'pago']
        
        total_pendente = sum(float(row['nao_pago']) for row in rows if row['nao_pago'] > 0)
        total_pago = sum(float(row['pago']) for row in rows if row['pago'] > 0)
        
        response = f"📊 **{cliente_nome}** (CNPJ: {cnpj})\n\n"
        response += f"💰 **Total Pendente**: R$ {total_pendente:,.2f}\n"
        response += f"✅ **Total Pago**: R$ {total_pago:,.2f}\n"
        response += f"📋 **Total de Faturas**: {len(rows)}\n\n"
        
        # Informações de LTV se disponível
        if rows[0]['ltv_total'] is not None:
            response += f"💎 **LTV Total Pago**: R$ {float(rows[0]['ltv_total']):,.2f}\n"
        if rows[0]['total_faturas'] is not None:
            response += f"📊 **Total de Faturas (LTV)**: {rows[0]['total_faturas']}\n"
        if rows[0]['valor_inadimplente_total'] is not None:
            response += f"⚠️ **Valor Inadimplente Total**: R$ {float(rows[0]['valor_inadimplente_total']):,.2f}\n"
        response += "\n"
        
        # Informações do ClickUp se disponível
        if rows[0]['responsavel']:
            response += f"👤 **Responsável**: {rows[0]['responsavel']}\n"
        if rows[0]['segmento']:
            response += f"🏢 **Segmento**: {rows[0]['segmento']}\n"
        if rows[0]['status_clickup'] is not None:
            status_operacional = "🟢 Ativo" if rows[0]['status_clickup'] == 'ativo' else "🔴 Inativo"
            response += f"⚡ **Status Operacional**: {status_operacional}\n"
        if rows[0]['cluster']:
            response += f"📊 **Cluster**: {rows[0]['cluster']}\n"
        
        # Resumo da atividade se disponível
        if rows[0]['atividade']:
            resumo_atividade = resumir_atividade(rows[0]['atividade'])
            if resumo_atividade:
                response += f"\n📝 **Resumo da Atividade**:\n{resumo_atividade}\n"
        
        # Criar lista única de todas as faturas ordenada por data
        todas_faturas = []
        faturas_html = None  # Inicializar a variável
        
        # Adicionar faturas pendentes (vencidas, vence hoje, futuras)
        for row in vencidas + vence_hoje + futuras:
            todas_faturas.append({
                'id': row['id'],
                'data': row['data_vencimento'],
                'valor': float(row['nao_pago']) if row['nao_pago'] else 0.0,
                'status': row['status_cobranca'],
                'link_pagamento': row['link_pagamento'],
                'descricao': row['descricao'] or 'Cobrança',
                'tipo': 'pendente'
            })
        
        # Adicionar últimas 3 faturas pagas
        for row in pagas[:3]:
            todas_faturas.append({
                'id': row['id'],
                'data': row['data_vencimento'],
                'valor': float(row['pago']) if row['pago'] else 0.0,
                'status': 'pago',
                'link_pagamento': None,
                'descricao': row['descricao'] or 'Cobrança',
                'tipo': 'pago'
            })
        
        # Ordenar por data (mais antigas primeiro, faturas vencidas no topo)
        todas_faturas.sort(key=lambda x: (x['data'], x['status'] != 'vencido'))
        
        # Botão para visualizar faturas (sem exibir diretamente)
        if todas_faturas:
            # Resumo de faturas vencidas se houver
            if vencidas:
                total_vencido = sum(float(row['nao_pago']) for row in vencidas)
                response += f"\n⚠️ **ATENÇÃO**: {len(vencidas)} fatura(s) vencida(s) totalizando R$ {total_vencido:,.2f}\n\n"
            
            response += f"📋 **{len(todas_faturas)} faturas encontradas**\n\n"
            response += "🔍 Use o botão abaixo para visualizar as faturas\n\n"
            
            # Criar dados das faturas para JavaScript (oculto inicialmente)
            faturas_html = "<div class='faturas-content'>\n"
            faturas_html += "<h4>📋 Histórico de Faturas (ordenado por data)</h4>\n"
            
            for i, fatura in enumerate(todas_faturas[:10], 1):  # Mostrar até 10 faturas
                # Definir emoji e formatação baseado no status
                if fatura['status'] == 'vencido':
                    status_emoji = "🔴"
                    status_text = "<strong>VENCIDA</strong>"
                    valor_format = f"<strong>R$ {fatura['valor']:,.2f}</strong>"
                    row_class = "text-danger"
                elif fatura['status'] == 'vence_hoje':
                    status_emoji = "🟡"
                    status_text = "Vence Hoje"
                    valor_format = f"<strong>R$ {fatura['valor']:,.2f}</strong>"
                    row_class = "text-warning"
                elif fatura['status'] == 'futuro':
                    status_emoji = "🔵"
                    status_text = "Futuro"
                    valor_format = f"R$ {fatura['valor']:,.2f}"
                    row_class = "text-info"
                else:  # pago
                    status_emoji = "✅"
                    status_text = "Pago"
                    valor_format = f"R$ {fatura['valor']:,.2f}"
                    row_class = "text-success"
                
                # Formatação da linha da fatura sem link localhost
                faturas_html += f"<div class='fatura-item {row_class} mb-2 p-2 border rounded'>\n"
                faturas_html += f"  <div><strong>{i:2d}. {status_emoji} {status_text}</strong> | {valor_format}</div>\n"
                faturas_html += f"  <div class='text-muted'>📅 {fatura['data']} | 📝 {fatura['descricao'][:50]}{'...' if len(fatura['descricao']) > 50 else ''}</div>\n"
                
                # Adicionar link de pagamento se disponível
                if fatura['link_pagamento'] and fatura['tipo'] == 'pendente':
                    faturas_html += f"  <div class='mt-1'><a href='{fatura['link_pagamento']}' target='_blank' class='btn btn-sm btn-primary'>💳 Pagar Agora</a></div>\n"
                
                faturas_html += "</div>\n"
            
            # Mostrar resumo se há mais faturas
            total_faturas = len(rows)
            if total_faturas > 10:
                faturas_html += f"<div class='text-muted mt-2'>📊 <em>Mostrando 10 de {total_faturas} faturas totais</em></div>\n"
            
            faturas_html += "</div>\n"
            

        
        return jsonify({
            'response': response,
            'type': 'success',
            'data': [dict(row) for row in rows],
            'faturas_html': faturas_html if todas_faturas else None
        })
        
    except Exception as e:
        return jsonify({
            'response': f'❌ Erro ao buscar dados: {str(e)}',
            'type': 'error'
        })

@app.route('/fatura/<int:fatura_id>')
def detalhes_fatura(fatura_id):
    """Exibir detalhes de uma fatura específica"""
    if not PSYCOPG2_AVAILABLE:
        return render_template('index.html', erro='Módulo de banco de dados não disponível.')
    
    try:
        conn = get_db_connection()
        if not conn:
            return render_template('index.html', erro='Não foi possível conectar ao banco de dados.')
            
        from psycopg2.extras import RealDictCursor
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute("""
        SELECT a.id, a.status, a.total, a.descricao, a.data_vencimento, 
               a.nao_pago, a.pago, a.data_criacao, a.data_alteracao, 
               a.cliente_id, a.cliente_nome, a.link_pagamento,
               c.cnpj, c.telefone, c.email
        FROM a_receber_turbo a
        LEFT JOIN clientes_turbo c ON a.cliente_nome = c.nome
        WHERE a.id = %s
        """, (fatura_id,))
        
        fatura = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if not fatura:
            return render_template('index.html', erro='Fatura não encontrada.')
        
        return render_template('index.html', fatura_detalhes=dict(fatura))
        
    except Exception as e:
        return render_template('index.html', erro=f'Erro ao buscar fatura: {str(e)}')

def buscar_por_nome_chat(nome):
    """Buscar dados por nome para o chat"""
    if not PSYCOPG2_AVAILABLE:
        return jsonify({
            'response': '❌ Módulo de banco de dados não disponível.',
            'type': 'error'
        })
    
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({
                'response': '❌ Não foi possível conectar ao banco de dados.',
                'type': 'error'
            })
            
        from psycopg2.extras import RealDictCursor
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute("""
        SELECT DISTINCT a.id, a.status, a.total, a.descricao, a.data_vencimento, 
               a.nao_pago, a.pago, a.data_criacao, a.data_alteracao, 
               a.cliente_id, a.cliente_nome, a.link_pagamento,
               ck.responsavel, ck.segmento, ck.cluster, ck.status_conta, 
               ck.atividade, ck.telefone as telefone_clickup,
               a.status_clickup,
               ltv.total_pago as ltv_total,
               ltv.total_faturas,
               ltv.valor_inadimplente_total
        FROM a_receber_turbo a
        LEFT JOIN clientes_turbo c ON a.cliente_nome = c.nome
        LEFT JOIN (
            SELECT DISTINCT ON (cnpj) cnpj, responsavel, segmento, cluster, status_conta, atividade, telefone
            FROM clientes_clickup
            ORDER BY cnpj, id DESC
        ) ck ON c.cnpj = ck.cnpj
        LEFT JOIN (
            SELECT cliente_nome,
                   SUM(pago) as total_pago,
                   COUNT(*) as total_faturas,
                   SUM(CASE WHEN nao_pago > 0 AND data_vencimento < CURRENT_DATE THEN nao_pago ELSE 0 END) as valor_inadimplente_total
            FROM a_receber_turbo
            GROUP BY cliente_nome
        ) ltv ON a.cliente_nome = ltv.cliente_nome
        WHERE a.cliente_nome ILIKE %s
          AND a.nao_pago > 0
          AND a.data_vencimento <= CURRENT_DATE
        ORDER BY a.data_vencimento DESC
        """, (f'%{nome}%',))
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if not rows:
            return jsonify({
                'response': f'❌ Nenhum cliente encontrado com o nome "{nome}".',
                'type': 'not_found'
            })
        
        # Formatar resposta para chat
        cliente_nome = rows[0]['cliente_nome']
        total_pendente = sum(float(row['nao_pago']) for row in rows)
        
        response = f"📊 **{cliente_nome}**\n\n"
        response += f"💰 **Total Pendente**: R$ {total_pendente:,.2f}\n"
        response += f"📋 **Faturas em Aberto**: {len(rows)}\n\n"
        
        # Informações de LTV se disponível
        if rows[0]['ltv_total'] is not None:
            response += f"💎 **LTV Total Pago**: R$ {float(rows[0]['ltv_total']):,.2f}\n"
        if rows[0]['total_faturas'] is not None:
            response += f"📊 **Total de Faturas**: {rows[0]['total_faturas']}\n"
        if rows[0]['valor_inadimplente_total'] is not None:
            response += f"⚠️ **Valor Inadimplente Total**: R$ {float(rows[0]['valor_inadimplente_total']):,.2f}\n"
        response += "\n"
        
        # Informações do ClickUp se disponível
        if rows[0]['responsavel']:
            response += f"👤 **Responsável**: {rows[0]['responsavel']}\n"
        if rows[0]['segmento']:
            response += f"🏢 **Segmento**: {rows[0]['segmento']}\n"
        if rows[0]['status_clickup'] is not None:
            status_operacional = "🟢 Ativo" if rows[0]['status_clickup'] == 'ativo' else "🔴 Inativo"
            response += f"⚡ **Status Operacional**: {status_operacional}\n"
        
        # Resumo da atividade se disponível
        if rows[0]['atividade']:
            resumo_atividade = resumir_atividade(rows[0]['atividade'])
            if resumo_atividade:
                response += f"\n📝 **Resumo da Atividade**:\n{resumo_atividade}\n"
        
        response += "\n📋 **Faturas Vencidas**:\n"
        for i, row in enumerate(rows[:3]):  # Mostrar apenas as 3 primeiras
            link_pagamento = f" [💳 Pagar]({row['link_pagamento']})" if row['link_pagamento'] else ""
            response += f"• R$ {float(row['nao_pago']):,.2f} - Venc: {row['data_vencimento']}{link_pagamento}\n"
        
        if len(rows) > 3:
            response += f"... e mais {len(rows) - 3} faturas\n"
        
        return jsonify({
            'response': response,
            'type': 'success',
            'data': [dict(row) for row in rows]
        })
        
    except Exception as e:
        return jsonify({
            'response': f'❌ Erro ao buscar dados: {str(e)}',
            'type': 'error'
        })

def listar_clientes_chat():
    """Listar clientes para o chat"""
    if not PSYCOPG2_AVAILABLE:
        return jsonify({
            'response': '❌ Módulo de banco de dados não disponível.',
            'type': 'error'
        })
    
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({
                'response': '❌ Não foi possível conectar ao banco de dados.',
                'type': 'error'
            })
            
        from psycopg2.extras import RealDictCursor
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute("""
        SELECT DISTINCT c.nome, c.cnpj,
               ck.responsavel, ck.segmento, ck.cluster, ck.status_conta, 
               ck.atividade, ck.telefone as telefone_clickup,
               ltv.total_pago as ltv_total,
               ltv.total_faturas,
               ltv.valor_inadimplente_total,
               CASE 
                   WHEN COUNT(a.id) FILTER (WHERE a.nao_pago > 0 AND a.data_vencimento <= CURRENT_DATE) > 0 THEN true
                   ELSE false
               END as tem_pendencias,
               SUM(a.nao_pago) FILTER (WHERE a.nao_pago > 0 AND a.data_vencimento <= CURRENT_DATE) as total_pendente
        FROM clientes_turbo c
        LEFT JOIN (
            SELECT DISTINCT ON (cnpj) cnpj, responsavel, segmento, cluster, status_conta, atividade, telefone
            FROM clientes_clickup
            ORDER BY cnpj, id DESC
        ) ck ON c.cnpj = ck.cnpj
        LEFT JOIN a_receber_turbo a ON c.nome = a.cliente_nome
        LEFT JOIN (
            SELECT cliente_nome,
                   SUM(pago) as total_pago,
                   COUNT(*) as total_faturas,
                   SUM(CASE WHEN nao_pago > 0 AND data_vencimento < CURRENT_DATE THEN nao_pago ELSE 0 END) as valor_inadimplente_total
            FROM a_receber_turbo
            GROUP BY cliente_nome
        ) ltv ON c.nome = ltv.cliente_nome
        GROUP BY c.nome, c.cnpj, ck.responsavel, ck.segmento, ck.cluster, ck.status_conta, ck.atividade, ck.telefone, ltv.total_pago, ltv.total_faturas, ltv.valor_inadimplente_total
        HAVING COUNT(a.id) FILTER (WHERE a.nao_pago > 0 AND a.data_vencimento <= CURRENT_DATE) > 0
        ORDER BY total_pendente DESC
        LIMIT 10
        """)
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if not rows:
            return jsonify({
                'response': '❌ Nenhum cliente com pendências encontrado.',
                'type': 'not_found'
            })
        
        response = f"📋 **Top {len(rows)} Clientes com Pendências**\n\n"
        
        for i, row in enumerate(rows, 1):
            total_pendente = float(row['total_pendente']) if row['total_pendente'] else 0
            response += f"{i}. **{row['nome']}**\n"
            response += f"   💰 Pendente: R$ {total_pendente:,.2f}\n"
            if row['ltv_total'] is not None:
                response += f"   💎 LTV: R$ {float(row['ltv_total']):,.2f}\n"
            if row['responsavel']:
                response += f"   👤 {row['responsavel']}\n"
            if row['status_conta']:
                response += f"   ⚡ Status: {row['status_conta']}\n"
            # Resumo muito breve da atividade (apenas primeira linha)
            if row['atividade']:
                primeira_linha = row['atividade'].split('\n')[0].split('|')[0].strip()
                if primeira_linha and len(primeira_linha) > 10:
                    resumo_breve = primeira_linha[:80] + "..." if len(primeira_linha) > 80 else primeira_linha
                    response += f"   📝 {resumo_breve}\n"
            response += "\n"
        
        response += "💡 *Digite o CNPJ ou nome de um cliente para ver detalhes*"
        
        return jsonify({
            'response': response,
            'type': 'success',
            'data': [dict(row) for row in rows]
        })
        
    except Exception as e:
        return jsonify({
            'response': f'❌ Erro ao listar clientes: {str(e)}',
            'type': 'error'
        })

# Iniciar a aplicação
if __name__ == '__main__':
    # Obter a porta do ambiente (para compatibilidade com Railway/Heroku) ou usar 5000 como padrão
    port = int(os.environ.get("PORT", 5000))
    # Definir o modo de depuração com base no ambiente
    debug_mode = os.environ.get("FLASK_ENV") == "development"
    app.run(debug=debug_mode, host='0.0.0.0', port=port)