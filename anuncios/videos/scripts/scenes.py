"""Componentes visuais (HTML + timeline GSAP) usados pelos anúncios."""
import html
import json
import re

from ads import BRAND, SITES

W, H = 1080, 1920
TOP_LAYOUT = {"phone", "insta", "chat", "split", "gallery"}


# ---------------------------------------------------------------- helpers

def esc(s):
    return html.escape(s, quote=False)


def parse_marks(text):
    """'a *b* !c!' -> [(texto, estilo)], estilo em {None, 'em', 'danger'}"""
    out, style, buf = [], None, ""
    for ch in text:
        if ch in "*!" and (style is None or style == {"*": "em", "!": "danger"}[ch]):
            if buf:
                out.append((buf, style))
            buf = ""
            style = None if style else {"*": "em", "!": "danger"}[ch]
        else:
            buf += ch
    if buf:
        out.append((buf, style))
    return out


def rich(text):
    parts = []
    for t, s in parse_marks(text):
        t = esc(t)
        parts.append(f'<span class="{s}">{t}</span>' if s else t)
    return "".join(parts)


def plain(text):
    return "".join(t for t, _ in parse_marks(text))


def price_html(text):
    """'R$16/mês*' -> com sup do rodapé (se houver rodapé)."""
    t = esc(text)
    if t.endswith("*"):
        t = t[:-1] + ("<sup>*</sup>" if BRAND.get("price_footnote") else "")
    return t


def fit(text, width=960, maxsize=170, k=0.64):
    n = max(len(plain(text)), 1)
    return int(min(maxsize, width / (k * n)))


class TL:
    def __init__(self):
        self.js = []

    def ft(self, sel, frm, to, at):
        self.js.append(f"tl.fromTo({json.dumps(sel)}, {json.dumps(frm)}, {json.dumps(to)}, {at:.3f});")

    def to(self, sel, vars_, at):
        self.js.append(f"tl.to({json.dumps(sel)}, {json.dumps(vars_)}, {at:.3f});")

    def set(self, sel, vars_, at):
        self.js.append(f"tl.set({json.dumps(sel)}, {json.dumps(vars_)}, {at:.3f});")


def pop_in(tl, sel, at, dur=0.28, y=40, scale=0.85):
    tl.ft(sel, {"opacity": 0, "y": y, "scale": scale}, {"opacity": 1, "y": 0, "scale": 1, "duration": dur, "ease": "back.out(1.8)"}, at)


def pulse(tl, sel, at, until, period=0.9, amt=1.06):
    n = max(int((until - at) / period) - 1, 0)
    if n <= 0:
        return
    tl.ft(sel, {"scale": 1}, {"scale": amt, "duration": period / 2, "ease": "sine.inOut", "yoyo": True, "repeat": n * 2 - 1}, at)


# ---------------------------------------------------------------- site / phone

def site_html(key, pid, small=False):
    s = SITES[key]
    services = "".join(
        f'<div class="svc"><div class="svc-n">{esc(n)}</div><div class="svc-p">{esc(p)}</div></div>' for n, p in s["services"])
    gallery = "".join(
        f'<div class="gal" style="background:linear-gradient(135deg,{s["c2"]}cc,{s["c1"]})"><span class="emo">{e}</span></div>' for e in s["gallery"])
    return f"""
<div class="site" id="{pid}-site" style="--c1:{s['c1']};--c2:{s['c2']}">
  <div class="s-sec s-nav" id="{pid}-sec0"><span class="emo">{s['emoji']}</span><b>{esc(s['name'])}</b><span class="burger">☰</span></div>
  <div class="s-sec s-hero" id="{pid}-sec1">
    <div class="hero-emo emo">{s['emoji']}</div>
    <h1>{esc(s['name'])}</h1>
    <p>{esc(s['tagline'])}</p>
    <div class="s-btn" id="{pid}-herobtn">💬 Agendar pelo WhatsApp</div>
    <div class="stars">★★★★★ <span>4,9 • 128 avaliações</span></div>
  </div>
  <div class="s-sec s-svcs" id="{pid}-sec2"><h2>Serviços</h2><div class="svc-grid">{services}</div></div>
  <div class="s-sec s-gal" id="{pid}-sec3"><h2>Galeria</h2><div class="gal-grid">{gallery}</div></div>
  <div class="s-sec s-rev" id="{pid}-sec4"><h2>O que dizem os clientes</h2>
    <div class="rev">“Atendimento impecável, recomendo demais!” <b>★★★★★</b></div>
    <div class="rev">“Agendei pelo site em 1 minuto.” <b>★★★★★</b></div></div>
  <div class="s-sec s-map" id="{pid}-sec5"><h2>Onde estamos</h2>
    <div class="map"><i class="st1"></i><i class="st2"></i><i class="st3"></i><span class="pin emo">📍</span></div>
    <div class="addr">{esc(s['addr'])}<br><small>{esc(s['hours'])}</small></div></div>
  <div class="s-sec s-foot" id="{pid}-sec6"><div class="s-btn">💬 Chamar no WhatsApp</div></div>
</div>"""


