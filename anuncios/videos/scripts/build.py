"""Gera voz, mixagem e composição HyperFrames para cada anúncio.

Uso:
  python3 scripts/build.py            # todos
  python3 scripts/build.py 01 07      # só os ids que começam com 01 e 07
Saída: build/<id>/index.html (+ assets) — renderize com scripts/render.sh
"""
import json
import os
import re
import shutil
import sys

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ads import ADS, BRAND  # noqa: E402
import scenes as S  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SR = 44100
GAP = 0.10          # pausa entre frases (igual ao narrar.py do canal)
GAP_PERGUNTA = 0.22
VOZ = "pt-BR-AntonioNeural"
VELOCIDADE = "+15%"
CTA_TAIL = 2.4

PRON = {
    "R$16/mês": "dezesseis reais por mês", "R$16": "dezesseis reais", "R$0,53": "cinquenta e três centavos",
    "R$2.000": "dois mil reais", "R$3.000": "três mil reais", "R$5.000": "cinco mil reais",
    "1": "um", "3": "três", "5": "cinco", "60": "sessenta",
}
PUNCT = ".,:;?…"

_kokoro = None
_tok = None


def kokoro():
    global _kokoro, _tok
    if _kokoro is None:
        from kokoro_onnx import Kokoro
        from kokoro_onnx.tokenizer import Tokenizer
        cache = os.path.expanduser("~/.cache/hyperframes/tts")
        _kokoro = Kokoro(f"{cache}/models/kokoro-v1.0.onnx", f"{cache}/voices/voices-v1.0.bin")
        _tok = Tokenizer()
    return _kokoro, _tok


def split_token(tok):
    m = re.match(r"^([…\.]*)(.*?)([" + re.escape(PUNCT) + r"]*)$", tok)
    return m.group(1), m.group(2), m.group(3)


def spoken_tokens(cap):
    """Devolve lista de (texto_caption, texto_falado, pontuação_final)."""
    out = []
    for tok in S.plain(cap).split():
        pre, core, post = split_token(tok)
        say = PRON.get(core, core)
        out.append((tok, say, post))
    return out


TICK = 10_000_000  # Edge TTS mede o tempo em unidades de 100 ns
ANTES, DEPOIS = 0.04, 0.12  # folga para não cortar o início nem o fim da fala


def tts(text):
    """Narra com Edge TTS (voz do canal). Devolve (áudio 44.1 kHz, palavras com início/fim relativos ao áudio)."""
    import asyncio
    import subprocess
    import tempfile
    import edge_tts

    async def run(dest):
        com = edge_tts.Communicate(text.replace("…", "..."), VOZ, rate=VELOCIDADE, boundary="WordBoundary",
                                   proxy=os.environ.get("HTTPS_PROXY") or None)
        words = []
        with open(dest, "wb") as f:
            async for ch in com.stream():
                if ch["type"] == "audio":
                    f.write(ch["data"])
                elif ch["type"] == "WordBoundary":
                    st = ch["offset"] / TICK
                    words.append(dict(text=ch["text"], start=st, end=st + ch["duration"] / TICK))
        return words

    with tempfile.TemporaryDirectory() as tmp:
        mp3 = os.path.join(tmp, "v.mp3")
        for tentativa in range(4):
            try:
                words = asyncio.run(run(mp3))
                break
            except Exception:
                if tentativa == 3:
                    raise
        raw = subprocess.run(["ffmpeg", "-v", "error", "-i", mp3, "-f", "f32le", "-ac", "1", "-ar", str(SR), "-"],
                             check=True, capture_output=True).stdout
    x = np.frombuffer(raw, dtype=np.float32).astype(np.float64)
    corte = max(0.0, words[0]["start"] - ANTES)
    fim = min(len(x) / SR, words[-1]["end"] + DEPOIS)
    x = x[int(corte * SR):int(fim * SR)]
    x = x / (np.max(np.abs(x)) + 1e-9) * 0.92
    for w in words:
        w["start"] -= corte
        w["end"] -= corte
    return x, words


def map_words(cap, start, edge_words, dur):
    """Casa as palavras do Edge TTS com as palavras da legenda (uma palavra da legenda pode virar várias faladas)."""
    toks = spoken_tokens(cap)
    counts = [len(say.split()) for _, say, _ in toks]
    if sum(counts) != len(edge_words):
        print(f"  aviso: {sum(counts)} palavras no texto x {len(edge_words)} faladas, tempos estimados: {S.plain(cap)}")
        print("   ", [w["text"] for w in edge_words])
        return word_times(cap, start, dur)  # contagem diferente: volta para a estimativa
    out, k = [], 0
    for (cap_tok, _, _), n in zip(toks, counts):
        ws = edge_words[k:k + n]
        k += n
        out.append(dict(text=cap_tok, t=start + ws[0]["start"], d=ws[-1]["end"] - ws[0]["start"]))
    return out


