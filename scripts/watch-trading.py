#!/usr/bin/env python3
"""
watch-trading.py — Pipeline de conhecimento de trading

Uso:
  python3 watch-trading.py <youtube-url>
  python3 watch-trading.py <caminho-para-video.mp4>
  python3 watch-trading.py --update-frameworks   # re-consolida frameworks
"""

import sys
import os
import re
import json
import subprocess
import tempfile
import shutil
from datetime import datetime
from pathlib import Path

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY") or ""
CLAWD_DIR = Path.home() / "clawd"
TRADING_DOCS = CLAWD_DIR / "docs" / "trading"
TRADING_VIDEOS = TRADING_DOCS / "videos"
MEMORY_DIR = CLAWD_DIR / "memory"
OBSIDIAN_TRADING = Path.home() / "notes" / "Conhecimento" / "Trading"

CATEGORIES = ["polymarket", "cripto", "acoes", "day-trade", "geral"]

ANALYSIS_PROMPT = """Você é um analista de trading especialista. Analise a transcrição abaixo de um vídeo de trading e extraia conhecimento estruturado.

Retorne um JSON com esta estrutura exata:
{
  "titulo": "título conciso do conteúdo (não o título literal do vídeo se não disponível)",
  "categoria": "polymarket | cripto | acoes | day-trade | geral",
  "resumo": "2-3 frases sobre o que o vídeo ensina",
  "conceitos_chave": ["conceito 1", "conceito 2", ...],
  "estrategias": [
    {
      "nome": "nome da estratégia/setup",
      "descricao": "como funciona",
      "condicoes_entrada": "quando entrar",
      "gestao_risco": "stop, position size, etc"
    }
  ],
  "insights_acionaveis": ["insight 1", "insight 2", ...],
  "psicologia": "menções sobre mentalidade, disciplina, erros comuns",
  "frameworks_para_atualizar": ["nome do framework permanente que deve ser atualizado com esse conhecimento"],
  "tags": ["tag1", "tag2", ...]
}

Se algum campo não tiver informação suficiente na transcrição, coloque null.
Responda APENAS com o JSON, sem markdown ou texto adicional.

TRANSCRIÇÃO:
{transcript}"""

FRAMEWORK_UPDATE_PROMPT = """Você é um analista de trading. Com base nas análises acumuladas abaixo, consolide e atualize o arquivo de frameworks permanentes de trading.

Mantenha a estrutura de seções existente (Gestão de Risco, Price Action, Polymarket, Cripto, Psicologia).
Adicione apenas conhecimento relevante e não redundante.
Seja direto e prático — cada item deve ser algo acionável.

FRAMEWORKS ATUAIS:
{current_frameworks}

NOVAS ANÁLISES:
{new_analyses}

Retorne o arquivo frameworks.md completo e atualizado em Markdown."""


def get_anthropic_key():
    key = ANTHROPIC_API_KEY
    if not key:
        env_file = Path.home() / ".secrets" / ".env"
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                if line.startswith("ANTHROPIC_API_KEY="):
                    key = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
    if not key:
        print("ERRO: ANTHROPIC_API_KEY não encontrada. Defina em ~/.secrets/.env")
        sys.exit(1)
    return key


def call_claude(prompt: str, key: str) -> str:
    import anthropic
    client = anthropic.Anthropic(api_key=key)
    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}]
    )
    return msg.content[0].text


def get_youtube_transcript(url: str) -> tuple[str, str]:
    """Retorna (transcript, titulo)"""
    print(f"⬇ Baixando transcrição do YouTube: {url}")
    with tempfile.TemporaryDirectory() as tmpdir:
        result = subprocess.run(
            ["yt-dlp", "--write-auto-sub", "--skip-download",
             "--sub-format", "vtt", "--sub-lang", "pt,en",
             "--output", f"{tmpdir}/video", url],
            capture_output=True, text=True
        )
        # Tentar pegar título
        title_result = subprocess.run(
            ["yt-dlp", "--get-title", url],
            capture_output=True, text=True
        )
        title = title_result.stdout.strip() or "video-sem-titulo"

        # Pegar arquivo de legenda gerado
        vtt_files = list(Path(tmpdir).glob("*.vtt"))
        if not vtt_files:
            # Tentar sem legenda — pegar apenas áudio e transcrever
            print("  Sem legenda disponível, tentando transcrição por áudio...")
            return get_audio_transcript_from_url(url, tmpdir), title

        vtt_content = vtt_files[0].read_text(encoding="utf-8", errors="ignore")
        transcript = parse_vtt(vtt_content)
        print(f"  ✓ Transcrição obtida ({len(transcript)} chars)")
        return transcript, title


