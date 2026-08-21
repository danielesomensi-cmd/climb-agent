# Kalymnos — Summertime (Arginonta) — dati ricostruiti per gli schizzi topo

Nota personale, non documentazione di prodotto (segue [[A278]] nel bridge Telegram).
Dati ricostruiti a mano dal guidebook incrociando più fonti — **da controllare sul
posto**, non è un topo ufficiale.

## Come rigenerare uno schizzo

```bash
python3 scripts/topo_sketch.py \
  --sector "Summertime — <nome settore>" \
  --subtitle "Kalymnos, Arginonta — N vie, sx→dx" \
  --routes scripts/topo_data/<file>.json \
  --out schizzo.png
```

Serve `rsvg-convert` (`brew install librsvg`). Il file `--routes` è una lista di
oggetti `{"position": N, "name": "...", "grade": "...", "length_m": N, "stars": N}`
— solo `name` e `grade` sono obbligatori, `position` decide l'ordine sinistra→destra
(di default segue l'ordine della lista se assente).

Per mandarlo su Telegram: copia il PNG dentro `.claude_bridge_outbox/` (nome file
= titolo con cui arriva) — il bridge lo consegna da solo, anche a un riavvio, senza
bisogno di un altro messaggio (vedi `deliver_outbox` / `_startup_flush_outbox` in
`scripts/telegram_bridge.py`).

## Fonti usate

- [climbkalymnos.com — vista completa Summertime](https://climbkalymnos.com/view/?crag=Summertime) (fonte primaria, posizione sx→dx)
- [theCrag — Summertime](https://www.thecrag.com/en/climbing/greece/kalymnos/arginonda/area/2267514189)
- [theTopo — Summertime](https://thetopo.com/crags/summertime-kalymnos/routelist/summertime)
- Mountain Project (incrocio grado su singole vie)

## Settore Main (`kalymnos_summertime_main_partial.json`) — **PARZIALE**

Solo le posizioni 1-3 e 12-15 sono confermate; **4-11 sconosciute**, climbkalymnos
non me le ha restituite in nessuna delle interrogazioni fatte.

| # | Via | Grado | m | ★ |
|---|-----|-------|---|---|
| 1 | Salbei | 6a | 20 | ★★ |
| 2 | Friends | 6b+ | 20 | ★ |
| 3 | Dill | 6a | 25 | ★★ |
| — | *(4–11 non ricostruite)* | | | |
| 12 | Salamina tis Kypros | 6a+ | 20 | ★★ |
| 13 | Ammohostos Vasilevousa | 6a | 20 | ★★★ |
| 14 | Maccabi | 6b+ | 23 | ★★★ |
| 15 | Orea Dana | 6a+ | 25 | ★★ |

## Settore Summer Wine / Ando Drom (`kalymnos_summertime_summer_wine.json`) — 20 vie

Attenzione al nome: climbkalymnos.com lo chiama **"Summer Wine"**, theTopo/27crags
lo chiamano **"Ando Drom"** — stesso settore, guide diverse.

| # | Via | Grado | m | ★ |
|---|-----|-------|---|---|
| 1 | Shiva + Dimitris | 6a | 30 | ★★ |
| 2 | Ando Drom | 6c | 30 | ★★★ |
| 3 | Acon69cagva | 6b+ | 30 | ★★ |
| 4 | Didi, hermana di alma | 6a | 25 | ★★★ |
| 5 | Summer Wine | 6b+ | 28 | ★★★ |
| 6 | Silver Spurs | 6c | 27 | ★★★ |
| 7 | Get Up | 6a+ | 25 | ★★ |
| 8 | Beru | 6a+ | 25 | ★★ |
| 9 | Mama Nota | 7a | 25 | ★★ |
| 10 | Père Vert | 7a | 25 | ★★ |
| 11 | Mr Rigolo | 6b+ | 25 | ★★★ |
| 12 | Antonis Lampos | 6c | 15 | ★★★ |
| 13 | 6 riens | 6b | 15 | ★★ |
| 14 | Roumain des bois | 6a+ | 15 | ★★ |
| 15 | Hongrois rêve | 6a+ | 15 | ★★ |
| 16 | Papou Christo | 6b | 18 | ★★ |
| 17 | Angry Bird | 7c+ | 12 | ★★★ |
| 18 | Norwegian Friends | 7b+ | 12 | ★★★ |
| 19 | Vulture | 7a+ | 16 | ★★ |
| 20 | No Pain No Gain | 7a | 16 | ★ |

**Da verificare sul posto:** una fonte (theTopo) elenca anche una via **"Pain" 6b+**
fra Norwegian Friends e Summer Wine, non confermata da climbkalymnos — non inclusa
nello schizzo. La stessa fonte, in un fetch diverso, dava ad **Ando Drom** il grado
6b invece di 6c: tenuto 6c perché confermato sia da climbkalymnos sia dal titolo
diretto della pagina theCrag ("6c ★★Ando Drom, 30m") sia da Mountain Project.

## Settore Magoulias (`kalymnos_summertime_magoulias.json`) — 17 vie

Settore tecnico, range ampio (5c-8b+). Un'unica fonte coerente (climbkalymnos.com),
quindi meno incroci fatti rispetto a Summer Wine — **controlla i gradi con più
attenzione sul posto**.

| # | Via | Grado | m | ★ |
|---|-----|-------|---|---|
| 1 | 7a l'Envers | 8b | 15 | ★★ |
| 2 | Begraveningsplatz | 8b+ | 15 | ★ |
| 3 | Finally it's not 7a | 8b+ | 18 | ★★ |
| 4 | Agrimi | 7a+ | 35 | ★★ |
| 5 | A Route With a View | 7b | 40 | ★★ |
| 6 | L'enfer du ménage | 7b | 40 | ★★ |
| 7 | Fred | 6b | 30 | ★★★ |
| 8 | Nikolas | 5c | 20 | ★★ |
| 9 | Nikolas ext | 7a+ | 40 | ★★ |
| 10 | Fotini | 6b | 25 | ★★★ |
| 11 | Honey Ball | 6c | 25 | ★★ |
| 12 | Toni | 6c | 25 | ★★★ |
| 13 | Anne | 6b | 30 | ★★ |
| 14 | Sabina | 6c+ | 28 | ★★★ |
| 15 | Vlasis House | 6c+ | 28 | ★★ |
| 16 | K tsi k | 7b+ | 20 | ★★★ |
| 17 | Vertigo | 7c | 20 | ★★ |

`Vlasis House` corretto a 6c+ (non 6c) dopo conferma diretta su theCrag — unica
correzione fatta su questo settore, il resto non ri-verificato via fonte esterna.

**Angry Birds / Norwegian Friends** compaiono anche in un articolo di
climbkalymnos.com su "Magoulias Right" — **non** in questa lista, che viene dalla
vista sezionata del sito e non li include: probabile sotto-settore diverso da
quello sopra, non incluso qui per evitare doppioni.

## Non ricostruiti

Local Freezer, Tonga Cave, Nikoleta, Big Shadow, Highlands — solo nomi/posizione
generica, nessun elenco vie ricostruito.
