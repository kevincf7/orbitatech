"""Gera ROTEIROS.md a partir de build/*/script.json (rode depois do build.py)."""
import glob, json, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
out = ["# Roteiros dos anúncios\n", "Gerado automaticamente por `scripts/roteiros.py`. Os tempos são o início de cada fala.\n"]
for f in sorted(glob.glob(os.path.join(ROOT, "build/*/script.json"))):
    d = json.load(open(f))
    out.append(f"\n## {d['id']}  ({d['duration']:.0f}s)\n")
    out.append(f"- **Nível de consciência:** {d['awareness']}\n- **Ângulo:** {d['angle']}\n- **Gancho base:** {d['hook']}\n- **Voz:** {d['voice']} · **Trilha:** {d['music']}\n")
    out.append("\n| Tempo | Fala |\n|---|---|\n")
    for b in d["beats"]:
        out.append(f"| {b['t']:.1f}s | {b['text']} |\n")
open(os.path.join(ROOT, "ROTEIROS.md"), "w").write("".join(out))
print("ok")