def get_audio_transcript_from_url(url: str, tmpdir: str) -> str:
    """Baixa áudio do YouTube e transcreve com Whisper"""
    audio_path = f"{tmpdir}/audio.mp3"
    subprocess.run(
        ["yt-dlp", "-x", "--audio-format", "mp3",
         "--output", audio_path, url],
        capture_output=True
    )
    if not Path(audio_path).exists():
        raise FileNotFoundError("Não foi possível baixar o áudio do vídeo")
    return transcribe_audio(audio_path)


def transcribe_audio(audio_path: str) -> str:
    """Transcreve arquivo de áudio com Whisper"""
    print(f"  🎙 Transcrevendo áudio com Whisper...")
    import whisper
    model = whisper.load_model("base")
    result = model.transcribe(audio_path, language="pt")
    text = result["text"].strip()
    print(f"  ✓ Transcrição via Whisper ({len(text)} chars)")
    return text


def get_local_transcript(filepath: str) -> tuple[str, str]:
    """Extrai áudio de arquivo local e transcreve"""
    path = Path(filepath)
    title = path.stem
    print(f"🎬 Processando arquivo local: {path.name}")

    with tempfile.TemporaryDirectory() as tmpdir:
        audio_path = f"{tmpdir}/audio.wav"
        print("  🔊 Extraindo áudio com ffmpeg...")
        subprocess.run(
            ["ffmpeg", "-i", str(path), "-ar", "16000", "-ac", "1",
             "-vn", audio_path, "-y"],
            capture_output=True
        )
        if not Path(audio_path).exists():
            raise FileNotFoundError(f"ffmpeg falhou ao extrair áudio de {filepath}")
        transcript = transcribe_audio(audio_path)

    return transcript, title


def parse_vtt(vtt_content: str) -> str:
    """Converte VTT para texto limpo sem timestamps"""
    lines = []
    for line in vtt_content.splitlines():
        line = line.strip()
        if not line or "-->" in line or line.startswith("WEBVTT") or re.match(r"^\d+$", line):
            continue
        # Remove tags HTML
        line = re.sub(r"<[^>]+>", "", line)
        if line and (not lines or lines[-1] != line):
            lines.append(line)
    return " ".join(lines)


def save_video_note(analysis: dict, source: str, date_str: str) -> Path:
    """Salva análise como nota Markdown em clawd e Obsidian"""
    slug = re.sub(r"[^\w\-]", "-", analysis["titulo"].lower())[:60]
    filename = f"{date_str}-{slug}.md"

    content = f"""# {analysis['titulo']}

**Data:** {date_str}
**Categoria:** {analysis['categoria']}
**Fonte:** {source}

## Resumo

{analysis['resumo']}

## Conceitos-chave

{chr(10).join(f"- {c}" for c in (analysis['conceitos_chave'] or []))}

## Estratégias e Setups

"""
    for s in (analysis.get("estrategias") or []):
        content += f"""### {s['nome']}

{s['descricao']}

- **Entrada:** {s.get('condicoes_entrada', '—')}
- **Gestão de risco:** {s.get('gestao_risco', '—')}

"""

    content += f"""## Insights Acionáveis

{chr(10).join(f"- {i}" for i in (analysis['insights_acionaveis'] or []))}

## Psicologia / Mentalidade

{analysis.get('psicologia') or '—'}

## Tags

{' '.join(f"#{t}" for t in (analysis.get('tags') or []))}
"""

    # Salvar em clawd
    clawd_path = TRADING_VIDEOS / filename
    clawd_path.write_text(content, encoding="utf-8")

    # Salvar em Obsidian
    obsidian_path = OBSIDIAN_TRADING / filename
    obsidian_path.write_text(content, encoding="utf-8")

    return clawd_path


def update_readme(analysis: dict, source: str, date_str: str, filename: str):
    """Atualiza o índice README.md do trading"""
    readme = TRADING_DOCS / "README.md"
    content = readme.read_text(encoding="utf-8")

    new_row = f"| {date_str} | {analysis['titulo']} | {analysis['categoria']} | [ver](videos/{filename}) |"
    content = content.replace(
        "| — | — | — | — |",
        f"{new_row}\n| — | — | — | — |"
    )

    # Atualizar estatísticas
    videos = list(TRADING_VIDEOS.glob("*.md"))
    content = re.sub(r"Total de vídeos: \d+", f"Total de vídeos: {len(videos)}", content)
    content = re.sub(r"Última análise: .*", f"Última análise: {date_str}", content)

    readme.write_text(content, encoding="utf-8")


