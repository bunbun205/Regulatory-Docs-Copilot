# F0 screenshot baseline

Captured 2026-10-25 from real Chromium at device scale 1; light system theme.
Viewports: 1280×900 and 390×844. Vite: `http://127.0.0.1:3100`; proxy target:
`http://127.0.0.1:8001`; API uses the fake LLM provider. No generation or upload
was submitted. The document rows are the existing local corpus. The 401 is real.

Every image below was opened and visually inspected. These are viewport images,
so overflow is visible as clipping, rather than hidden by a wider full-page PNG.
The library and invalid-key screenshots scroll vertically to show those states.
Horizontal scrolling needed by the broken mobile layout is a baseline defect.

| Existing screen / state | 1280px | 390px |
| --- | --- | --- |
| No key / shell | [Desktop](no-key-1280.png) | [Mobile](no-key-390.png) |
| Documents input | [Desktop](documents-1280.png) | [Mobile](documents-390.png) |
| Document library | [Desktop](documents-library-1280.png) | [Mobile](documents-library-390.png) |
| Search input | [Desktop](search-1280.png) | [Mobile](search-390.png) |
| Ask input | [Desktop](ask-1280.png) | [Mobile](ask-390.png) |
| Agent input | [Desktop](agent-1280.png) | [Mobile](agent-390.png) |
| Gap Check input | [Desktop](gap-check-1280.png) | [Mobile](gap-check-390.png) |
| Invalid key / Documents error | [Desktop](invalid-key-1280.png) | [Mobile](invalid-key-390.png) |

Settings has no existing screen. The header key flow is its baseline.
Every 390px capture has horizontal page overflow; controls and table columns
are clipped. Desktop input controls are much smaller than the available space.
These findings are not fixed in F0.

[Recorded metrics and 22 passing capture checks](baseline.json).
[Audit and plan](../../frontend-f0-audit.md).
