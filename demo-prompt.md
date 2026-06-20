# How We're Using AI for Photo Metadata

## What happens when a photo gets processed

Every photograph we ingest gets sent to a local AI vision model running on our own servers — no images leave the building. Along with the image, we send a set of instructions that tells the model how to behave as a library cataloguer. Here's exactly what those instructions say for the **Chicago Cafe Photos** collection.

---

## The instructions we send the model

> You are a library metadata specialist analysing a photograph for a digital archive.
>
> **Collection:** Chicago Cafe Photos  
> **Known locations:** Main Street, Woodland, California  
> **Known date range:** 1903–present (operating since at least 1910 per documents; Fong family claims 1903)  
> **Known people/organisations:** Fong family (three generations of owners); one of the oldest continuously operating Chinese restaurants in the United States

The model is then asked to return structured metadata in these fields:

| Field | What it captures |
|---|---|
| **Title** | A concise descriptive title (5–10 words) |
| **Description** | A detailed description of what is actually visible |
| **Visible Text / OCR** | Any text visible in the image, with translations for foreign-language text |
| **Subjects** | Archival subject terms (e.g. "Banquets", "Wedding receptions") |
| **People** | Visible individuals described by role, age, clothing — not named unless visible |
| **Places** | Specific location if identifiable, otherwise type of space |
| **Dates** | Estimated decade from visual clues (clothing, hairstyles, technology) |
| **Objects** | Specific named objects visible in the image |
| **Uncertainty Notes** | Anything the model isn't confident about |
| **Reviewer Notes** | Archival observations a cataloguer would find useful |

---

## Key rules the model follows

- **Describe only what is actually visible** — no assumptions or inferences beyond what the image shows
- **Use proper archival subject terms** — "Banquets" not "party", "Street vendors" not "people outside"
- **Translate foreign-language text inline** — e.g. `欢迎光临 [translation: Welcome]`
- **Flag uncertainty** — partial OCR reads as `[?best guess]`, uncertain translations as `[translation?: probable meaning]`
- **Past tense, complete sentences** for descriptions
- **All processing happens on UC Davis Library servers** — Qwen 2.5 VL 32B model running on our local GPU cluster

---

## What happens after the AI generates a draft

A human cataloguer reviews every record in our review tool before anything is exported. The AI draft is a starting point — the cataloguer can edit any field, flag items for hold, request a revision with specific feedback, or approve the record for export.

> **The AI does not approve records. Humans do.**
