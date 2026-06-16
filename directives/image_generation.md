# Directive: Image Generation (Gemini — Phase 5)

## Purpose
Tell Gemini exactly how to generate the requested images and wire them into the pipeline. Image generation is Gemini's responsibility during its design phase. Claude Code never generates images.

## Trigger
When `supervisor_status.md` reaches Gemini for Phase 5, the `## Generate the requested images` section lists every image request from `project_input.md § Images to Generate`.

## Generation Steps

1. **Read the requests** from `supervisor_status.md` (surfaced from `project_input.md`).
2. **Read the style references** — the `## Image References` URLs in `project_input.md`. These define the visual style to imitate: lighting, mood, color temperature, composition. Do not copy content from them; imitate the aesthetic.
3. **Generate each image** in Antigravity. Keep generation prompts specific:
   - Include the business type and brand feel (e.g. "luxury salon, gold and dark tones").
   - Include the style references as mood anchors.
   - Include technical specs if helpful (e.g. "16:9 ratio, soft bokeh background").
4. **Save** each image to `assets/images/generated_{slug}.png` where `{slug}` is a short kebab-case label from the request (e.g. `generated_hero_reception.png`).
5. **Update `images_manifest.json`**: append a JSON object for each generated image:
   ```json
   {
     "path": "assets/images/generated_hero_reception.png",
     "source": "generated",
     "prompt": "warm-lit reception with gold honeycomb accents, wide shot",
     "suggested_use": "hero"
   }
   ```
6. **Reference in the brief**: the `image_assignments` field in `design_brief.md` must include every generated image, naming which section it goes in.

## No-Hallucination Rule (images)
If a generation request cannot be fulfilled (Antigravity error, unclear prompt, quota):
- Leave the image slot EMPTY.
- Write the original prompt as a marker in `images_manifest.json`:
  ```json
  { "path": "EMPTY", "source": "generated", "prompt": "...", "suggested_use": "hero" }
  ```
- Note it in the brief's `image_assignments` as `EMPTY: <prompt>`.
- **Never substitute a random/unrelated image.** Empty beats wrong.

## Image Naming Convention
| Use | Filename |
|-----|----------|
| Hero background | `generated_hero.png` |
| Interior gallery | `generated_interior_1.png`, `generated_interior_2.png` |
| Service/treatment | `generated_service_manicure.png` |
| Product shot | `generated_product.png` |
| Team/staff ambiance | `generated_team.png` |

## Quality Checks Before Moving On
- Every request in `project_input.md § Images to Generate` has a corresponding entry in `images_manifest.json` (FILLED or EMPTY).
- Every generated image is ≥ 50KB (not a blank/error output).
- Every generated image is referenced in `design_brief.md § image_assignments`.