def word_times(cap, start, dur):
    """Estima o início de cada palavra pela contagem de fonemas + pausas."""
    _, tok = kokoro()
    toks = spoken_tokens(cap)
    weights, pauses = [], []
    for _, say, post in toks:
        ph = tok.phonemize(say, "pt-br")
        n = len(re.sub(r"[ˈˌ\s]", "", ph))
        weights.append(max(n, 2))
        p = 0
        if post:
            p = 6 if any(ch in post for ch in ".?…") else (4 if ":" in post else 3)
        pauses.append(p)
    total = sum(weights) + sum(pauses[:-1])
    unit = dur / max(total, 1)
    t, out = start, []
    for (cap_tok, say, _), w, p in zip(toks, weights, pauses):
        out.append(dict(text=cap_tok, t=t, d=w * unit))
        t += (w + p) * unit
    return out


def marked_words(cap):
    """Divide o texto em palavras, preservando o estilo (*em* / !danger!) de cada pedaço."""
    words, cur = [], []
    for seg, st in S.parse_marks(cap):
        parts = seg.split(" ")
        for k, piece in enumerate(parts):
            if k > 0:
                words.append(cur)
                cur = []
            if piece:
                cur.append((piece, st))
    words.append(cur)
    words = [w for w in words if w]
    return ["".join(f'<span class="{st}">{S.esc(p)}</span>' if st else S.esc(p) for p, st in w) for w in words]


def cap_chunks(cap, words):
    """Agrupa palavras (com marcações) em blocos de legenda de até 3 palavras."""
    marked = marked_words(cap)
    chunks, cur = [], []
    for i, w in enumerate(words):
        cur.append(i)
        txt = " ".join(words[j]["text"] for j in cur)
        if len(cur) >= 3 or len(txt) > 15 or w["text"][-1] in PUNCT:
            chunks.append(cur)
            cur = []
    if cur:
        chunks.append(cur)
    out = []
    for ch in chunks:
        out.append(dict(t=words[ch[0]]["t"], html=" ".join(marked[j] for j in ch)))
    return out


