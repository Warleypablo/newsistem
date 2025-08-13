# Deploy no Railway - Sistema ContaAzul

## Pré-requisitos

1. Conta no [Railway](https://railway.app)
2. Repositório Git (GitHub, GitLab, etc.)
3. Código da aplicação preparado

## Passos para Deploy

### 1. Preparar o Repositório

✅ **Já configurado neste projeto:**
- `requirements.txt` na raiz
- `Procfile` configurado
- `railway.json` para configurações específicas
- `.gitignore` atualizado

### 2. Configurar Variáveis de Ambiente no Railway

No painel do Railway, adicione estas variáveis:

```
FLASK_ENV=production
PORT=5000
DATABASE_URL=postgresql://usuario:senha@host:porta/banco
CONTA_AZUL_ACCESS_TOKEN=seu_token_aqui
```

### 3. Deploy

1. **Conectar Repositório:**
   - Acesse [railway.app](https://railway.app)
   - Clique em "New Project"
   - Selecione "Deploy from GitHub repo"
   - Escolha este repositório

2. **Configurar Banco de Dados:**
   - No Railway, clique em "+ New"
   - Selecione "Database" > "PostgreSQL"
   - Copie a `DATABASE_URL` gerada
   - Cole nas variáveis de ambiente

3. **Deploy Automático:**
   - O Railway detectará automaticamente que é uma aplicação Python
   - Usará o `requirements.txt` para instalar dependências
   - Executará o comando do `Procfile`

### 4. Verificar Deploy

- Acesse a URL fornecida pelo Railway
- Teste as rotas principais:
  - `/` - Página inicial
  - `/turbochat` - Chat
  - `/turbox` - Dashboard
  - `/check-db` - Verificação do banco

## Estrutura do Projeto

```
.
├── src/
│   ├── app.py              # Aplicação principal
│   ├── templates/          # Templates HTML
│   └── __init__.py
├── requirements.txt        # Dependências Python
├── Procfile               # Comando de inicialização
├── railway.json           # Configurações Railway
├── .gitignore            # Arquivos ignorados
└── DEPLOY_RAILWAY.md     # Este arquivo
```

## Comandos Úteis

```bash
# Instalar Railway CLI (opcional)
npm install -g @railway/cli

# Login no Railway
railway login

# Deploy local
railway up

# Ver logs
railway logs
```

## Troubleshooting

### Erro de Porta
- Certifique-se que a variável `PORT` está configurada
- O Railway define automaticamente a porta

### Erro de Banco
- Verifique se `DATABASE_URL` está correta
- Teste a conexão com `/check-db`

### Erro de Dependências
- Verifique se `requirements.txt` está na raiz
- Todas as dependências devem estar listadas

## Monitoramento

- **Logs:** Disponíveis no painel Railway
- **Métricas:** CPU, memória e rede
- **Uptime:** Monitoramento automático

## Custos

- **Plano Gratuito:** 500 horas/mês
- **Banco PostgreSQL:** Incluído no plano gratuito
- **Domínio:** Subdomínio railway.app gratuito

---

**Pronto para deploy!** 🚀

Após seguir estes passos, sua aplicação estará rodando no Railway com deploy automático a cada push no repositório.