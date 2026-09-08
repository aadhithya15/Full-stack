# HueFit - Frontend Integration Note: MVP Template Images
*The image layer changed: recommendations now carry recoloured outfit-template
images instead of AI-generated pictures. Contract changes are tiny.*

## What changed in the analyze response

Each recommendation now has:

| Field | Values | Meaning |
|---|---|---|
| `image_url` | URL or `null` | permanent link to the recoloured template render (public bucket - loads fast, never expires, cacheable) |
| `image_source` | `"template"` or `"none"` | `"template"` = a real render exists; `"none"` = no template matched this outfit's dress type yet |
| `template_code` | string or absent | which approved template produced the image |

REMOVED behaviour: image URLs are no longer Pollinations links. No generation
delay, no random quality - the same outfit+colour always yields the same image.

## What to build/change

1. Render the image only when `image_source == "template"` (same null-handling
   pattern as before - palette-only card when absent).
2. No loading skeleton needed for images anymore: renders are pre-generated
   and served from storage - they load like any static image.
3. Nothing else changes: all other fields, auth, endpoints identical.

## Why images can be "none" during this phase

The template library is being filled by the design team. Until a dress type
has an approved template, its outfits return `image_source: "none"`.
The set of covered dress types will grow as templates are approved - no
frontend change needed as coverage improves.
