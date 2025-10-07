# 🗄️ Configuração do Banco de Dados no Railway

## Problema Atual

A aplicação está funcionando, mas não consegue conectar ao banco de dados porque as variáveis de ambiente não estão configuradas no Railway.

## ✅ Solução: Configurar PostgreSQL no Railway

### Passo 1: Adicionar Banco PostgreSQL

1. **Acesse seu projeto no Railway:**
   - Vá para [railway.app](https://railway.app)
   - Entre no seu projeto

2. **Adicionar PostgreSQL:**
   - Clique no botão **"+ New"**
   - Selecione **"Database"**
   - Escolha **"PostgreSQL"**
   - Aguarde a criação do banco

### Passo 2: Configurar Variáveis de Ambiente

1. **Copiar DATABASE_URL:**
   - No banco PostgreSQL criado, vá na aba **"Variables"**
   - Copie o valor de **`DATABASE_URL`**

2. **Configurar na aplicação:**
   - Vá para o serviço da sua aplicação (não o banco)
   - Clique na aba **"Variables"**
   - Adicione a variável:
     ```
     DATABASE_URL = postgresql://usuario:senha@host:porta/banco
     ```

### Passo 3: Verificar Conexão

Após configurar, acesse:
- **`/check-db`** - Para verificar se a conexão está funcionando
- **`/turbochat`** - Para testar as consultas

## 🔧 Variáveis Necessárias

### Opção 1: DATABASE_URL (Recomendado)
```
DATABASE_URL=postgresql://usuario:senha@host:porta/banco
```

### Opção 2: Variáveis Individuais
```
PG_HOST=seu_host
PG_DBNAME=seu_banco
PG_USER=seu_usuario
PG_PASSWORD=sua_senha
PG_PORT=5432
```

## 📊 Estrutura do Banco

O banco precisa ter as seguintes tabelas:
- `caz_clientes`
- `caz_receber`
- `cup_clientes`

## 🚨 Troubleshooting

### Erro: "Não foi possível conectar ao banco"
- ✅ Verifique se DATABASE_URL está configurada
- ✅ Teste a conexão em `/check-db`
- ✅ Verifique se o banco PostgreSQL está ativo

### Erro: "Variáveis não configuradas"
- ✅ Configure DATABASE_URL no Railway
- ✅ Redeploy a aplicação

## 📞 Suporte

Se precisar de ajuda:
1. Verifique os logs no Railway
2. Teste `/check-db` para diagnóstico
3. Confirme que o banco PostgreSQL está rodando

---

**Após configurar o banco, todas as funcionalidades do TurboChat estarão disponíveis!** 🚀