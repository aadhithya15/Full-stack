/* HUEFIT-END-SELFIE-CTA: full home page skin-tone only + StyleDNA-style selfie CTA image */
import { ArrowUpRight, ChevronRight, Sparkles } from 'lucide-react'
import { Link } from 'react-router-dom'
import heroSkinBg from '../assets/hero-skin-bg.jpg'
import heroSkinInsetA from '../assets/hero-skin-inset-a.jpg'
import heroSkinInsetB from '../assets/hero-skin-inset-b.jpg'
import ctaSelfie from '../assets/cta-selfie.jpg'
import stripSkin1 from '../assets/strip-skin-1.jpg'
import stripSkin2 from '../assets/strip-skin-2.jpg'
import stripSkin3 from '../assets/strip-skin-3.jpg'
import stripSkin4 from '../assets/strip-skin-4.jpg'
import paletteFair from '../assets/palette-fair.jpg'
import paletteMedium from '../assets/palette-medium.jpg'
import paletteDeep from '../assets/palette-deep.jpg'
import paletteUndertone from '../assets/palette-undertone.jpg'
import statementSkinBg from '../assets/statement-skin-bg.jpg'
import './HomePage.css'

const TONES = [
  { value: 'fair', label: 'Fair', swatch: '#C5AFA3' },
  { value: 'light', label: 'Light', swatch: '#BBA192' },
  { value: 'wheatish', label: 'Wheatish', swatch: '#AE9181' },
  { value: 'medium', label: 'Medium', swatch: '#BE815E' },
  { value: 'dusky', label: 'Dusky', swatch: '#9E7F6E' },
  { value: 'deep', label: 'Deep', swatch: '#90705C' },
]

const CLOTH_TYPES = [
  { type: 'FAIR Â· LIGHT', title: 'Soft, bright\nand light', image: paletteFair, colors: ['#F5EBD8', '#E8C39E', '#C99A7B'] },
  { type: 'WHEATISH Â· MEDIUM', title: 'Warm, golden\nand rich', image: paletteMedium, colors: ['#C99A42', '#8A5A22', '#5C3A1E'] },
  { type: 'DUSKY Â· DEEP', title: 'Deep, bold\njewel tones', image: paletteDeep, colors: ['#3B1B22', '#11684F', '#C9A227'] },
  { type: 'UNDERTONE', title: 'Warm, cool\nor neutral', image: paletteUndertone, colors: ['#D9A441', '#B9C0C7', '#8A6F5C'] },
]

