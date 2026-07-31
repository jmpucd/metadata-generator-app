---
name: language-cjk
description: Chinese / Japanese / Korean text — whole-phrase translation, compound handling, worked examples
applies_to: photo, verso, document
tess_lang: eng+chi_tra+chi_sim+chi_tra_vert+chi_sim_vert
---

- CJK compounds must be read as units, never glossed character-by-character: 歡迎光臨 = 'Welcome' (not 'welcome + visit'), 合影留念 = 'commemorative group photo' (not 'group photo + souvenir'), 記念写真 = 'commemorative photograph' (not 'memory + photo').
- Worked example of the required visible_text format: '歡迎光臨曼谷大皇宮合影留念 (Traditional Chinese) [translation: Welcome to Bangkok Grand Palace — commemorative group photo] WELCOME TO BANGKOK GRAND PALACE'.
- Distinguish Traditional from Simplified Chinese in the language label when the script makes it clear; if a segment is ambiguous, label it 'Chinese' and note the ambiguity in uncertainty_notes.
- Vertical text is common on signage, banners, and photo-studio marks — read top-to-bottom, right-to-left, and say so in uncertainty_notes if the reading order is uncertain.
- Personal and business names are frequently transliterated inconsistently. Transcribe exactly what is written; do not silently normalise a name to a spelling used elsewhere in the collection.