SITE_SCROLL = 1040  # distância de rolagem do site dentro do celular


def phone_wrap(pid, inner, x, y, scale=1.0, rot=0, label=True, extra=""):
    lab = '<div class="ex-label">EXEMPLO ILUSTRATIVO</div>' if label else ""
    return f"""
<div class="phone" data-layout-ignore id="{pid}" style="left:{x}px;top:{y}px;transform:scale({scale}) rotate({rot}deg)">
  <div class="screen"><div class="status"><span>9:41</span><span>▮▮▮ 5G ▰</span></div>
    <div class="viewport" id="{pid}-vp">{inner}</div>{extra}
  </div>{lab}
</div>"""


def whats_fab(pid):
    return f'<div class="fab" id="{pid}-fab">💬</div>'


def insta_html(pid, sc):
    posts = "".join(
        f'<div class="ig-post" style="background:linear-gradient(135deg,hsl({(i*47)%360},55%,62%),hsl({(i*47+60)%360},60%,40%))"><span class="emo">{e}</span></div>'
        for i, e in enumerate(sc["posts"] * 2))
    return f"""
<div class="ig" id="{pid}-ig">
  <div class="ig-top"><b>@{esc(sc['handle'])}</b><span>⊕ ☰</span></div>
  <div class="ig-head"><div class="ig-av emo">{sc['emoji']}</div>
    <div class="ig-stats"><div><b>248</b><br>posts</div><div><b>{esc(sc['followers'])}</b><br>seguidores</div><div><b>312</b><br>seguindo</div></div></div>
  <div class="ig-bio"><b>{esc(sc['name'])}</b><br>✨ Chama no direct pra saber o preço<br>📍 Pergunta o endereço no direct</div>
  <div class="ig-btns"><span>Seguir</span><span>Mensagem</span></div>
  <div class="ig-grid" id="{pid}-grid">{posts}</div>
</div>"""


# ---------------------------------------------------------------- cenas

class Ctx:
    """Dá acesso aos tempos dos beats de uma cena."""

    def __init__(self, beats):
        self.beats = beats  # lista de dicts com start, speech, end
        self.t0 = beats[0]["start"]
        self.t1 = beats[-1]["end"]

    def T(self, spec):
        if isinstance(spec, (int, float)):
            return self.t0 + spec
        b, f = spec.split(":")
        bt = self.beats[int(b)]
        return bt["start"] + float(f) * bt["speech"]