def update_obsidian_index(analysis: dict, filename: str):
    """Atualiza o índice Trading/Index.md no Obsidian"""
    index = OBSIDIAN_TRADING / "Index.md"
    content = index.read_text(encoding="utf-8")

    link = f"- [[{filename[:-3]}]] — {analysis['resumo'][:80]}"
    content = content.replace(
        "*(será preenchido automaticamente)*",
        f"{link}\n*(será preenchido automaticamente)*"
    )
    index.write_text(content, encoding="utf-8")


def append_to_memory(analysis: dict, source: str, date_str: str):
    """Adiciona sumário à memória diária do clawd"""
    MEMORY_DIR.mkdir(exist_ok=True)
    memory_file = MEMORY_DIR / f"{date_str}.md"

    entry = f"""
## [trading] {analysis['titulo']}

- **Fonte:** {source}
- **Categoria:** {analysis['categoria']}
- **Resumo:** {analysis['resumo']}
- **Top insight:** {(analysis['insights_acionaveis'] or ['—'])[0]}
"""

    if memory_file.exists():
        memory_file.write_text(memory_file.read_text() + entry, encoding="utf-8")
    else:
        memory_file.write_text(f"# Memória — {date_str}\n{entry}", encoding="utf-8")


def update_frameworks(key: str):
    """Re-consolida frameworks com base em todas as análises acumuladas"""
    print("🔄 Atualizando frameworks permanentes...")
    current = (TRADING_DOCS / "frameworks.md").read_text(encoding="utf-8")
    analyses = []
    for f in sorted(TRADING_VIDEOS.glob("*.md"))[-10:]:  # últimas 10
        analyses.append(f"### {f.stem}\n{f.read_text()[:800]}")

    if not analyses:
        print("Nenhuma análise encontrada ainda.")
        return

    prompt = FRAMEWORK_UPDATE_PROMPT.format(
        current_frameworks=current,
        new_analyses="\n\n".join(analyses)
    )
    updated = call_claude(prompt, key)
    (TRADING_DOCS / "frameworks.md").write_text(updated, encoding="utf-8")
    print("  ✓ frameworks.md atualizado")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    arg = sys.argv[1]
    key = get_anthropic_key()
    date_str = datetime.now().strftime("%Y-%m-%d")

    if arg == "--update-frameworks":
        update_frameworks(key)
        return

    # Determinar fonte e obter transcrição
    is_youtube = arg.startswith("http://") or arg.startswith("https://")
    if is_youtube:
        transcript, title = get_youtube_transcript(arg)
        source = arg
    else:
        if not Path(arg).exists():
            print(f"ERRO: arquivo não encontrado: {arg}")
            sys.exit(1)
        transcript, title = get_local_transcript(arg)
        source = Path(arg).name

    if len(transcript) < 200:
        print("AVISO: transcrição muito curta, resultado pode ser impreciso")

    # Analisar com Claude
    print("🧠 Analisando com Claude...")
    prompt = ANALYSIS_PROMPT.format(transcript=transcript[:12000])
    raw = call_claude(prompt, key)

    try:
        analysis = json.loads(raw)
    except json.JSONDecodeError:
        # Tentar extrair JSON do texto
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            analysis = json.loads(match.group())
        else:
            print("ERRO: Claude não retornou JSON válido")
            print(raw[:500])
            sys.exit(1)

    print(f"  ✓ Categoria: {analysis['categoria']}")
    print(f"  ✓ Título: {analysis['titulo']}")

    # Salvar nota
    note_path = save_video_note(analysis, source, date_str)
    filename = note_path.name
    print(f"  ✓ Nota salva: {filename}")

    # Atualizar índices
    update_readme(analysis, source, date_str, filename)
    update_obsidian_index(analysis, filename)
    append_to_memory(analysis, source, date_str)

    # Atualizar frameworks se indicado
    if analysis.get("frameworks_para_atualizar"):
        update_frameworks(key)

    print(f"""
✅ Concluído!
   clawd:    ~/clawd/docs/trading/videos/{filename}
   obsidian: ~/notes/Conhecimento/Trading/{filename}
   memória:  ~/clawd/memory/{date_str}.md
""")


if __name__ == "__main__":
    main()
