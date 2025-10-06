# Monitor de Alertas do Slack

Monitor inteligente de Slack que usa Claude AI para filtrar e priorizar mensagens que merecem sua atenção.

## 🚀 Início Rápido

### 1. Instalar Dependências

```bash
# Configurar ambiente virtual e instalar dependências
./setup.sh

# Atualizar para incluir PyYAML (necessário para config.yaml)
source venv/bin/activate
./update_deps.sh
```

### 2. Configurar Tokens do Slack

1. Abra o Slack no navegador: https://app.slack.com
2. Pressione **F12** (Ferramentas do Desenvolvedor)
3. Vá em: **Application** → **Cookies** → `https://app.slack.com`
4. Copie os cookies:
   - `d` → Este é seu **SLACK_MCP_XOXD_TOKEN**
   - `d-s` → Este é seu **SLACK_MCP_XOXC_TOKEN**

### 3. Configurar Variáveis de Ambiente

```bash
export SLACK_MCP_XOXC_TOKEN='xoxc-seu-token-aqui'
export SLACK_MCP_XOXD_TOKEN='xoxd-seu-token-aqui'
```

Ou crie um arquivo `.env`:
```bash
cp .env.example .env
# Edite .env e cole seus tokens
```

### 4. Configurar Canais e Palavras-chave

O arquivo **`config.yaml`** já está configurado para:

**Canais monitorados:**
- Todos os canais que começam com `cslog-alertas` (exemplo: cslog-alertas-prod, cslog-alertas-dev, etc.)

**Palavras-chave em Português:**
- urgente, emergência, crítico, erro, falha, ajuda, socorro, alerta, etc.

Você pode editar `config.yaml` para personalizar.

### 5. Executar o Monitor

```bash
# Ativar ambiente virtual
source venv/bin/activate

# Verificar uma vez (teste)
python slack_monitor_yaml.py --once

# Monitorar continuamente
python slack_monitor_yaml.py

# Ver ajuda
python slack_monitor_yaml.py --help
```

## 📋 Configuração (config.yaml)

### Canais com Padrões Wildcard

```yaml
channels:
  - "cslog-alertas*"     # Todos os canais cslog-alertas-*
  - "cslog-prod*"        # Todos os canais cslog-prod-*
  - "incidents"          # Canal específico
```

### Palavras-chave Personalizadas

```yaml
keywords:
  - "urgente"
  - "crítico"
  - "erro"
  - "falha"
  - "ajuda"
  # Adicione suas próprias palavras-chave
```

### Intervalo de Verificação

```yaml
check_interval: 300  # Em segundos (300 = 5 minutos)
```

### Recursos Avançados

```yaml
advanced:
  notifications: true              # Notificações desktop
  database: "slack_messages.db"    # Banco de dados
  persist: true                    # Salvar histórico
```

## 🎯 Exemplos de Uso

### Verificar Alertas Uma Vez

```bash
python slack_monitor_yaml.py --once
```

### Monitorar Continuamente

```bash
python slack_monitor_yaml.py
```

### Usar Monitor Básico (sem notificações)

```bash
python slack_monitor_yaml.py --basic
```

### Usar Configuração Customizada

```bash
python slack_monitor_yaml.py --config meu_config.yaml
```

### Executar em Background

```bash
nohup python slack_monitor_yaml.py > monitor.log 2>&1 &
```

## 🔔 Como Funciona

```
Canais do Slack (cslog-alertas*)
         ↓
Servidor MCP do Slack (via tokens do navegador)
         ↓
Claude SDK Client
         ↓
Claude AI (analisa mensagens em português)
         ↓
Classificação: CRÍTICO | IMPORTANTE | NORMAL | IGNORAR
         ↓
Saída Filtrada + Notificações (opcional)
```

## 📊 Classificação de Mensagens

O Claude analisa cada mensagem e classifica como:

- **CRÍTICO** 🚨 - Precisa de atenção imediata
  - Erros de produção
  - Incidentes de segurança
  - Problemas que afetam clientes

