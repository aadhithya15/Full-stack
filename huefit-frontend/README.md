# HueFit — AI Personal Fashion Stylist

HueFit helps users discover outfits, colours, accessories and footwear based on skin tone, occasion, weather, budget and personal style.

## Frontend features
- Premium responsive AI-fashion landing page
- AI style quiz
- Fashion analysis form with photo preview and validation
- Multiple outfit result cards, colour palette and Generate More UI
- Login/Register interface
- Dashboard, profile, saved looks, compare looks and digital closet UI
- Responsive mobile, tablet and desktop layouts

## Tech stack
React, Vite, React Router, Axios, Tailwind CSS, Lucide Icons.

## Local setup
```bash
npm install
cp .env.example .env
npm run dev
```

Set `VITE_API_BASE_URL` to the backend API URL. Do not commit `.env` or API keys.

## Backend integration
The frontend follows `API-CONTRACT.md` for JWT authentication, fashion analysis, saved looks, profile and history APIs.
