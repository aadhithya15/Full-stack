# MVP Round-Trip Verification (the final check)

Terminal 1:
    python run.py

Terminal 2 (PowerShell):
    $body = @{ email = "demo@huefit.com"; password = "demopass123" } | ConvertTo-Json
    $res = Invoke-RestMethod -Uri "http://localhost:5000/api/auth/login" -Method Post -ContentType "application/json" -Body $body
    $token = $res.token

    $r = curl.exe -s -X POST http://localhost:5000/api/fashion/analyze -H "Authorization: Bearer $token" -F "skin_tone_text=wheatish" -F "occasion=festive" -F "gender=female" -F "dress_type=saree" -F "outfit_culture=tamil" -F "age=24" | ConvertFrom-Json
    $r | ConvertTo-Json -Depth 8

What to verify in the output:
  1. "mock": false                      (real AI recommended the colours)
  2. recommendations[i].image_source    = "template" for saree outfits
  3. recommendations[i].image_url       -> open in browser = recoloured saree
     in THAT outfit's recommended colour (different colour per outfit!)
  4. template_code                      = "saree_f_01" (until real templates land)
  5. run the SAME request again         -> repeat images arrive instantly (cache)