- **IMPORTANTE** ⚠️ - Deve ser revisado em breve
  - Falhas de build/deploy
  - Solicitações de revisão de código
  - Avisos de equipe

- **NORMAL** 📝 - Pode ser revisado depois
  - Chat geral da equipe
  - Perguntas não urgentes
  - Mensagens FYI

- **IGNORAR** 🗑️ - Não relevante
  - Spam de bots
  - Chat off-topic
  - Relatórios automatizados

## 🛠️ Comandos Úteis

```bash
# Ativar ambiente
source venv/bin/activate

# Testar configuração
python config_loader.py

# Verificar logs
tail -f monitor.log

# Ver estatísticas (modo avançado)
python cli.py --stats

# Desativar ambiente
deactivate
```

## 🔧 Solução de Problemas

### "ModuleNotFoundError: No module named 'yaml'"

```bash
source venv/bin/activate
pip install pyyaml
```

### "Arquivo de configuração não encontrado"

```bash
# O config.yaml já existe, verifique se está no diretório correto
ls -la config.yaml
```

### "Tokens expirados"

Os tokens do navegador expiram quando você sai do Slack. Solução:
1. Faça login no Slack novamente
2. Pegue novos tokens dos cookies
3. Atualize as variáveis de ambiente

### "Claude Code não encontrado"

```bash
npm install -g @anthropic-ai/claude-code
```

## 📝 Personalização Avançada

### Adicionar Regras Customizadas

Edite `config.yaml`:

```yaml
importance_rules: |
  Regras especiais para minha equipe:

  1. Mensagens do @gerente são sempre IMPORTANTES
  2. Mensagens com "cliente" são CRÍTICAS
  3. Erros em canais cslog-alertas-prod são CRÍTICOS
  4. Ignorar mensagens de bots de CI/CD
```

### Monitorar Múltiplos Padrões

```yaml
channels:
  - "cslog-alertas*"
  - "cslog-prod*"
  - "cslog-incidentes*"
  - "team-urgente"
```

### Adicionar Palavras-chave Específicas do Domínio

```yaml
keywords:
  # Palavras-chave gerais
  - "urgente"
  - "erro"

  # Específicas do seu sistema
  - "api timeout"
  - "banco offline"
  - "cache corrompido"
  - "fila travada"
```

## 🎨 Estrutura dos Arquivos

```
slack_agent/
├── config.yaml              # ← SUA CONFIGURAÇÃO PRINCIPAL
├── slack_monitor_yaml.py    # ← Monitor com suporte a YAML
├── config_loader.py         # Carregador de configuração
├── slack_monitor.py         # Monitor básico
├── advanced_example.py      # Monitor avançado
├── cli.py                   # Interface de linha de comando
├── quick_start.py           # Assistente de configuração
├── setup.sh                 # Script de instalação
├── update_deps.sh           # Atualizar dependências
└── README_PT.md             # Esta documentação
```

## 📞 Suporte

Se encontrar problemas:

1. Verifique os logs: `tail -f monitor.log`
2. Teste a configuração: `python config_loader.py`
3. Teste o SDK: `python test_sdk.py`
4. Verifique os tokens do Slack

## 🚦 Status do Sistema

Verificar se tudo está funcionando:

```bash
# 1. Ambiente ativo?
which python  # Deve mostrar: .../venv/bin/python

# 2. Dependências instaladas?
pip list | grep claude

# 3. Configuração válida?
python config_loader.py

# 4. Tokens configurados?
echo $SLACK_MCP_XOXC_TOKEN

# 5. Testar conexão
python quick_start.py
```

## 💡 Dicas

1. **Execute em background** para monitoramento contínuo
2. **Ajuste o intervalo** conforme necessário (60s para urgente, 600s para normal)
3. **Use notificações** para alertas críticos
4. **Revise o histórico** no banco de dados
5. **Customize as regras** para seu workflow

---

Criado com ❤️ usando Claude Agent SDK