def scene_hook(c, sc, sid, tl, sfx, beat):
    lines = sc["lines"]
    # sincroniza cada linha com a 1ª palavra correspondente
    words = beat["words"]
    norm = lambda s: re.sub(r"[^\wà-úÀ-Ú$]", "", plain(s).lower())
    idx, times = 0, []
    for li, line in enumerate(lines):
        first = norm(line.split()[0])
        t = None
        for j in range(idx, len(words)):
            if norm(words[j]["text"]) == first or (first and norm(words[j]["text"]).startswith(first)):
                t, idx = words[j]["t"], j + 1
                break
        if t is None:
            t = c.t0 + (li / len(lines)) * beat["speech"]
        times.append(0 if li == 0 else max(t - 0.04, 0))
    tl.set(f"#{sid}-shake", {"x": 0, "skewX": 0}, max(c.t0 - 0.01, 0))
    sizes = [fit(l, 980, 175 if "!" in l or "*" in l else 120, 0.8) for l in lines]
    total_h = sum(s * 1.08 for s in sizes) + (220 if sc.get("emoji") else 0)
    if total_h > 880:  # cabe na área segura do Feed 4:5 (y 300–1250)
        k = 880 / total_h
        sizes = [int(s * k) for s in sizes]
        total_h = 880
    y = max(330, 775 - total_h / 2)
    h = []
    if sc.get("emoji"):
        h.append(f'<div class="hook-emo emo" id="{sid}-emo" style="top:{y:.0f}px">{sc["emoji"]}</div>')
        tl.ft(f"#{sid}-emo", {"scale": 0.2, "rotation": -30}, {"scale": 1, "rotation": 0, "duration": 0.4, "ease": "back.out(2)"}, c.t0 if c.t0 > 0 else 0)
        y += 220
    for i, (line, size) in enumerate(zip(lines, sizes)):
        lid = f"{sid}-l{i}"
        h.append(f'<div class="hook-line" id="{lid}" style="top:{y:.0f}px;font-size:{size}px">{rich(line)}</div>')
        at = c.t0 + times[i] if i else c.t0
        if i == 0:
            tl.ft(f"#{lid}", {"scale": 1.25}, {"scale": 1, "duration": 0.35, "ease": "power3.out"}, at)
        else:
            tl.ft(f"#{lid}", {"opacity": 0, "scale": 1.7}, {"opacity": 1, "scale": 1, "duration": 0.16, "ease": "power4.out"}, at)
            big = "!" in line or "*" in line
            if big:
                tl.ft(f"#{sid}-shake", {"x": -14}, {"x": 0, "duration": 0.25, "ease": "elastic.out(1,0.3)"}, at + 0.05)
                sfx.append(("impact" if "!" in line else "pop", at, 0.55 if "!" in line else 0.6))
        y += size * 1.08
    if sc.get("glitch"):
        for k in range(10):
            at = c.t0 + 0.05 + k * 0.13
            tl.set(f"#{sid}-shake", {"x": [-18, 14, -8, 20, 0][k % 5], "skewX": [8, -6, 0, 10, 0][k % 5]}, at)
        tl.set(f"#{sid}-shake", {"x": 0, "skewX": 0}, c.t0 + 1.4)
        sfx.append(("glitch", c.t0 + 0.05, 0.5))
    flash = BRAND["danger"] if sc.get("flash") == "danger" else BRAND["primary"]
    stop = ""
    if sc.get("stop"):
        stop = f'<div class="stop-oct" id="{sid}-stop">✋</div>'
        tl.ft(f"#{sid}-stop", {"scale": 1.4, "opacity": 0.9}, {"scale": 1, "opacity": 0.16, "duration": 0.6}, c.t0)
    sfx.append(("impact", c.t0, 0.9))
    tl.ft(f"#{sid}-flash", {"opacity": 0.95}, {"opacity": 0, "duration": 0.7, "ease": "power2.in"}, c.t0)
    return f'<div class="flash" id="{sid}-flash" style="background:{flash}"></div>{stop}<div class="shake" id="{sid}-shake">{"".join(h)}</div>'


