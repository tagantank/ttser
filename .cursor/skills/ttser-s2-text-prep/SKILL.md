---
name: ttser-s2-text-prep
description: Prepares UTF-8 narration text for ttser desktop TTS using Fish Audio S2 Pro (s2.cpp / libs2_*). Use only in the ttser repo, or when the user names ttser, Fish Audio S2 Pro, s2-pro, s2.cpp, or [pause] chunks for this app. Do not use for VoxCPM, other TTS engines, or generic озвучка.
---

# ttser / Fish Audio S2 Pro text prep

Scope: **ttser + Fish Audio S2 Pro only**. ttser calls `S2Synthesize` once per non-empty line through `libs2_*`. Line breaks are synthesis chunks, not typography. Early EOS and mid-clause wraps swallow phrase endings.

Do not apply this skill to VoxCPM, HTTP `s2` server prompts, or any other TTS. Those have different pause syntax and chunk limits.

## Workflow

1. Read the source UTF-8 file. Do not overwrite it unless the user asked to replace it. Write beside it (`*_tts_vN.txt` or `*.s2.txt`).
2. Editorial listenability pass, then wrap.
3. Run the skill script. It keeps ttser `[pause …]` lines, packs at most two sentences toward 180 characters, caps at 260, and restores terminal punctuation.
4. Inspect the report and fix leftover wrap bugs by hand, especially `period_stacks_over_2`.
5. Re-run `--check-only` until there are no lines over 260, no lowercase-start lines, no speech lines without `. ! ? … ; :`, and no period stacks over 2.

```bash
python .cursor/skills/ttser-s2-text-prep/scripts/prepare_s2_tts_text.py \
  --input "$SRC" \
  --output "$DST" \
  --report "$DST.report.json" \
  --target-chars 180 \
  --max-chars 260
```

Check an already wrapped file:

```bash
python .cursor/skills/ttser-s2-text-prep/scripts/prepare_s2_tts_text.py \
  --input "$DST" --check-only --max-chars 260
```

Do **not** run `python -m engine.prepare_s2_text` on files that already use `[pause …]`. That helper only understands `<break time="…"/>` and treats every blank-line paragraph as its own tiny chunk. ttser runtime pauses are `[pause 0.3s]` / `[pause 500ms]`, never SSML.

## Chunk rules

- One line = one complete spoken unit ending in `.` `!` `?` `…` `;` or `:`.
- Prefer 80–260 characters. Podcast target is **180**. Never exceed **260** (S2 quality drops after ~800 tokens / ~37 s; 260 chars stays well under that).
- Avoid speech lines shorter than **25** characters unless they are a heading or sit next to `[pause …]`.
- Do **not** pack 3+ independent period-separated sentences into one line. S2 often emits EOS after the first few and never speaks the last one (`отдых`, `деньги`). Join those stacks with commas or a colon into **one** sentence, or put the last sentence on its own line of at least ~60 characters.
- The wrap script packs at most **two** sentences per chunk. Editorial comma-join is still required for telegraphic lists (`Что происходит с ценами. Какие направления растут.`).
- Split after `. ! ? ; …`, not in the middle of a clause. If a sentence is still over 260, cut at `, ` or ` — ` and end the first piece with `…`.
- Do not split on `:` when the next words continue the same sentence (`Одна сторона говорит: отдыхать в России слишком дорого.` stays one line).
- Keep `[pause 0.3s]` / `[pause 0.4s]` / `[pause 500ms]` on their own lines. Do not invent pauses; keep the author's markers.
- Do not hyphenate inside words. Soft hyphens (`U+00AD`) must be removed.
- Keep names, numbers-with-units, and short noun phrases together.
- Empty lines are ignored by ttser. Use `[pause …]`, not blank lines, when a pause must be heard.
- Dictionaries at synth time: `dictionaries/s2_terms_ru.json` and `dictionaries/s2_pronunciation_ru.json`. Prefer adding a dictionary row over baking a one-off spelling into the script.

## Listenability pass

When the user asks to оптимизировать / под синтез / под ttser / S2 Pro:

- Merge one-word staccato lists **and** short question/statement stacks into one comma-joined sentence:
  - bad: `Перелёт.` / `Трансфер.` / `Пляж.`
  - bad: `Что происходит с ценами. Какие направления растут. … И главное — как всё это влияет на наш отдых.`
  - good: `Что происходит с ценами, какие направления растут, … и главное — как всё это влияет на наш отдых.`
  - good: `Он сравнивает полную стоимость отдыха: перелёт, трансфер, проживание, пляж, сервис и уровень предсказуемости.`
- Keep contrast pairs in one chunk: `не как найти туриста, а как найти свободный номер.`
- Move orphan tails like `И наконец.` onto the next question.
- Expand symbols a listener cannot hear (`№` → `номер`, `&` → `и`). Do not reintroduce digits if the source already spells numbers out.
- Preserve facts. Do not invent numbers, names, or conclusions.

## Why S2 Pro swallows endings

| Symptom | Cause | Fix in the text |
|---|---|---|
| Last words of a line never spoken | Fish Speech / S2 early EOS: a fragment, **or** 3+ short sentences packed into one 180-char line | One sentence with commas/colon; avoid 1–20 character chunks; do not stack telegraphic periods |
| Syllable exists in WAV but next line slams in | WAV concat in ttser | Leave `[pause …]`; ttser also adds `line_pause_ms` (default 180) |
| Line is silent / much too short | GPU abort in `libs2_*` | Not a text issue; ttser retries those WAVs |

Do not raise ttser `max_new_tokens` to "fix" long lines. Split the text. After wrap, a useful ttser dialog hint is `min_tokens_before_end` ≈ 80–150; too high makes S2 ramble.

## Verification

Report:

- speech chunk count and pause count
- min / median / max speech line length
- lines `< 25`, `> 260`, missing end punct, lowercase starts
- leftover Latin tokens (candidates for `s2_terms_ru.json`)
- `period_stacks_over_2`: lines with 3+ `. ! ? …` (S2 early-EOS risk; comma-join them)

Done when: max ≤ 260, no lowercase-start speech lines, every speech line has end punctuation, `[pause …]` lines are unchanged, and the file is meant for ttser + S2 Pro — not another engine.