def build_ad(ad):
    outdir = os.path.join(ROOT, "build", ad["id"])
    if os.path.exists(outdir):
        shutil.rmtree(outdir)
    os.makedirs(os.path.join(outdir, "assets"))
    shutil.copytree(os.path.join(ROOT, "assets/fonts"), os.path.join(outdir, "assets/fonts"))
    emoji = os.path.join(outdir, "assets/fonts/NotoColorEmoji.ttf")
    if not os.path.exists(emoji):
        shutil.copy("/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf", emoji)
    shutil.copy(os.path.join(ROOT, "assets/gsap.min.js"), os.path.join(outdir, "assets/gsap.min.js"))

    # 1) voz e tempos
    beats, t = [], 0.0
    voice_parts = []
    for i, b in enumerate(ad["beats"]):
        say = " ".join(s for _, s, _ in spoken_tokens(b["cap"]))
        # mantém pontuação para prosódia
        say = " ".join(s + (p if not s.endswith(p) else "") for _, s, p in spoken_tokens(b["cap"]))
        audio, ew = tts(say)
        dur = len(audio) / SR
        beat = dict(i=i, start=t, speech=dur, cap=b["cap"], scene=b.get("scene"))
        beat["words"] = map_words(b["cap"], t, ew, dur)
        voice_parts.append((t, audio))
        t += dur + (GAP_PERGUNTA if S.plain(b["cap"]).rstrip().endswith("?") else GAP)
        beat["end"] = t
        beats.append(beat)
    beats[-1]["end"] = beats[-1]["start"] + beats[-1]["speech"] + CTA_TAIL
    total = beats[-1]["end"]

    # 2) cenas
    tl = S.TL()
    sfx = []
    scene_html, cap_html = [], []
    groups = []
    for b in beats:
        if b["scene"]:
            groups.append(dict(scene=b["scene"], beats=[b]))
        else:
            groups[-1]["beats"].append(b)
    for gi, g in enumerate(groups):
        sc = g["scene"]
        ctx = S.Ctx(g["beats"])
        sid = f"s{gi}"
        layout = "top" if sc["type"] in S.TOP_LAYOUT else "mid"
        body = S.SCENES[sc["type"]](ctx, sc, sid, tl, sfx, g["beats"][0])
        if sc.get("badge"):
            body += S.badge(sid, sc["badge"], layout, tl, ctx.t0 + 0.1)
        start = ctx.t0 if gi == 0 else ctx.t0 - 0.0
        dur = ctx.t1 - start
        scene_html.append(f'<div class="clip scene sc-{sc["type"]}" id="{sid}" data-start="{start:.3f}" data-duration="{dur:.3f}" data-track-index="1">{body}</div>')
        if gi > 0:
            tl.ft(f"#{sid}", {"opacity": 0.0, "scale": 1.06}, {"opacity": 1, "scale": 1, "duration": 0.14, "ease": "power2.out"}, start)
            sfx.append(("whoosh", start - 0.15, 0.45))
        if sc["type"] == "cta":
            sfx.append(("riser", start - 1.6, 0.25))
        # legendas
        if sc["type"] not in ("hook", "cta"):
            for b in g["beats"]:
                chunks = S_chunks = cap_chunks(b["cap"], b["words"])
                for ci, ch in enumerate(S_chunks):
                    c0 = max(ch["t"] - 0.06, b["start"])
                    c1 = S_chunks[ci + 1]["t"] - 0.06 if ci + 1 < len(S_chunks) else b["end"]
                    cid = f"c{b['i']}_{ci}"
                    cap_html.append(f'<div class="clip cap cap-{layout}" id="{cid}" data-start="{c0:.3f}" data-duration="{max(c1 - c0, 0.1):.3f}" data-track-index="2"><span class="cap-in" id="{cid}-in">{ch["html"]}</span></div>')
                    tl.ft(f"#{cid}-in", {"scale": 0.7, "opacity": 0}, {"scale": 1, "opacity": 1, "duration": 0.12, "ease": "back.out(2.5)"}, c0)

    # 3) áudio
    mix_audio(ad, voice_parts, sfx, total, os.path.join(outdir, "assets/mix.wav"))

    # 4) html
    page = PAGE.format(
        css=CSS % dict(BRAND), total=f"{total:.3f}", scenes="\n".join(scene_html), caps="\n".join(cap_html),
        stars=stars_html(), js="\n".join(tl.js), orbit_dur=f"{total:.3f}", title=ad["id"])
    with open(os.path.join(outdir, "index.html"), "w") as f:
        f.write(page)
    with open(os.path.join(outdir, "meta.json"), "w") as f:
        json.dump({"id": ad["id"], "name": ad["id"]}, f)
    with open(os.path.join(outdir, "hyperframes.json"), "w") as f:
        json.dump({"paths": {"blocks": "compositions", "components": "compositions/components", "assets": "assets"}}, f)
    with open(os.path.join(outdir, "script.json"), "w") as f:
        json.dump(dict(id=ad["id"], awareness=ad["awareness"], angle=ad["angle"], hook=ad["hook_ref"], voice=VOZ,
                       music=ad["music"], duration=round(total, 2),
                       beats=[dict(t=round(b["start"], 2), text=S.plain(b["cap"])) for b in beats]), f, ensure_ascii=False, indent=1)
    print(f"{ad['id']}: {total:.1f}s, {len(groups)} cenas, {len(cap_html)} legendas")
    return total


def load_wav(path):
    x, sr = sf.read(path, always_2d=True)
    assert sr == SR
    return x


def mix_audio(ad, voice_parts, sfx, total, path):
    n = int((total + 0.2) * SR)
    voice = np.zeros(n)
    for t, a in voice_parts:
        i = int(t * SR)
        voice[i:i + len(a)] += a[: max(n - i, 0)]
    # envelope de ducking
    act = np.convolve((np.abs(voice) > 0.02).astype(float), np.ones(int(0.25 * SR)) / int(0.25 * SR), mode="same")
    act = np.clip(act * 3, 0, 1)
    music = load_wav(os.path.join(ROOT, "assets/audio/music", f"{ad['music']}.wav"))
    if len(music) < n:
        music = np.concatenate([music, music])
    music = music[:n].copy()
    gain = 0.30 - 0.17 * act
    fade = int(1.5 * SR)
    gain[-fade:] *= np.linspace(1, 0, fade)
    gain[: int(0.05 * SR)] *= np.linspace(0, 1, int(0.05 * SR))
    out = music * gain[:, None]
    out += np.stack([voice, voice], 1) * 0.95
    cache = {}
    for name, t, g in sfx:
        if name not in cache:
            cache[name] = load_wav(os.path.join(ROOT, "assets/audio/sfx", f"{name}.wav"))
        s = cache[name]
        i = int(max(t, 0) * SR)
        m = min(len(s), n - i)
        if m > 0:
            out[i:i + m] += s[:m] * g * 0.42
    peak = np.max(np.abs(out))
    out = np.tanh(out / max(peak, 1e-9) * 1.1) * 0.95
    sf.write(path, out.astype(np.float32), SR, subtype="PCM_16")