def scene_search(c, sc, sid, tl, sfx, beat):
    q = sc["query"]
    chars = "".join(f'<span class="ch" id="{sid}-c{i}">{esc(ch)}</span>' for i, ch in enumerate(q))
    t_type = c.t0 + 0.25
    dt = min(0.045, (beat["speech"] * 0.45) / max(len(q), 1))
    for i in range(len(q)):
        tl.set(f"#{sid}-c{i}", {"opacity": 1}, t_type + i * dt)
        if i % 3 == 0:
            sfx.append(("click", t_type + i * dt, 0.35))
    res = []
    for i, r in enumerate(sc.get("results", [])):
        chips = "".join(f"<span>{esc(ch)}</span>" for ch in r.get("chips", []))
        tag = '<div class="tag-comp">SEU CONCORRENTE</div>' if r.get("hl") else ""
        res.append(f'<div class="res{" hl" if r.get("hl") else ""}" id="{sid}-r{i}">{tag}<div class="r-url">🌐 {esc(r["url"])}</div>'
                   f'<div class="r-title">{esc(r["title"])}</div><div class="r-stars">★ {esc(r["stars"])} · Aberto agora</div><div class="r-chips">{chips}</div></div>')
        at = c.T(sc.get("show_results", "0:0.5")) + i * 0.35
        pop_in(tl, f"#{sid}-r{i}", at)
        sfx.append(("pop", at, 0.5))
    if sc.get("missing"):
        empty = not sc.get("results")
        txt = (f'<div class="miss-big">🔍 {esc(sc["missing"])}</div>' if empty else
               f'<div class="miss-name">{esc(sc["missing"])}</div><div class="miss-x">❌ não encontrada</div>')
        res.append(f'<div class="res miss" id="{sid}-miss">{txt}</div>')
        at = c.T(sc.get("show_missing", "0:0.7"))
        pop_in(tl, f"#{sid}-miss", at, y=0, scale=1.3)
        tl.ft(f"#{sid}-miss", {"x": -18}, {"x": 0, "duration": 0.5, "ease": "elastic.out(1,0.25)"}, at + 0.2)
        sfx.append(("buzz", at + 0.05, 0.6))
    pop_in(tl, f"#{sid}-card", c.t0, y=80, scale=0.95)
    return f"""<div class="search" id="{sid}-card">
  <div class="sbar"><span class="mag">🔍</span><div class="q">{chars}<span class="caret">|</span></div></div>
  <div class="sres">{''.join(res)}</div></div>"""


def scene_phone(c, sc, sid, tl, sfx, beat):
    pid = f"{sid}-ph"
    extra = whats_fab(pid)
    if sc.get("tap"):
        extra += f'<div class="notif" id="{pid}-notif"><span class="emo">💬</span><div><b>Nova mensagem</b><br>“Oi! Vi seu site e quero agendar 😊”</div></div>'
    html_ = phone_wrap(pid, site_html(sc["site"], pid), 260, 480, extra=extra)
    html_ += f'<div class="finger emo" id="{pid}-finger">👆</div>' if sc.get("tap") else ""
    tl.ft(f"#{pid}", {"y": 260, "opacity": 0, "rotation": 6}, {"y": 0, "opacity": 1, "rotation": 0, "duration": 0.45, "ease": "power3.out"}, c.t0)
    pulse(tl, f"#{pid}-fab", c.t0 + 0.5, c.t1, 0.8, 1.15)
    if sc.get("build"):
        n = 7
        span = beat["speech"] * 0.9
        for i in range(n):
            at = c.t0 + 0.3 + i * span / n
            tl.ft(f"#{pid}-sec{i}", {"opacity": 0, "x": 120 if i % 2 else -120}, {"opacity": 1, "x": 0, "duration": 0.3, "ease": "back.out(1.6)"}, at)
            sfx.append(("pop", at, 0.45))
        tl.ft(f"#{pid}-site", {"y": 0}, {"y": -SITE_SCROLL * 0.75, "duration": span * 0.6, "ease": "power1.inOut"}, c.t0 + 0.3 + span * 0.45)
    elif sc.get("scroll", True):
        d = c.t1 - c.t0
        tl.ft(f"#{pid}-site", {"y": 0}, {"y": -SITE_SCROLL, "duration": d * 0.8, "ease": "power1.inOut"}, c.t0 + d * 0.1)
    if sc.get("tap"):
        at = c.T(sc["tap"])
        tl.ft(f"#{pid}-finger", {"opacity": 0, "x": 240, "y": 300}, {"opacity": 1, "x": 0, "y": 0, "duration": 0.45, "ease": "power2.out"}, at - 0.5)
        tl.ft(f"#{pid}-finger", {"scale": 1}, {"scale": 0.8, "duration": 0.1, "yoyo": True, "repeat": 1}, at)
        sfx.append(("click", at, 0.8))
        pop_in(tl, f"#{pid}-notif", at + 0.25, y=-80, scale=0.9)
        sfx.append(("ding", at + 0.25, 0.6))
    return html_


