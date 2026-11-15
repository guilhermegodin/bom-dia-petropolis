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

## Site

`python -m robo.site` gera o site em `_site/` a partir das matérias e da agenda. O workflow
"Publicar site" faz isso sozinho depois de cada rodada do robô e publica no GitHub Pages.

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
