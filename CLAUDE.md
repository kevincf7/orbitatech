# Orbitatech — negócio de criação de sites

Este repositório centraliza tudo sobre o negócio de **criação de sites para empresas locais**:
a oferta, os anúncios, os clientes e os sites entregues.

Não coloque aqui:
- vídeos do @manualdetudobr → repositório `videos-remotion`
- o app Prato Forte → repositório `prato-forte`
- campanhas da engbrunalacerda → repositório `engbrunalacerda`

## Estrutura

- `oferta/` — preço, o que está incluso, respostas para objeções e o roteiro da conversa no WhatsApp.
- `anuncios/` — anúncios em vídeo e imagem do negócio (os 12 vídeos 9:16 do "site por R$16/mês"
  vêm para cá, em `anuncios/videos/`).
- `clientes/` — um arquivo por cliente: contato, pedido, status e entregas.
- `sites/` — projetos dos sites (um subdiretório por cliente).

## Oferta atual

- Site profissional por **R$16/mês** para empresas locais, com botão do WhatsApp e prévia
  antes de decidir.
- Os anúncios não falam em "grátis", portfólio, plataforma ou afiliação; o motivo do preço
  fica para a conversa no WhatsApp.
- Não prometa prazo de entrega nem número de ajustes, e não invente escassez.
- O CTA pede para tocar em "Enviar mensagem" (anúncio de clique para o WhatsApp).

## Regras para criação de campanhas Meta Ads

- Vídeos verticais (9:16) **também rodam no Feed e no Perfil do Instagram**. Use
  `instagram:stream`, `instagram:profile_feed`, `instagram:reels` e `instagram:story`, a menos
  que o usuário peça outra coisa.
- A ferramenta OneClick remove Feed/Perfil de vídeos verticais (e pode remover Reels/Stories de
  carrosséis e imagens). Depois que o job terminar, confira cada conjunto e recoloque os 4
  posicionamentos com `updateAdSet` sem perguntar.
