# Directive: Business Discovery

## Purpose
Before a single line of HTML is written, find everything the internet already knows about this business. The goal is a ranked manifest of every source — from which the rest of the pipeline pulls real content. The biggest prize is an existing website ("liquid gold"), which is a pre-curated content source that can be used near-verbatim.

## Script
```
python execution/discover_business.py
```
Reads `inputs/project_input.md` — no arguments needed.

## Discovery Steps

### 1. Google Business Profile (if URL is provided)
Open via Playwright. Extract:
- **Website URL** — the single most important field. If present, marks a `liquid_gold` source.
- Phone, address
- All photo URLs (`lh3.googleusercontent.com/*`) — must be downloaded immediately as they expire within ~24 hours.
- Business description / "From the business" text.

### 2. Existing website (web search, if not on Google profile)
Search: `"{name} {location} official website"`. Take the first result whose host does not match a known social/aggregator domain. Classify as `liquid_gold` if found.

### 3. Social & directory profiles
Search for each platform separately:
- Facebook — `"{name} {location} facebook"`
- Instagram — `"{name} {location} instagram"`
- JustDial — `"{name} {location} justdial"`
- Sulekha — `"{name} {location} sulekha"`
Match results to the correct host before recording.

### 4. News mentions
Search: `"{name} {location} news"`. Record title + URL only (no content invented from snippets).

## Output: business_manifest.json
```json
{
  "business_name": "...",
  "location": "...",
  "discovered_at": "...",
  "google_photos": ["lh3.googleusercontent.com/..."],
  "sources": {
    "existing_website": { "url": "...", "priority": 1, "type": "liquid_gold" },
    "google_profile":   { "url": "...", "priority": 2, "type": "google", "photos": N },
    "facebook":         { "url": "...", "priority": 3, "type": "social" },
    "justdial":         { "url": "...", "priority": 4, "type": "directory" },
    "news":             { "priority": 5, "type": "news", "items": [...] }
  }
}
```

## Priority Rules
- `liquid_gold` (priority 1) — existing website. Used by `collect_assets.py` first. Gemini uses as primary copy source.
- `google` (priority 2) — Business Profile photos + description.
- `social` (priority 3) — FB, IG, etc.
- `directory` (priority 4) — JustDial, Sulekha.
- `news` (priority 5) — titles + URLs only; never used as content source.

## Edge Cases

| Situation | Action |
|-----------|--------|
| No Google URL provided | Skip Playwright profile step; rely on web search |
| Google profile has no website link | `liquid_gold` stays absent; continue with P2+ |
| Google photos expire before download | `collect_assets.py` re-runs the Google step only |
| All social searches return no match | Platform absent from manifest; log warning |
| Search tool (ddgs) rate-limits | Wait 2s, retry once; on second failure log and continue |
| Business name returns ambiguous results | Log warning; user should provide Google URL directly |

## What NOT to do
- Do not invent a website URL if search returns nothing.
- Do not record a social profile URL unless the host matches exactly.
- Do not scrape login-walled content (FB, IG walls) — record the URL only.
