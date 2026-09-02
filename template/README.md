# HUE FIT — templates + masks (final)

30 template photos + 56 garment masks (M7 carries three pieces: jacket, kurta, churidar), produced with the FASHN human-parser
pipeline (class gates + sleeve colour gate + white-shirt cut + strip-after-polish).
Every mask passed the 10-check audit: zero skin/face/hair/hands/feet/jewellery
pixels, pieces non-overlapping, outside-mask pixels bit-identical after recolour.

Layout:
  templates/<photo>.jpg   1400px JPEG, matching guide filenames
  masks/<piece>-mask.png  white = garment, black = everything else (same WxH as photo)

App usage (recolour piece at runtime, no AI needed):
  result = photo;  result[mask>0] = hueShift(photo[mask>0], dh)  // HSV dh any 0-179

Mask naming: photo-id-piece (e.g. M8-sherwani-mask.png ↔ templates/M8-sherwani.jpg).