def stars_html():
    seed, out = 12345, []
    for i in range(46):
        seed = (seed * 1103515245 + 12345) % 2 ** 31
        x = seed % 1080
        seed = (seed * 1103515245 + 12345) % 2 ** 31
        y = seed % 1920
        s = 2 + (seed % 3)
        o = 0.25 + (seed % 50) / 100
        out.append(f'<i style="left:{x}px;top:{y}px;width:{s}px;height:{s}px;opacity:{o:.2f}"></i>')
    return "".join(out)


PAGE = """<!doctype html>
<html lang="pt-BR" data-resolution="portrait">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=1080, height=1920" />
<title>{title}</title>
<script src="assets/gsap.min.js"></script>
<style>{css}</style>
</head>
<body>
<div id="root" data-composition-id="main" data-start="0" data-duration="{total}" data-width="1080" data-height="1920">
  <div class="bg"><div class="glow g1"></div><div class="glow g2"></div>
    <div class="orbit o1" id="orb1"><b></b></div><div class="orbit o2" id="orb2"><b></b></div>
    <div class="stars">{stars}</div></div>
{scenes}
{caps}
  <audio id="mix" src="assets/mix.wav" data-start="0" data-duration="{total}" data-volume="1"></audio>
</div>
<script>
  window.__timelines = window.__timelines || {{}};
  const tl = gsap.timeline({{ paused: true }});
  tl.fromTo("#orb1", {{rotation: 0}}, {{rotation: 120, duration: {orbit_dur}, ease: "none"}}, 0);
  tl.fromTo("#orb2", {{rotation: 20}}, {{rotation: -90, duration: {orbit_dur}, ease: "none"}}, 0);
{js}
  window.__timelines["main"] = tl;
  tl.seek(0);
</script>
</body>
</html>
"""

