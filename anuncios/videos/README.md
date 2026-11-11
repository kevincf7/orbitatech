# Anúncios em vídeo 9:16: site profissional por R$16/mês para empresas locais

São 12 anúncios verticais (1080×1920, 30 fps, de 17 a 37 s), feitos com [HyperFrames](https://github.com/heygen-com/hyperframes).
Cada um combina um **ângulo** e um **gancho** das planilhas de referência e mira um **nível de consciência** diferente.

Os vídeos prontos ficam em `out/`. Os roteiros completos, com tempos, estão em [`ROTEIROS.md`](ROTEIROS.md).

| # | Arquivo | Nível de consciência | Ângulo | Gancho | Duração |
|---|---|---|---|---|---|
| 1 | `01-custo-oculto.mp4` | Inconsciente | Custo oculto | "Você está perdendo cliente todo dia… e nem percebe." | 28 s |
| 2 | `02-pare-de-rolar.mp4` | Inconsciente | Pattern interrupt | "Para de rolar e olha isso: pra internet, a sua empresa não existe." | 24 s |
| 3 | `03-erro-invisivel.mp4` | Consciente do problema | Erro invisível | "Você está fazendo isso errado há anos…" | 34 s |
| 4 | `04-se-o-instagram-sumisse.mp4` | Consciente do problema | Medo / consequência | "Se o Instagram da sua empresa sumisse amanhã… todo, todo." | 29 s |
| 5 | `05-3-motivos-concorrente.mp4` | Consciente do problema | Comparação social | "3 motivos pro cliente escolher o seu concorrente…" | 37 s |
| 6 | `06-verdade-preco-site.mp4` | Consciente da solução | Mito / crença falsa | "A verdade sobre o preço de um site que nenhuma agência te conta." | 33 s |
| 7 | `07-do-zero-ao-site.mp4` | Consciente da solução | Demonstração (3 passos) | "Do zero a um site profissional. Olha só como funciona." | 31 s |
| 8 | `08-sem-gastar-fortuna.mp4` | Consciente da solução | Sem o sacrifício esperado | "Você não precisa gastar uma fortuna pra ter um site profissional." | 18 s |
| 9 | `09-qual-a-pegadinha.mp4` | Consciente do produto | Objeção + transparência | "Site profissional por R$16/mês? Qual é a pegadinha?" | 32 s |
| 10 | `10-16-reais-por-mes.mp4` | Consciente do produto | Custo por dia | "Site profissional por R$16 por mês. Sim… dezesseis." | 20 s |
| 11 | `11-nao-e-pra-voce.mp4` | Totalmente consciente | Anti-venda / qualificação | "Não me chama se a sua empresa já tem cliente demais." | 27 s |
| 12 | `12-a-um-passo.mp4` | Totalmente consciente | Simplicidade | "Você está a um passo de colocar a sua empresa na internet." | 18 s |

Regras aplicadas em todos os vídeos:

- A voz começa no quadro 0 e o texto do gancho já aparece no primeiro quadro, com flash e impacto sonoro.
- Os textos ficam dentro da área segura do Feed 4:5 e fora dos ~35% de baixo, onde fica a interface dos Reels.
- A oferta é uma só: site profissional por **R$16/mês**. Os vídeos não falam em "grátis", portfólio, plataforma ou afiliação; o motivo do preço fica para a conversa no WhatsApp.
- A copy segue o manual do Desafio 10K: o preço aparece como único custo, "sem surpresa", e a redução de risco é a prévia ("você vê o site pronto antes de decidir").
- Os vídeos prometem só: página completa com botão do WhatsApp e prévia antes de decidir. Não citam prazo de entrega nem número de ajustes, e não há escassez inventada.
- O CTA final pede para tocar em "Enviar mensagem", o botão do anúncio de clique para o WhatsApp.

## Como editar e gerar de novo

Pré-requisitos: Node 22+, Python 3 com `edge-tts soundfile scipy numpy` (e `kokoro-onnx`, só para a estimativa de reserva dos tempos), ffmpeg e Chrome. A narração precisa de acesso a `speech.platform.bing.com` (no ambiente de nuvem, o ambiente `principal-videos-tts` já libera esse host).

```bash
cd videos
npm install                       # hyperframes, gsap e fontes
python3 scripts/audio_synth.py    # trilhas e efeitos originais (assets/audio)
python3 scripts/build.py          # voz, legendas, cenas e mixagem (build/<id>)
scripts/render.sh                 # MP4 em out/ (ou: scripts/render.sh 03 07)
python3 scripts/roteiros.py       # atualiza ROTEIROS.md
```

- **Textos e cenas:** edite `scripts/ads.py`. `*palavra*` destaca em amarelo e `!palavra!` em vermelho.
  Cada item de `beats` é uma fala, e `scene` define o visual (hook, search, phone, insta, chat, statement,
  checklist, bignum, steps, price, split, gallery, cta).
- **Identidade visual:** em `BRAND`, no topo de `scripts/ads.py`, ficam nome, cores e o rodapé do preço.
  Use `price_footnote: None` para remover o asterisco.
- **Narração:** Edge TTS com a voz do canal (`pt-BR-AntonioNeural`, `+15%`), igual ao `narrar.py` do repositório videos-remotion: cada frase é narrada separadamente, sem o silêncio das pontas, e as frases são coladas com 0,1 s de pausa (0,22 s depois de pergunta). As legendas e os ganchos usam o tempo exato de cada palavra devolvido pelo Edge.
- **Pronúncia:** na tabela `PRON` de `scripts/build.py`, os valores em reais e os números são falados por extenso; a legenda continua com "R$16/mês".
- **Prévia de quadros:** `scripts/snap.sh build/<id>` gera uma folha de contato no meio de cada cena.

## Pendências

- A identidade visual (nome "Órbita Tech Sites", roxo, ciano e amarelo) é provisória. O seu site não pôde ser acessado
  daqui; troque as cores e o nome em `BRAND`.
- Os sites mostrados nos celulares são **exemplos ilustrativos** de negócios fictícios e estão marcados como tal.
  Para mais prova, troque por capturas dos sites que você já fez.
- As trilhas e os efeitos foram sintetizados do zero (sem direitos de terceiros). Se preferir, troque pela biblioteca de músicas do Meta.
