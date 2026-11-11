#!/usr/bin/env bash
# Tira um quadro no meio de cada cena de um anúncio já gerado: scripts/snap.sh build/<id>
set -e
cd "$1"
ts=$(python3 -c "
import re
h=open('index.html').read()
out=[]
for m in re.finditer(r'class=\"clip scene[^\"]*\" id=\"s\d+\" data-start=\"([\d.]+)\" data-duration=\"([\d.]+)\"',h):
    s,d=float(m.group(1)),float(m.group(2)); out.append(round(s+d*0.75,2))
print(','.join(map(str,out)))")
npx --prefix "$(dirname "$0")/.." hyperframes snapshot --at "$ts" 2>&1 | grep contact-sheet | awk '{print $1}'
