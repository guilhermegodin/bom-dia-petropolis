# Bom Dia Petrópolis

Portal de notícias de Petrópolis escrito automaticamente por IA, com tom positivo.

## Como funciona

1. **Coleta** (`robo/coletar.py`): quatro vezes por dia, o robô lê as fontes de `fontes.yaml`
   e pega as notícias que ainda não viu.
2. **Escrita** (`robo/escrever.py`): a IA (Gemini grátis por padrão, ou Claude) lê cada notícia, decide se ela combina com o
   `guia_editorial.md` e, se sim, escreve uma matéria com texto próprio e a coloca em
   Cotidiano, Agenda ou Cidade.
3. **Publicação** (`robo/main.py`): as matérias aprovadas viram arquivos em
   `conteudo/materias/`, e os eventos vão para `dados/agenda.json`. O site (próximo passo)
   é montado a partir dessas pastas.

Cada decisão, inclusive as notícias descartadas e o motivo, fica em `dados/registro.jsonl`.

## Configuração (uma vez só)

1. Crie uma chave grátis do Gemini em https://aistudio.google.com/apikey (não pede cartão).
2. No GitHub, abra **Settings → Secrets and variables → Actions → New repository secret**,
   com o nome `GEMINI_API_KEY` e a chave como valor.
3. Em **Actions → Robô de notícias → Run workflow**, marque "modo teste" para ver no log o
   que seria publicado, sem publicar nada.

### Trocar para o Claude (pago) no futuro

1. Crie uma chave em https://platform.claude.com e salve como o segredo `ANTHROPIC_API_KEY`.
2. Em **Settings → Secrets and variables → Actions → Variables**, crie a variável
   `IA_PROVEDOR` com o valor `claude`.

### Se o Gemini reclamar do modelo

O nome do modelo grátis muda de tempos em tempos. Crie a variável `GEMINI_MODELO` (aba
Variables) com o nome atual de um modelo "Flash-Lite" listado no Google AI Studio.

### Releases por e-mail (opcional)

O robô também lê releases enviados para uma caixa de e-mail do portal.

1. Crie um Gmail só para o portal e ative a verificação em duas etapas
   (https://myaccount.google.com/security).
2. Crie uma **senha de app** em https://myaccount.google.com/apppasswords.
3. Salve dois segredos no GitHub: `EMAIL_USUARIO` (o endereço) e `EMAIL_SENHA_APP` (a senha de app).
4. Peça às assessorias (prefeitura, Sesc, museus, teatros) para incluírem esse e-mail na lista de releases.
5. Para aceitar só remetentes conhecidos, preencha `remetentes` na fonte "Releases por e-mail" em `fontes.yaml`.

O robô só lê os e-mails, sem apagar nem marcar como lidos.

## Site

`python -m robo.site` gera o site em `_site/` a partir das matérias e da agenda. O workflow
"Publicar site" faz isso sozinho depois de cada rodada do robô e publica no GitHub Pages.

O visual fica em `site/estilo.css` e o layout em `robo/site.py` (capa com manchete, destaques,
blocos por editoria, "Últimas" e "Agenda da semana" na lateral). Como as matérias não têm foto,
cada uma ganha uma arte própria de serra e sol nas cores da editoria. Se uma matéria trouxer o
campo `imagem` no cabeçalho (endereço de uma foto com direito de uso), ela substitui a arte.
Prévias do layout ficam em `previa/`.

O arquivo `site/portal.js` cuida do relógio, do carrossel de manchetes, da previsão do tempo
(Open-Meteo, grátis e sem chave) e da busca, que procura nas matérias listadas em `busca.json`.

Para ligar o GitHub Pages (uma vez só): **Settings → Pages → Build and deployment → Source:
GitHub Actions**.

## Ajustes comuns

- **Adicionar uma fonte:** inclua um item em `fontes.yaml`.
- **Mudar o tom ou as regras:** edite `guia_editorial.md`.
- **Mais ou menos matérias:** mude `MAX_MATERIAS_POR_RODADA` em `robo/main.py` (hoje 8 por
  rodada, 4 rodadas por dia) ou os horários em `.github/workflows/robo.yml`.

## Rodar no computador

```bash
pip install -r requirements.txt
export GEMINI_API_KEY=...
python -m robo.main --teste
```

## Redes sociais (Facebook e Instagram)

Depois que o site é publicado, o workflow "Publicar site" posta as matérias novas na Página do
Facebook e no Instagram do portal, pelas APIs oficiais da Meta (`robo/redes.py`). Cada matéria
vira um card 1080x1350 com a foto, a etiqueta e a cor da editoria (Cotidiano verde, Agenda
laranja, Cidade azul) e a marca no rodapé. Sem foto, o card usa a arte de serra e sol.

- No Facebook o post leva o título, o resumo e o link da matéria.
- No Instagram o post leva título, resumo, "link na bio" e hashtags.
- Posta até 3 matérias por rodada (variável `REDES_POR_RODADA`), só das últimas 24 horas.
- O que já foi postado fica em `dados/redes.json`, para nada sair repetido.
- Sem o segredo `META_TOKEN`, nada é postado e o resto segue normal.

WhatsApp não é automatizado de propósito: robôs em grupos levam ao bloqueio do número. O caminho
seguro é um Canal de WhatsApp do portal, com postagem manual.

### Configuração (uma vez só)

1. **Página do Facebook**: crie em https://www.facebook.com/pages/create.
2. **Instagram profissional**: no app do Instagram, em Configurações → Tipo de conta, mude para
   conta profissional. Depois ligue o Instagram à Página (na Página: Configurações → Contas
   vinculadas → Instagram).
3. **App da Meta**: em https://developers.facebook.com/apps clique em **Criar app**, escolha o
   caso de uso de gerenciar Página e conteúdo do Instagram, tipo **Empresa**.
4. **Token**: abra o Explorador da Graph API (https://developers.facebook.com/tools/explorer),
   escolha o app, clique em **Gerar token de acesso** e marque as permissões
   `pages_show_list`, `pages_read_engagement`, `pages_manage_posts`, `instagram_basic`,
   `instagram_content_publish` e `business_management`. Autorize a Página e o Instagram.
5. **Token que não expira**: cole o token no Depurador (https://developers.facebook.com/tools/debug/accesstoken),
   clique em **Depurar** e depois em **Estender token de acesso**. Volte ao Explorador, cole o
   token estendido, consulte `me/accounts` e copie o `access_token` da sua Página.
   No Depurador, esse token da Página deve mostrar "Expira: Nunca".
6. **GitHub**: salve esse token como o segredo `META_TOKEN`
   (Settings → Secrets and variables → Actions → New repository secret).
7. **Teste**: em Actions → **Testar redes sociais** → Run workflow. O log mostra a Página e o
   Instagram conectados e o que seria postado, sem postar nada.
8. Coloque o endereço do site no link da bio do Instagram.

Se os posts do Facebook aparecerem só para você, publique o app (modo "Ao vivo") no painel da Meta.
