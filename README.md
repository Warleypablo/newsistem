# 🚀 Sistema de Integração ClickUp + Conta Azul com TurboChat Inteligente

Sistema web para integração e sincronização de dados entre ClickUp e Conta Azul, com interface para visualização de clientes, cobranças e status. Agora inclui o **TurboChat Inteligente** para consultas analíticas sobre contas a receber.

## 🤖 TurboChat Inteligente

O TurboChat agora responde perguntas inteligentes sobre suas finanças:

### 📊 Consultas Analíticas
- "Quanto recebemos em 2024?"
- "Total de receitas este mês"
- "Receita do ano atual"

### 🏆 Rankings e Comparações
- "Qual cliente mais nos pagou?"
- "Top 10 clientes"
- "Maiores pagadores"

### ⚠️ Análise de Inadimplência
- "Clientes inadimplentes"
- "Faturas vencidas"
- "Quem está em atraso?"

**Acesse:** `/turbochat` para usar o chat inteligente!

## 📁 Estrutura do Projeto

```
├── src/                    # Aplicação principal
│   ├── app.py             # Servidor Flask principal
│   └── templates/         # Templates HTML
│       └── index.html     # Interface principal
│
├── scripts/               # Scripts de integração
│   ├── clientes.py        # Integração de clientes
│   ├── contas_a_pagar.py  # Contas a pagar
│   ├── contas_a_receber.py # Contas a receber
│   ├── acess_token.py     # Gerenciamento de tokens
│   ├── automate.py        # Automação
│   └── 01/                # Scripts antigos/específicos
│
├── deploy/                # Arquivos de deploy
│   ├── Procfile           # Configuração Heroku/Render
│   ├── render.yaml        # Configuração Render.com
│   ├── app.json           # Configuração Heroku
│   └── deploy_*.ps1       # Scripts de deploy
│
├── docs/                  # Documentação
│   ├── README_DEPLOY.md   # Instruções de deploy
│   ├── INSTRUCOES_DEPLOY.md # Instruções detalhadas
│   └── PROXIMOS_PASSOS_GITHUB.md # Guia GitHub
│
├── tests/                 # Testes
│   ├── test_endpoint_direct.py
│   └── test_join.py
│
├── utils/                 # Utilitários
│   ├── check_db.py        # Verificação do banco
│   ├── init_db.py         # Inicialização do banco
│   ├── debug_agropedd.py  # Debug específico
│   └── planil.py          # Manipulação de planilhas
│
├── config/                # Configurações
│   └── .env.example       # Exemplo de variáveis de ambiente
│
├── requirements.txt       # Dependências Python
├── .gitignore            # Arquivos ignorados pelo Git
└── README.md             # Este arquivo
```

## 🗄️ Configuração do Banco de Dados

### ⚠️ Aviso: "Variáveis de ambiente do banco de dados não configuradas"

Se você está vendo este aviso, precisa configurar a conexão com o banco PostgreSQL:

#### Para Railway/Heroku (Produção):
1. Adicione um banco PostgreSQL no seu projeto
2. Configure a variável `DATABASE_URL` no painel
3. Acesse `/check-db` para verificar a conexão

#### Para Desenvolvimento Local:
1. Copie `.env.example` para `.env`
2. Configure suas variáveis do PostgreSQL:
   ```
   PG_HOST=localhost
   PG_DBNAME=turbo_db
   PG_USER=seu_usuario
   PG_PASSWORD=sua_senha
   PG_PORT=5432
   ```
3. Instale PostgreSQL localmente
4. Acesse `/check-db` para verificar

📖 **Documentação completa:** `CONFIGURAR_BANCO.md`

## 🚀 Como Executar

### Desenvolvimento Local

1. **Instalar dependências:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configurar variáveis de ambiente:**
   ```bash
   cp config/.env.example .env
   # Edite o arquivo .env com suas credenciais
   ```

3. **Executar aplicação:**
   ```bash
   cd src
   python app.py
   ```

4. **Acessar:** http://localhost:5000

### Deploy em Produção

Consulte os arquivos na pasta `docs/` para instruções detalhadas de deploy:

- **Render.com:** `docs/README_DEPLOY.md`
- **GitHub Setup:** `docs/PROXIMOS_PASSOS_GITHUB.md`
- **Instruções Completas:** `docs/INSTRUCOES_DEPLOY.md`

## 🔧 Funcionalidades

- **Lista de Clientes:** Visualização geral com filtros
- **Busca Específica:** Busca detalhada por CNPJ/Nome
- **Integração ClickUp:** Sincronização de dados
- **Integração Conta Azul:** Importação de dados financeiros
- **Interface Responsiva:** Design moderno e intuitivo

## 🛠️ Tecnologias

- **Backend:** Python + Flask
- **Frontend:** HTML + CSS + JavaScript
- **Banco de Dados:** PostgreSQL
- **Deploy:** Render.com / Heroku
- **APIs:** ClickUp API + Conta Azul API

## 📝 Scripts Disponíveis

### Utilitários
- `utils/check_db.py` - Verificar conexão com banco
- `utils/init_db.py` - Inicializar banco de dados

### Deploy
- `deploy/deploy_render.ps1` - Deploy automático Render.com
- `deploy/deploy_heroku.ps1` - Deploy automático Heroku

### Integração
- `scripts/clientes.py` - Sincronizar clientes
- `scripts/contas_a_receber.py` - Importar contas a receber

## 🔒 Configuração

Crie um arquivo `.env` na raiz baseado em `config/.env.example`:

```env
PG_HOST=localhost
PG_PORT=5432
PG_DBNAME=seu_banco
PG_USER=seu_usuario
PG_PASSWORD=sua_senha
DATABASE_URL=postgresql://user:pass@host:port/db
```

## 📚 Documentação

Toda a documentação está organizada na pasta `docs/`:

- **Deploy:** Instruções completas de implantação
- **API:** Documentação das integrações
- **Troubleshooting:** Soluções para problemas comuns

## 🤝 Contribuição

1. Faça um fork do projeto
2. Crie uma branch para sua feature
3. Commit suas mudanças
4. Push para a branch
5. Abra um Pull Request

## 📄 Licença

Este projeto é privado e proprietário.

---

**Desenvolvido para integração ClickUp + Conta Azul**