def scene_insta(c, sc, sid, tl, sfx, beat):
    pid = f"{sid}-ph"
    extra = ""
    if sc.get("banned"):
        extra = f"""<div class="ban" id="{pid}-ban"><div class="emo" style="font-size:110px">⚠️</div><b>Sua conta foi desativada</b>
        <p>Você não tem mais acesso a este perfil, às suas fotos e aos seus seguidores.</p><div class="ban-btn">Solicitar análise</div></div>"""
    out = phone_wrap(pid, insta_html(pid, sc), 260, 480, label=False, extra=extra)
    tl.ft(f"#{pid}", {"y": 260, "opacity": 0}, {"y": 0, "opacity": 1, "duration": 0.45, "ease": "power3.out"}, c.t0)
    if sc.get("scroll"):
        tl.ft(f"#{pid}-ig", {"y": 0}, {"y": -380, "duration": (c.t1 - c.t0) * 0.8, "ease": "power1.inOut"}, c.t0 + 0.4)
        qs = ["Preço? 🤔", "Endereço? 📍", "Horário? 🕘"]
        for i, q in enumerate(qs):
            out += f'<div class="qbub" id="{sid}-q{i}" style="left:{[60, 640, 90][i]}px;top:{[620, 860, 1180][i]}px">{q}</div>'
            at = c.t0 + 0.8 + i * (c.t1 - c.t0 - 1.2) / 3
            pop_in(tl, f"#{sid}-q{i}", at)
            sfx.append(("pop", at, 0.5))
    if sc.get("banned"):
        at = c.T(sc["banned"])
        for k in range(8):
            tl.set(f"#{pid}", {"x": [-16, 12, -6, 18, -10, 6, 0, 0][k], "skewX": [6, -4, 0, 8, -3, 0, 0, 0][k]}, at + k * 0.06)
        tl.ft(f"#{pid}-ig", {"filter": "grayscale(0) blur(0px)"}, {"filter": "grayscale(1) blur(6px)", "duration": 0.4}, at)
        pop_in(tl, f"#{pid}-ban", at + 0.15, y=0, scale=1.2)
        sfx.append(("glitch", at, 0.7))
        sfx.append(("buzz", at + 0.2, 0.5))
    return out


def scene_chat(c, sc, sid, tl, sfx, beat):
    pid = f"{sid}-ph"
    msgs = []
    for i, (who, text, at_s) in enumerate(sc["msgs"]):
        tick = ' <span class="tick">✓✓</span>' if who == "out" else ""
        msgs.append(f'<div class="msg {who}" id="{sid}-m{i}">{esc(text)}<span class="tm">10:4{i}{tick}</span></div>')
        at = max(c.T(at_s), c.t0 + 0.35)
        pop_in(tl, f"#{sid}-m{i}", at, y=30, scale=0.8)
        sfx.append(("ding" if who == "in" else "pop", at, 0.35))
    inner = f"""<div class="wa"><div class="wa-top"><span class="wa-av emo">👤</span><div><b>{esc(sc['title'])}</b><br><small>online</small></div></div>
      <div class="wa-body">{''.join(msgs)}</div><div class="wa-input">Mensagem</div></div>"""
    out = phone_wrap(f"{pid}", inner, 260, 480, label=False)
    tl.ft(f"#{pid}", {"y": 260, "opacity": 0}, {"y": 0, "opacity": 1, "duration": 0.4, "ease": "power3.out"}, c.t0)
    return out