CSS = """
@font-face{font-family:Mont;font-weight:800;src:url(assets/fonts/montserrat-latin-800-normal.woff2) format('woff2')}
@font-face{font-family:Mont;font-weight:900;src:url(assets/fonts/montserrat-latin-900-normal.woff2) format('woff2')}
@font-face{font-family:Mont;font-weight:900;font-style:italic;src:url(assets/fonts/montserrat-latin-900-italic.woff2) format('woff2')}
@font-face{font-family:'Noto Color Emoji';src:url(assets/fonts/NotoColorEmoji.ttf) format('truetype')}
@font-face{font-family:Inter;font-weight:400;src:url(assets/fonts/inter-latin-400-normal.woff2) format('woff2')}
@font-face{font-family:Inter;font-weight:500;src:url(assets/fonts/inter-latin-500-normal.woff2) format('woff2')}
@font-face{font-family:Inter;font-weight:600;src:url(assets/fonts/inter-latin-600-normal.woff2) format('woff2')}
@font-face{font-family:Inter;font-weight:700;src:url(assets/fonts/inter-latin-700-normal.woff2) format('woff2')}
@font-face{font-family:Inter;font-weight:800;src:url(assets/fonts/inter-latin-800-normal.woff2) format('woff2')}
:root{--wab:#0d9448;--bg1:%(bg1)s;--bg2:%(bg2)s;--pri:%(primary)s;--sec:%(secondary)s;--acc:%(accent)s;--dan:%(danger)s;--wa:%(whats)s}
*{margin:0;padding:0;box-sizing:border-box}
html,body{width:1080px;height:1920px;overflow:hidden;background:var(--bg1)}
#root{position:relative;width:1080px;height:1920px;overflow:hidden;font-family:Inter,'Noto Color Emoji',sans-serif;color:#fff}
.emo{font-family:'Noto Color Emoji',sans-serif}
.em{color:var(--acc)} .danger{color:var(--dan)}
.bg{position:absolute;inset:0;background:radial-gradient(1200px 1400px at 50%% 35%%,var(--bg2),var(--bg1))}
.glow{position:absolute;border-radius:50%%;filter:blur(90px);opacity:.45}
.g1{width:700px;height:700px;left:-250px;top:150px;background:var(--pri)}
.g2{width:600px;height:600px;right:-220px;top:1100px;background:var(--sec);opacity:.25}
.orbit{position:absolute;left:50%%;top:42%%;border:2px solid rgba(255,255,255,.08);border-radius:50%%}
.o1{width:1500px;height:1500px;margin:-750px 0 0 -750px}
.o2{width:1000px;height:1000px;margin:-500px 0 0 -500px;border-color:rgba(43,217,254,.10)}
.orbit b{position:absolute;top:-9px;left:50%%;width:18px;height:18px;border-radius:50%%;background:var(--sec);box-shadow:0 0 24px var(--sec)}
.o1 b{background:var(--pri);box-shadow:0 0 24px var(--pri)}
.stars i{position:absolute;border-radius:50%%;background:#fff}
.clip.scene{position:absolute;inset:0}
.flash{position:absolute;inset:0}
.shake{position:absolute;inset:0}
.hook-line{position:absolute;left:40px;right:40px;text-align:center;font-family:Mont;font-weight:900;text-transform:uppercase;line-height:1;letter-spacing:-.02em;text-shadow:0 8px 0 rgba(0,0,0,.35),0 0 40px rgba(0,0,0,.4)}
.hook-emo{position:absolute;left:0;right:0;text-align:center;font-size:190px;line-height:1}
.stop-oct{position:absolute;left:0;right:0;top:420px;text-align:center;font-size:900px;line-height:1;font-family:'Noto Color Emoji'}
/* legendas */
.clip.cap{position:absolute;left:50px;right:50px;display:flex;justify-content:center;align-items:center;text-align:center}
.cap-mid{top:1070px;height:200px}
.cap-top{top:292px;height:180px}
.cap-in{display:inline-block;font-family:Mont;font-weight:900;font-size:68px;line-height:1.1;text-transform:uppercase;letter-spacing:-.01em;
  background:rgba(6,10,31,.78);padding:16px 30px;border-radius:26px;box-shadow:0 12px 40px rgba(0,0,0,.35);border:2px solid rgba(255,255,255,.08)}
/* badge */
.badge{position:absolute;left:44px;width:150px;height:150px;border-radius:50%%;background:var(--acc);color:#111;font-family:Mont;font-weight:900;font-size:100px;display:flex;align-items:center;justify-content:center;box-shadow:0 10px 40px rgba(255,210,63,.45);z-index:5}
/* busca */
.search{position:absolute;left:60px;right:60px;top:260px;background:#fff;border-radius:40px;padding:34px;color:#202124;box-shadow:0 30px 80px rgba(0,0,0,.45)}
.sbar{display:flex;align-items:center;gap:18px;border:3px solid #dfe1e5;border-radius:60px;padding:22px 30px;font-size:42px;box-shadow:0 4px 14px rgba(0,0,0,.08)}
.q{white-space:nowrap;overflow:hidden;font-weight:500}.q .ch{opacity:0}.caret{color:#1a73e8;font-weight:300}
.sres{margin-top:26px;display:flex;flex-direction:column;gap:20px}
.res{position:relative;border:2px solid #eceef1;border-radius:26px;padding:22px 26px}
.res.hl{border:4px solid var(--wa);box-shadow:0 0 0 8px rgba(37,211,102,.15)}
.tag-comp{position:absolute;right:20px;top:-22px;background:var(--wab);color:#fff;font-weight:800;font-size:24px;padding:6px 16px;border-radius:20px}
.r-url{font-size:26px;color:#4d5156}.r-title{font-size:40px;color:#1a0dab;font-weight:600;margin:4px 0}
.r-stars{font-size:28px;color:#70757a}.r-stars:first-letter{color:#fbbc04}
.r-chips{display:flex;gap:12px;margin-top:12px}.r-chips span{border:2px solid #dadce0;border-radius:30px;padding:8px 20px;font-size:26px;color:#1a73e8;font-weight:600}
.res.miss{border:4px dashed var(--dan);background:#fff5f6;text-align:center}
.miss-name{font-size:40px;font-weight:700;color:#5f6368}.miss-x{font-size:40px;font-weight:800;color:var(--dan);margin-top:6px}
.miss-big{font-size:42px;font-weight:800;color:var(--dan);padding:30px 0}
/* celular */
.phone{position:absolute;width:560px;height:1110px;border-radius:78px;background:#0b0b0f;padding:18px;box-shadow:0 0 0 4px #2a2a35,0 40px 100px rgba(0,0,0,.6),0 0 120px rgba(123,97,255,.25)}
.screen{position:relative;width:100%%;height:100%%;border-radius:62px;overflow:hidden;background:#fff}
.status{position:absolute;top:0;left:0;right:0;height:48px;z-index:3;display:flex;justify-content:space-between;padding:12px 40px;font-size:20px;font-weight:700;color:#111;background:rgba(255,255,255,.92)}
.viewport{position:absolute;top:48px;left:0;right:0;bottom:0;overflow:hidden}
.ex-label{position:absolute;top:-34px;right:40px;background:rgba(255,255,255,.14);color:#fff;font-size:18px;font-weight:700;padding:5px 14px;border-radius:14px;letter-spacing:.08em}
.fab{position:absolute;right:26px;bottom:34px;width:96px;height:96px;border-radius:50%%;background:var(--wab);display:flex;align-items:center;justify-content:center;font-size:50px;box-shadow:0 10px 30px rgba(37,211,102,.55);z-index:4;font-family:'Noto Color Emoji'}
.finger{position:absolute;left:705px;top:1465px;font-size:130px;z-index:9;transform-origin:30%% 10%%}
.notif{position:absolute;left:18px;right:18px;top:64px;z-index:6;background:rgba(255,255,255,.97);border-radius:28px;padding:20px 22px;display:flex;gap:16px;align-items:center;color:#111;font-size:23px;box-shadow:0 18px 40px rgba(0,0,0,.35)}
.notif .emo{font-size:46px}
/* site */
.site{color:#111;font-family:Inter,'Noto Color Emoji'}
.s-nav{height:74px;display:flex;align-items:center;gap:12px;padding:0 26px;font-size:22px;background:#fff;border-bottom:1px solid #eee}
.s-nav .burger{margin-left:auto;font-size:30px}
.s-hero{height:540px;background:linear-gradient(160deg,var(--c1),var(--c2));color:#fff;text-align:center;padding:40px 34px}
.hero-emo{font-size:110px;line-height:1.1}
.s-hero h1{font-family:Mont;font-weight:900;font-size:42px;line-height:1.05;margin:14px 0 10px}
.s-hero p{font-size:24px;opacity:.9}
.s-btn{display:inline-block;margin-top:26px;background:var(--wab);color:#fff;font-weight:800;font-size:24px;padding:18px 28px;border-radius:40px;box-shadow:0 10px 24px rgba(0,0,0,.25)}
.stars{margin-top:18px;color:#ffd23f;font-size:22px}.stars span{color:#fff;font-size:18px}
.s-sec h2{font-family:Mont;font-weight:900;font-size:32px;margin-bottom:18px}
.s-svcs{height:420px;padding:34px 26px;background:#fff}
.svc-grid{display:grid;grid-template-columns:1fr 1fr;gap:14px}
.svc{border-radius:20px;background:#f4f4f7;padding:20px 18px;height:132px}
.svc-n{font-weight:700;font-size:22px}.svc-p{font-weight:800;font-size:28px;color:var(--c2);margin-top:10px}
.s-gal{height:420px;padding:30px 26px;background:#fafafa}
.gal-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.gal{height:150px;border-radius:20px;display:flex;align-items:center;justify-content:center;font-size:70px}
.s-rev{height:330px;padding:30px 26px;background:#fff}
.rev{background:#f4f4f7;border-radius:18px;padding:18px;font-size:21px;margin-bottom:12px}.rev b{display:block;color:#f5b301;margin-top:6px}
.s-map{height:400px;padding:30px 26px;background:#fafafa}
.map{position:relative;height:220px;border-radius:20px;background:#e8f0e3;overflow:hidden}
.map i{position:absolute;background:#fff}.st1{left:0;right:0;top:90px;height:22px}.st2{top:0;bottom:0;left:180px;width:22px}.st3{top:0;bottom:0;left:340px;width:16px;transform:rotate(18deg)}
.pin{position:absolute;left:170px;top:30px;font-size:64px}
.addr{font-size:21px;margin-top:14px;font-weight:600}.addr small{font-weight:400;color:#555}
.s-foot{height:200px;background:var(--c1);display:flex;align-items:center;justify-content:center}
/* insta */
.ig{color:#111;font-family:Inter,'Noto Color Emoji';background:#fff;height:100%%}
.ig-top{display:flex;justify-content:space-between;padding:18px 26px;font-size:26px}
.ig-head{display:flex;align-items:center;gap:30px;padding:10px 26px}
.ig-av{width:130px;height:130px;border-radius:50%%;display:flex;align-items:center;justify-content:center;font-size:66px;background:#fff;box-shadow:0 0 0 5px #fff,0 0 0 9px #d62976}
.ig-stats{display:flex;gap:22px;text-align:center;font-size:19px}.ig-stats b{font-size:26px}
.ig-bio{padding:14px 26px;font-size:21px;line-height:1.4}
.ig-btns{display:flex;gap:10px;padding:0 26px 16px}.ig-btns span{flex:1;text-align:center;background:#efefef;border-radius:12px;padding:12px;font-weight:700;font-size:20px}
.ig-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:4px}
.ig-post{height:172px;display:flex;align-items:center;justify-content:center;font-size:60px}
.ban{position:absolute;inset:48px 0 0 0;z-index:5;background:rgba(10,10,14,.9);color:#fff;text-align:center;padding:200px 46px 0;font-size:34px}
.ban b{display:block;font-size:40px;margin:20px 0;font-family:Mont;font-weight:900}.ban p{font-size:24px;color:#bbb;line-height:1.4}
.ban-btn{margin-top:40px;display:inline-block;padding:16px 30px;border-radius:14px;background:#333;font-size:22px;color:#888}
.qbub{position:absolute;z-index:6;background:#fff;color:#111;font-weight:800;font-size:44px;padding:18px 30px;border-radius:40px;box-shadow:0 16px 40px rgba(0,0,0,.35)}
/* chat */
.wa{height:100%%;display:flex;flex-direction:column;background:#efeae2}
.wa-top{background:#075e54;color:#fff;display:flex;gap:16px;align-items:center;padding:16px 22px;font-size:24px}
.wa-top small{font-size:18px;opacity:.85}
.wa-av{width:64px;height:64px;border-radius:50%%;background:#d1d7db;display:flex;align-items:center;justify-content:center;font-size:36px}
.wa-body{flex:1;padding:26px 18px;display:flex;flex-direction:column;gap:16px;background-image:radial-gradient(rgba(0,0,0,.04) 2px,transparent 2px);background-size:26px 26px}
.msg{max-width:84%%;padding:16px 20px 30px;border-radius:20px;font-size:28px;color:#111;position:relative;box-shadow:0 2px 2px rgba(0,0,0,.1)}
.msg.in{background:#fff;align-self:flex-start;border-top-left-radius:4px}
.msg.out{background:#d9fdd3;align-self:flex-end;border-top-right-radius:4px}
.tm{position:absolute;right:14px;bottom:6px;font-size:16px;color:#667781}.tick{color:#53bdeb}
.wa-input{margin:14px;background:#fff;border-radius:40px;padding:20px 26px;font-size:24px;color:#888}
/* statement */
.stmt{position:absolute;left:40px;right:40px;top:290px;height:760px;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center}
.stmt-emo{font-size:210px;line-height:1.1}
.stmt-big{font-family:Mont;font-weight:900;line-height:1;margin-top:30px;text-transform:uppercase;text-shadow:0 8px 0 rgba(0,0,0,.3)}
.stmt-sub{font-size:50px;font-weight:700;margin-top:28px;color:#dfe3ff}
/* checklist */
.cklist{position:absolute;left:60px;right:60px;top:280px;height:770px;display:flex;flex-direction:column;justify-content:center;gap:26px}
.ck-title{font-family:Mont;font-weight:900;font-size:66px;text-transform:uppercase;margin-bottom:12px;text-align:center}
.ck{display:flex;align-items:center;gap:28px;background:rgba(255,255,255,.08);border:2px solid rgba(255,255,255,.12);border-radius:30px;padding:24px 28px;font-size:46px;font-weight:700}
.ck-ic{flex:none;width:80px;height:80px;border-radius:50%%;display:flex;align-items:center;justify-content:center;font-size:50px;font-weight:900}
.ck.ok .ck-ic{background:var(--wab);color:#fff}.ck.no .ck-ic{background:var(--dan);color:#fff}.ck.no span:last-child{text-decoration:line-through;text-decoration-color:rgba(255,77,94,.8);text-decoration-thickness:5px}
/* big number */
.bnwrap{position:absolute;left:0;right:0;top:300px;height:740px}
.bn{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center}
.bn-big{font-family:Mont;font-weight:900;line-height:1;letter-spacing:-.03em;text-shadow:0 10px 0 rgba(0,0,0,.3),0 0 60px rgba(255,210,63,.35)}
.bn-big sup{font-size:.4em;vertical-align:top}
.bn-sub{font-size:56px;font-weight:700;margin-top:24px}
.foot-in{position:absolute;left:0;right:0;top:1010px;text-align:center;font-size:26px;color:rgba(255,255,255,.6)}
/* steps */
.steps{position:absolute;left:70px;right:70px;top:300px;height:740px;display:flex;flex-direction:column;justify-content:center;gap:40px}
.st-line{position:absolute;left:62px;top:150px;bottom:150px;width:10px;border-radius:5px;background:rgba(255,255,255,.12)}
.st-bar{position:absolute;inset:0;background:linear-gradient(var(--sec),var(--wa));border-radius:5px;transform-origin:top}
.step{position:relative;display:flex;align-items:center;gap:34px;padding:26px;border-radius:32px;background:rgba(255,255,255,.06);border:2px solid rgba(255,255,255,.1)}
.step.on{background:rgba(123,97,255,.25);border-color:var(--pri)}
.step.off{opacity:.45}
.st-ic{flex:none;width:110px;height:110px;border-radius:50%%;background:#fff;display:flex;align-items:center;justify-content:center;font-size:60px}
.st-d{font-family:Mont;font-weight:900;font-size:50px;color:var(--acc)}.st-t{font-size:38px;font-weight:600;margin-top:6px}
/* price */
.price{position:absolute;left:50px;right:50px;top:300px;height:700px;display:flex;gap:30px;align-items:center}
.pc{position:relative;flex:1;border-radius:36px;padding:40px 28px;text-align:center;height:620px;display:flex;flex-direction:column;justify-content:center}
.pc.bad{background:rgba(255,77,94,.12);border:3px solid rgba(255,77,94,.6)}
.pc.good{background:linear-gradient(160deg,rgba(123,97,255,.55),rgba(43,217,254,.35));border:4px solid var(--acc);box-shadow:0 0 60px rgba(255,210,63,.3)}
.pc-h{font-family:Mont;font-weight:900;font-size:50px;text-transform:uppercase;margin-bottom:24px}
.pc-v{font-family:Mont;font-weight:900;font-size:64px;line-height:1.05}
.pc-v.em{font-size:120px}.pc-big{font-size:74px!important;margin-bottom:20px;white-space:nowrap}.pc-big sup{font-size:.5em}.pc-v2{font-family:Mont;font-weight:900;font-size:56px;color:#fff}.pc-v2 sup{font-size:.5em}
.pc-l{font-size:30px;font-weight:600;margin-top:16px;opacity:.9}
.pc-s{font-size:32px;margin-top:20px;color:#ffb3ba}
.strike{position:absolute;left:20px;right:20px;top:50%%;height:12px;background:var(--dan);transform:rotate(-14deg);transform-origin:left;border-radius:6px}
/* split */
.sp-t{position:absolute;top:1535px;width:460px;text-align:center;font-family:Mont;font-weight:900;font-size:50px}
.sp-t.bad{left:80px;color:var(--dan)}.sp-t.good{left:580px;color:var(--wa)}
/* cta */
.cta{position:absolute;inset:0}
.cta>*{position:absolute;left:50px;right:50px;text-align:center}
.cta-brand{top:255px;font-family:Mont;font-weight:800;font-size:40px;display:flex;gap:18px;justify-content:center;align-items:center}
.logo{position:relative;width:62px;height:62px;border-radius:50%%;background:linear-gradient(135deg,var(--pri),var(--sec));display:inline-block}
.logo i{position:absolute;left:-12px;top:22px;width:86px;height:18px;border:4px solid #fff;border-radius:50%%;transform:rotate(-20deg)}
.cta-h1{top:350px;font-family:Mont;font-weight:900;font-size:62px;white-space:nowrap;text-transform:uppercase;line-height:1}
.cta-free sup{font-size:.4em;vertical-align:top}.cta-free{top:450px;font-family:Mont;font-weight:900;font-size:172px;white-space:nowrap;line-height:1;color:var(--acc);text-shadow:0 12px 0 rgba(0,0,0,.3),0 0 80px rgba(255,210,63,.45)}
.cta-pay{top:690px;font-size:46px;font-weight:700;white-space:nowrap}.cta-pay sup{font-size:.55em}
.cta-chips{top:790px;display:flex;flex-wrap:wrap;gap:16px;justify-content:center}
.cta-chips span{background:rgba(255,255,255,.1);border:2px solid rgba(255,255,255,.18);border-radius:40px;padding:14px 26px;font-size:36px;font-weight:700}
.cta-btn{top:990px;left:90px;right:90px;background:var(--wab);border-radius:90px;padding:40px 0;font-family:Mont;font-weight:900;font-size:58px;box-shadow:0 20px 60px rgba(37,211,102,.5)}
.cta-hand{top:1060px;left:760px;right:auto;font-size:130px}
.cta-hint{top:1215px;font-size:40px;font-weight:600;color:#dfe3ff}.arrow{display:inline-block}
.cta-foot{top:1285px;font-size:26px;color:rgba(255,255,255,.55)}
"""


def main():
    sel = sys.argv[1:]
    for ad in ADS:
        if sel and not any(ad["id"].startswith(s) for s in sel):
            continue
        build_ad(ad)


if __name__ == "__main__":
    main()