export default function HomePage() {
  return (
    <main className="home-mix">
      <section className="mix-hero">
        <div className="mix-hero-image">
          {/* HUEFIT-NEW-SKIN-HERO: front hero uses brand-new generated skin-tone images only */}
          <img className="mix-hero-main" src={heroSkinBg} alt="Skin tone with silk colour palette" />
          <img className="mix-hero-inset mix-hero-inset-a" src={heroSkinInsetA} alt="Hand holding personal colour swatches" />
          <img className="mix-hero-inset mix-hero-inset-b" src={heroSkinInsetB} alt="Skin tone on maroon and gold silk" />
          <div className="mix-hero-vignette" />
        </div>
        <div className="mix-hero-copy">
          <p className="hero-reward">
            <Sparkles size={15} /> COLOUR FIRST <b>SKIN TONE Â· PALETTE Â· THEN CLOTH</b>
          </p>
          <p className="mix-kicker">HUEFIT / PERSONAL COLOUR ANALYSIS</p>
          <h1>
            FIND THE COLOURS<br />
            THAT FEEL <em>LIKE YOU.</em>
          </h1>
          <p className="hero-sub">
            Start with your skin tone. HueFit builds a personal colour palette,
            then recommends cloth that sits well on that palette â€” traditional, modern or fusion.
          </p>
          <div className="home-tone-row" aria-hidden="true">
            {TONES.map((t) => (
              <span key={t.value} title={t.label}>
                <i style={{ background: t.swatch }} />
                {t.label}
              </span>
            ))}
          </div>
          <div className="mix-hero-actions">
            <Link to="/analyze" className="hero-primary">Analyse my colours <ArrowUpRight size={18} /></Link>
            <Link to="/quiz" className="hero-ghost">Take the style quiz</Link>
          </div>
        </div>
      </section>

      <section className="intro-v2 mix-intro">
        <div className="wide">
          <p className="micro dark">THE CORE EXPERIENCE</p>
          <div className="intro-title">
            <h2>Selfie. Skin tone.<br /><em>Then the cloth.</em></h2>
            <p>
              Colour analysis is the product. Outfit recommendation is the second layer â€”
              driven by your colour profile and the clothes type you choose next.
            </p>
          </div>
          <div className="number-line">
            <span>01 - SELFIE / SKIN TONE</span>
            <span>02 - PERSONAL PALETTE</span>
            <span>03 - CLOTHES TYPE</span>
            <span>04 - OUTFIT EDIT</span>
          </div>
        </div>
      </section>

      <section className="mix-strip">
        <div className="wide">
          <p className="micro dark">SKIN TONES WE ANALYSE</p>
          <div className="mix-strip-grid" style={{ marginTop: 22 }}>
            <figure className="fit-hand"><div className="mix-strip-frame"><img src={stripSkin1} alt="Fair light skin tone with pastel swatches" /></div><figcaption>Fair Â· Light</figcaption></figure>
            <figure className="fit-portrait"><div className="mix-strip-frame"><img src={stripSkin2} alt="Wheatish medium skin tone with maroon and gold" /></div><figcaption>Wheatish Â· Medium</figcaption></figure>
            <figure className="fit-walk"><div className="mix-strip-frame"><img src={stripSkin3} alt="Dusky deep skin tone with jewel tones" /></div><figcaption>Dusky Â· Deep</figcaption></figure>
            <figure className="fit-portrait"><div className="mix-strip-frame"><img src={stripSkin4} alt="Warm versus cool undertone test on skin" /></div><figcaption>Warm Â· Cool Â· Neutral</figcaption></figure>
          </div>
        </div>
      </section>

      <section className="process" id="process">
        <div className="wide process-grid">
          <div className="process-left">
            <p className="micro dark">HOW THE HUEFIT EDIT WORKS</p>
            <h2>Start with colour.<br /><em>Clothes come<br />second.</em></h2>
            <div className="orb mix-orb"><span>YOUR<br/>COLOUR<br/>STORY</span></div>
          </div>
          <div className="process-steps">
            <article>
              <b>01</b>
              <div>
                <h3>Share your skin-tone signal</h3>
                <p>Upload a clear selfie or pick Fair, Light, Wheatish, Medium, Dusky or Deep.</p>
              </div>
              <span>â†˜</span>
            </article>
            <article>
              <b>02</b>
              <div>
                <h3>See your personal palette</h3>
                <p>HueFit turns that signal into colour families that work on your skin.</p>
              </div>
              <span>â†˜</span>
            </article>
            <article>
              <b>03</b>
              <div>
                <h3>Choose the clothes type</h3>
                <p>Occasion, dress type and style â€” traditional, modern or fusion â€” then get the outfit edit.</p>
              </div>
              <span>â†˜</span>
            </article>
            <Link to="/analyze" className="under-link">Analyse my colours <ChevronRight size={18} /></Link>
          </div>
        </div>
      </section>

      <section className="lookbook mix-lookbook" id="looks">
        <div className="wide">
          <div className="section-top">
            <p className="micro">YOUR PERSONAL COLOUR PALETTE</p>
            <span>FAIR Â· LIGHT Â· WHEATISH Â· MEDIUM Â· DUSKY Â· DEEP</span>
          </div>
          <div className="look-head">
            <h2>Find your skin tone.<br /><em>Get your palette.</em></h2>
            <p>Six skin tones. One palette made<br />for your skin only.</p>
          </div>
        </div>
        <div className="look-track mix-track">
          {CLOTH_TYPES.map((look, index) => (
            <article className="look" key={look.type}>
              <div className="look-photo">
                <img src={look.image} alt={look.title} />
                <span>0{index + 1}</span>
              </div>
              <div className="look-info">
                <p>{look.type}</p>
                <h3>{look.title.split('\n').map((x, i) => <span key={i}>{i > 0 ? ' ' : ''}{x}<br /></span>)}</h3>
                <div className="swatches">{look.colors.map((c) => <i style={{ background: c }} key={c} />)}</div>
                <Link to="/analyze">Start with colour <ArrowUpRight size={16} /></Link>
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="image-statement">
        <img src={statementSkinBg} alt="Skin tone on dark silk" />
        <div className="statement-copy">
          <p className="micro">COLOUR FIRST Â· CLOTH SECOND</p>
          <h2>Your skin tone<br />writes the<br /><em>colour story.</em></h2>
          <Link to="/analyze" className="pill-light">Analyse my colours <ArrowUpRight size={16} /></Link>
        </div>
      </section>

      <section className="end-v2">
        <div className="end-v2-split">
          <div className="end-v2-copy">
            <p className="micro dark">READY WHEN YOU ARE</p>
            <h2>Begin with<br />your colours.<br /><em>Then the cloth.</em></h2>
            <Link to="/analyze" className="big-link">Analyse my colours <ArrowUpRight /></Link>
          </div>
          <div className="end-v2-cloth">
            <img src={ctaSelfie} alt="Selfie skin tone analysis with personal palette results" />
          </div>
        </div>
      </section>
    </main>
  )
}