def scene_statement(c, sc, sid, tl, sfx, beat):
    size = fit(sc["big"], 980, 150, 0.8)
    pop_in(tl, f"#{sid}-emo", c.t0, y=-120, scale=0.3)
    tl.ft(f"#{sid}-big", {"opacity": 0, "scale": 1.6}, {"opacity": 1, "scale": 1, "duration": 0.2, "ease": "power4.out"}, c.t0 + 0.15)
    pop_in(tl, f"#{sid}-sub", c.t0 + 0.45)
    tl.ft(f"#{sid}-emo", {"rotation": -8}, {"rotation": 8, "duration": 0.6, "yoyo": True, "repeat": max(int((c.t1 - c.t0) / 0.6) - 2, 1), "ease": "sine.inOut"}, c.t0 + 0.3)
    sfx.append(("impact" if "!" in sc["big"] else "pop", c.t0 + 0.15, 0.6))
    return f"""<div class="stmt"><div class="stmt-emo emo" id="{sid}-emo">{sc['emoji']}</div>
      <div class="stmt-big" id="{sid}-big" style="font-size:{size}px">{rich(sc['big'])}</div>
      <div class="stmt-sub" id="{sid}-sub">{rich(sc['sub'])}</div></div>"""


def scene_checklist(c, sc, sid, tl, sfx, beat):
    items = []
    n = len(sc["items"])
    span = (c.t1 - c.t0) * 0.85
    for i, (kind, text) in enumerate(sc["items"]):
        icon = "✓" if kind == "ok" else "✕"
        items.append(f'<div class="ck {kind}" id="{sid}-i{i}"><span class="ck-ic">{icon}</span><span>{esc(text)}</span></div>')
        at = c.t0 + 0.35 + i * span / n
        tl.ft(f"#{sid}-i{i}", {"opacity": 0, "x": -140}, {"opacity": 1, "x": 0, "duration": 0.3, "ease": "back.out(1.7)"}, at)
        sfx.append(("pop", at, 0.55))
    pop_in(tl, f"#{sid}-t", c.t0, y=-40)
    return f'<div class="cklist"><div class="ck-title" id="{sid}-t">{esc(sc["title"])}</div>{"".join(items)}</div>'


def scene_bignum(c, sc, sid, tl, sfx, beat):
    out = []
    states = sc["states"]
    tone = "danger" if sc.get("tone") == "danger" else "em"
    for i, (at_s, big, sub) in enumerate(states):
        at = max(c.T(at_s), c.t0)
        out.append(f'<div class="bn" id="{sid}-s{i}"><div class="bn-big {tone}" style="font-size:{fit(big, 980, 230, 0.74)}px">{price_html(big)}</div><div class="bn-sub">{esc(sub)}</div></div>')
        if i > 0:
            tl.to(f"#{sid}-s{i-1}", {"opacity": 0, "y": -120, "scale": 0.6, "duration": 0.18}, at - 0.02)
        tl.ft(f"#{sid}-s{i}", {"opacity": 0, "scale": 1.8}, {"opacity": 1, "scale": 1, "duration": 0.22, "ease": "power4.out"}, at)
        sfx.append(("cash" if "R$" in big else "pop", at, 0.6))
    foot = ""
    if any(b.endswith("*") for _, b, _ in states) and BRAND.get("price_footnote"):
        foot = f'<div class="foot-in">{esc(BRAND["price_footnote"])}</div>'
    return f'<div class="bnwrap">{"".join(out)}</div>{foot}'


STEPS = [("📩", "Passo 1", "Você me manda fotos, serviços e contatos"),
         ("🛠️", "Passo 2", "Eu monto sua página completa"),
         ("👀", "Passo 3", "Você vê a prévia e aprova")]


def scene_steps(c, sc, sid, tl, sfx, beat):
    act = sc.get("active", 0)
    rows = []
    for i, (e, d, t) in enumerate(STEPS):
        cls = "on" if i <= act else "off"
        rows.append(f'<div class="step {cls}" id="{sid}-st{i}"><div class="st-ic emo">{e}</div><div><div class="st-d">{d}</div><div class="st-t">{esc(t)}</div></div></div>')
        pop_in(tl, f"#{sid}-st{i}", c.t0 + 0.1 + i * 0.18, y=60)
    tl.ft(f"#{sid}-bar", {"scaleY": 0}, {"scaleY": [0.12, 0.55, 1][act], "duration": 0.9, "ease": "power2.out"}, c.t0 + 0.4)
    tl.ft(f"#{sid}-st{act}", {"scale": 1}, {"scale": 1.05, "duration": 0.5, "yoyo": True, "repeat": 3, "ease": "sine.inOut"}, c.t0 + 0.9)
    sfx.append(("pop", c.t0 + 0.1, 0.4))
    return f'<div class="steps"><div class="st-line"><div class="st-bar" id="{sid}-bar"></div></div>{"".join(rows)}</div>'


