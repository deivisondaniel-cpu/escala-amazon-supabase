# Escala Amazon — versão Supabase

Esta versão remove o SQLite local (`escala_amazon_v2.db`) da aplicação.

## Arquitetura

Streamlit → Supabase PostgreSQL

O banco é criado automaticamente na primeira execução e os dados ficam persistidos no Supabase.

## Arquivos

- `app.py` — aplicação completa
- `requirements.txt` — dependências
- `.streamlit/secrets.example.toml` — modelo de configuração
- `.gitignore` — impede envio de credenciais e bancos locais

## Importante

Não publique `secrets.toml` no GitHub.

No Streamlit Cloud, configure os Secrets com:

```toml
[connections.supabase_db]
url = "SUA_CONNECTION_STRING"

[auth]
usuario = "admin"
senha = "SUA_SENHA_FORTE"
```

A senha do banco mostrada em capturas anteriores deve ser trocada/rotacionada antes de usar a nova aplicação.

## Sobre os dados antigos

O novo app NÃO consegue recuperar alterações que estavam somente dentro do antigo SQLite sem ter acesso ao arquivo `.db`.

Se o arquivo `escala_amazon_v2.db` existir e for localizado, ele pode ser migrado para o Supabase antes de apagar qualquer coisa.
