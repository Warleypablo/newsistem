# TurboZap - Módulo de Envio de Mensagens WhatsApp

## Descrição
O TurboZap é um módulo integrado ao sistema TurboX que facilita o envio automatizado de mensagens WhatsApp para clientes inadimplentes. O sistema utiliza a Evolution API para envio das mensagens e se conecta ao banco de dados PostgreSQL para buscar informações dos clientes.

## Funcionalidades

### 📱 Envio Automatizado de Mensagens
- Envio de mensagens personalizadas para clientes inadimplentes
- Suporte a diferentes períodos de inadimplência (D-3, D+0, D+1, D+7, D+14, D+21)
- Formatação automática de números de telefone
- Controle de taxa de envio com delays configuráveis

### 📊 Gestão de Clientes
- Busca automática de clientes por data de vencimento
- Filtro por dias de inadimplência
- Validação de dados de contato
- Logging detalhado de operações

### 🔧 Configuração Flexível
- Configuração via variáveis de ambiente
- Validação automática de credenciais
- Suporte a múltiplas instâncias da Evolution API
- Templates de mensagem personalizáveis

## Estrutura do Código

### Classes Principais

#### `TurboZapConfig`
Gerencia as configurações do sistema, incluindo:
- Credenciais do banco de dados
- Configurações da Evolution API
- Validação de variáveis de ambiente

#### `DatabaseManager`
Responsável pela conexão e operações com o banco de dados:
- Conexão segura com PostgreSQL
- Gerenciamento automático de conexões
- Tratamento de erros de banco

#### `WhatsAppSender`
Gerencia o envio de mensagens via Evolution API:
- Formatação de números de telefone
- Envio de mensagens com retry automático
- Controle de estatísticas de envio
- Logging detalhado de operações

#### `ClienteManager`
Gerencia a busca e filtro de clientes:
- Busca por data de vencimento
- Filtro por dias de inadimplência
- Validação de dados de contato

#### `MessageTemplates`
Gerencia os templates de mensagem:
- Templates para diferentes períodos
- Personalização de mensagens
- Descrições dos períodos de cobrança

#### `TurboZap`
Classe principal que orquestra todo o sistema:
- Inicialização de componentes
- Execução de campanhas de envio
- Relatórios de resultados

## Configuração

### Variáveis de Ambiente Necessárias

```bash
# Banco de Dados
DB_HOST=localhost
DB_PORT=5432
DB_NAME=turbodb
DB_USER=usuario
DB_PASSWORD=senha

# Evolution API
EVOLUTION_API_URL=https://sua-evolution-api.com
EVOLUTION_API_KEY=sua-chave-api
EVOLUTION_INSTANCE=sua-instancia
```

## Uso

### Execução via Linha de Comando

```bash
# Enviar mensagens para todos os períodos configurados
python turbozap.py

# Enviar mensagens para um período específico
python turbozap.py --periodo D+7

# Listar períodos disponíveis
python turbozap.py --help
```

### Integração com TurboX
O módulo pode ser integrado à interface web do TurboX para:
- Configuração de campanhas
- Monitoramento de envios
- Relatórios de resultados
- Gestão de templates

## Templates de Mensagem

O sistema inclui templates pré-configurados para diferentes estágios da cobrança:

- **D-3**: Lembrete amigável antes do vencimento
- **D+0**: Notificação no dia do vencimento
- **D+1**: Primeiro aviso de atraso
- **D+7**: Cobrança após uma semana
- **D+14**: Cobrança mais firme após duas semanas
- **D+21**: Último aviso antes de medidas legais

## Logging

O sistema gera logs detalhados em:
- **Arquivo**: `turbozap.log`
- **Console**: Saída padrão
- **Níveis**: INFO, WARNING, ERROR

## Segurança

- Todas as credenciais são gerenciadas via variáveis de ambiente
- Conexões seguras com o banco de dados
- Validação de dados de entrada
- Logs sem exposição de informações sensíveis

## Requisitos

- Python 3.7+
- PostgreSQL
- Evolution API configurada
- Bibliotecas: `psycopg2`, `requests`, `python-dotenv`

## Próximos Passos

1. Integração com a interface web do TurboX
2. Dashboard de monitoramento em tempo real
3. Relatórios avançados de performance
4. Suporte a múltiplos canais de comunicação
5. Templates dinâmicos baseados em dados do cliente