def scene_price(c, sc, sid, tl, sfx, beat):
    d = c.t1 - c.t0
    pop_in(tl, f"#{sid}-a", c.t0, y=60)
    tl.ft(f"#{sid}-strike", {"scaleX": 0}, {"scaleX": 1, "duration": 0.3, "ease": "power2.out"}, c.t0 + d * 0.22)
    sfx.append(("buzz", c.t0 + d * 0.22, 0.4))
    pop_in(tl, f"#{sid}-b", c.t0 + d * 0.3, y=60, scale=0.7)
    sfx.append(("cash", c.t0 + d * 0.3, 0.6))
    pulse(tl, f"#{sid}-b", c.t0 + d * 0.3 + 0.4, c.t1, 1.0, 1.03)
    foot = f'<div class="foot-in">{esc(BRAND["price_footnote"])}</div>' if BRAND.get("price_footnote") else ""
    return f"""<div class="price">
  <div class="pc bad" id="{sid}-a"><div class="pc-h">Agência</div><div class="pc-v">R$ 2.000<br>a R$ 5.000</div><div class="pc-s">+ manutenção mensal</div><div class="strike" id="{sid}-strike"></div></div>
  <div class="pc good" id="{sid}-b"><div class="pc-h">Comigo</div><div class="pc-v em pc-big">{price_html('R$16/mês*')}</div>
    <div class="pc-l">✓ Página completa</div><div class="pc-l">✓ Botão do WhatsApp</div><div class="pc-l">✓ Prévia antes de decidir</div></div>
</div>{foot}"""


def scene_split(c, sc, sid, tl, sfx, beat):
    lp = f"{sid}-L"
    rp = f"{sid}-R"
    messy = dict(handle="clinica.sorriso", name="Clínica", emoji="🦷", followers="312", posts=["📷", "🦷", "📄", "🗓️", "📷", "😁", "📄", "📷", "🦷"])
    left = phone_wrap(lp, insta_html(lp, messy), 30, 490, scale=0.82, label=False)
    right = phone_wrap(rp, site_html(sc["right"]["site"], rp), 530, 490, scale=0.82)
    tl.ft(f"#{lp}", {"x": -300, "opacity": 0}, {"x": 0, "opacity": 1, "duration": 0.4, "ease": "power3.out"}, c.t0)
    tl.ft(f"#{rp}", {"x": 300, "opacity": 0}, {"x": 0, "opacity": 1, "duration": 0.4, "ease": "power3.out"}, c.t0 + 0.15)
    d = c.t1 - c.t0
    tl.to(f"#{lp}", {"opacity": 0.45, "filter": "grayscale(1)", "duration": 0.4}, c.t0 + d * 0.35)
    tl.ft(f"#{rp}", {"scale": 0.82}, {"scale": 0.88, "duration": 0.4, "ease": "back.out(2)"}, c.t0 + d * 0.35)
    tl.ft(f"#{rp}-site", {"y": 0}, {"y": -SITE_SCROLL * 0.6, "duration": d * 0.6, "ease": "power1.inOut"}, c.t0 + d * 0.35)
    pop_in(tl, f"#{sid}-lt", c.t0 + 0.3)
    pop_in(tl, f"#{sid}-rt", c.t0 + 0.45)
    sfx.append(("buzz", c.t0 + d * 0.35, 0.35))
    sfx.append(("ding", c.t0 + d * 0.38, 0.4))
    return (left + right + f'<div class="sp-t bad" id="{sid}-lt">✕ {esc(sc["left"]["title"])}</div>'
            f'<div class="sp-t good" id="{sid}-rt">✓ {esc(sc["right"]["title"])}</div>')


def scene_gallery(c, sc, sid, tl, sfx, beat):
    out = []
    pos = [(-300, -8, 0.6), (300, 8, 0.6), (0, 0, 0.74)]
    for i, (key, (dx, rot, s)) in enumerate(zip(sc["sites"], pos)):
        pid = f"{sid}-g{i}"
        out.append(phone_wrap(pid, site_html(key, pid), 260 + dx, 470, scale=s, rot=rot, label=(i == 2)))
        tl.ft(f"#{pid}", {"y": 400, "opacity": 0}, {"y": 0, "opacity": 1, "duration": 0.45, "ease": "back.out(1.4)"}, c.t0 + i * 0.2)
        tl.ft(f"#{pid}-site", {"y": 0}, {"y": -SITE_SCROLL * 0.7, "duration": (c.t1 - c.t0) * 0.8, "ease": "power1.inOut"}, c.t0 + 0.6)
        sfx.append(("pop", c.t0 + i * 0.2, 0.4))
    return "".join(out)


def scene_cta(c, sc, sid, tl, sfx, beat):
    t = c.t0
    seq = [f"#{sid}-brand", f"#{sid}-h1", None, f"#{sid}-pay", f"#{sid}-chips", f"#{sid}-btn", f"#{sid}-hint"]
    for i, s in enumerate(seq):
        if s:
            pop_in(tl, s, t + 0.05 + i * 0.12, y=50)
    tl.ft(f"#{sid}-free", {"scale": 2.2, "opacity": 0}, {"scale": 1, "opacity": 1, "duration": 0.3, "ease": "power4.out"}, t + 0.29)
    pulse(tl, f"#{sid}-btn", t + 1.1, c.t1, 0.9, 1.06)
    tl.ft(f"#{sid}-hand", {"opacity": 0, "y": 160}, {"opacity": 1, "y": 0, "duration": 0.4}, t + 1.0)
    n = max(int((c.t1 - t - 1.6) / 0.9), 1)
    tl.ft(f"#{sid}-hand", {"scale": 1}, {"scale": 0.82, "duration": 0.45, "yoyo": True, "repeat": n * 2 - 1, "ease": "sine.inOut"}, t + 1.4)
    tl.ft(f"#{sid}-arrow", {"y": 0}, {"y": 22, "duration": 0.45, "yoyo": True, "repeat": n * 2 - 1, "ease": "sine.inOut"}, t + 1.2)
    sfx.append(("impact", t + 0.29, 0.6))
    sfx.append(("ding", t + 1.1, 0.5))
    foot = f'<div class="cta-foot">{esc(BRAND["price_footnote"])}</div>' if BRAND.get("price_footnote") else ""
    return f"""<div class="cta">
  <div class="cta-brand" id="{sid}-brand"><span class="logo"><i></i></span>{esc(BRAND['name'])}</div>
  <div class="cta-h1" id="{sid}-h1">Seu site profissional</div>
  <div class="cta-free" id="{sid}-free">{price_html('R$16/mês*')}</div>
  <div class="cta-pay" id="{sid}-pay">Página completa com <span class="em">botão do WhatsApp</span></div>
  <div class="cta-chips" id="{sid}-chips"><span>👀 Prévia antes de decidir</span><span>📱 Feito pro celular</span></div>
  <div class="cta-btn" id="{sid}-btn">💬 Chamar no WhatsApp</div>
  <div class="cta-hand emo" id="{sid}-hand">👆</div>
  <div class="cta-hint" id="{sid}-hint"><span id="{sid}-arrow" class="arrow">👇</span> Toque em <b>“Enviar mensagem”</b></div>
  {foot}
</div>"""


SCENES = dict(hook=scene_hook, search=scene_search, phone=scene_phone, insta=scene_insta, chat=scene_chat,
              statement=scene_statement, checklist=scene_checklist, bignum=scene_bignum, steps=scene_steps,
              price=scene_price, split=scene_split, gallery=scene_gallery, cta=scene_cta)


def badge(sid, n, layout, tl, at):
    top = 495 if layout == "top" else 120
    pop_in(tl, f"#{sid}-badge", at, y=0, scale=0.2)
    return f'<div class="badge" id="{sid}-badge" style="top:{top}px">{esc(n)}</div>'
