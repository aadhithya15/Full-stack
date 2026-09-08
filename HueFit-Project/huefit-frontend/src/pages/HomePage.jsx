import { ArrowUpRight, ChevronRight, Sparkles } from 'lucide-react'
import { Link } from 'react-router-dom'
import traditionalHero from '../assets/traditional-hero.jpg'
import traditionalSareeLandscape from '../assets/traditional-saree-landscape.jpg'
import traditionalFusionLandscape from '../assets/traditional-fusion-landscape.jpg'
import traditionalFestival from '../assets/traditional-festival.jpg'
import streetLook from '../assets/look-street.jpg'
import formalLook from '../assets/look-formal.jpg'
import heroFashion from '../assets/hero-fashion.jpg'
import skinCardImage from '../assets/card-skin-analysis.jpg'
import skinToneSample from '../assets/skin-tone-sample.jpg'
import sareeMaterial from '../assets/saree-material.jpg'
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
  { type: 'TRADITIONAL', title: 'Silk, handloom\nand ceremony', image: traditionalSareeLandscape, colors: ['#7A2633', '#C99A42', '#F5EBD8'] },
  { type: 'MODERN', title: 'Tailoring for\nthe city', image: formalLook, colors: ['#1E2430', '#C9D2E3', '#F4F1EA'] },
  { type: 'FUSION', title: 'East and west\nin one look', image: traditionalFusionLandscape, colors: ['#762D36', '#2C3344', '#E0B15A'] },
  { type: 'OCCASION', title: 'Festival, wedding\nand night', image: traditionalFestival, colors: ['#7A1F2B', '#C99A42', '#1A1210'] },
]

export default function HomePage() {
  return (
    <main className="home-mix">
      <section className="mix-hero">
        <div className="mix-hero-image">
          <img className="mix-hero-main" src={traditionalHero} alt="Man in veshti and woman in silk — colour on skin" />
          <img className="mix-hero-inset mix-hero-inset-a" src={heroFashion} alt="Young man testing a colour against skin" />
          <img className="mix-hero-inset mix-hero-inset-b" src={skinCardImage} alt="Woman comparing silk swatches to skin tone" />
          <div className="mix-hero-vignette" />
        </div>
        <div className="mix-hero-copy">
          <p className="hero-reward">
            <Sparkles size={15} /> COLOUR FIRST <b>SKIN TONE · PALETTE · THEN CLOTH</b>
          </p>
          <p className="mix-kicker">HUEFIT / PERSONAL COLOUR ANALYSIS</p>
          <h1>
            FIND THE COLOURS<br />
            THAT FEEL <em>LIKE YOU.</em>
          </h1>
          <p className="hero-sub">
            Start with your skin tone. HueFit builds a personal colour palette,
            then recommends cloth that sits well on that palette — traditional, modern or fusion.
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
              Colour analysis is the product. Outfit recommendation is the second layer —
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
          <p className="micro dark">HOW COLOUR SITS ON CLOTH</p>
          <div className="mix-strip-grid" style={{ marginTop: 22 }}>
            <figure className="fit-hand"><div className="mix-strip-frame"><img src={skinToneSample} alt="Skin tone next to silk" /></div><figcaption>Skin signal</figcaption></figure>
            <figure className="fit-portrait"><div className="mix-strip-frame"><img src={traditionalSareeLandscape} alt="Colour on traditional silk" /></div><figcaption>On traditional cloth</figcaption></figure>
            <figure className="fit-walk"><div className="mix-strip-frame"><img src={streetLook} alt="Colour on modern cloth" /></div><figcaption>On modern cloth</figcaption></figure>
            <figure className="fit-portrait"><div className="mix-strip-frame"><img src={traditionalFusionLandscape} alt="Colour on fusion cloth" /></div><figcaption>On fusion cloth</figcaption></figure>
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
              <span>↘</span>
            </article>
            <article>
              <b>02</b>
              <div>
                <h3>See your personal palette</h3>
                <p>HueFit turns that signal into colour families that work on your skin.</p>
              </div>
              <span>↘</span>
            </article>
            <article>
              <b>03</b>
              <div>
                <h3>Choose the clothes type</h3>
                <p>Occasion, dress type and style — traditional, modern or fusion — then get the outfit edit.</p>
              </div>
              <span>↘</span>
            </article>
            <Link to="/analyze" className="under-link">Analyse my colours <ChevronRight size={18} /></Link>
          </div>
        </div>
      </section>

      <section className="lookbook mix-lookbook" id="looks">
        <div className="wide">
          <div className="section-top">
            <p className="micro">CLOTHES TYPE — AFTER COLOUR</p>
            <span>TRADITIONAL · MODERN · FUSION · OCCASION</span>
          </div>
          <div className="look-head">
            <h2>The palette stays.<br /><em>The cloth changes.</em></h2>
            <p>Same colour profile. Different clothes types<br />for ceremony, city and everyday.</p>
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
        <img src={traditionalFestival} alt="" />
        <div className="statement-copy">
          <p className="micro">COLOUR FIRST · CLOTH SECOND</p>
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
            <img src={sareeMaterial} alt="Kanjivaram silk cloth" />
          </div>
        </div>
      </section>
    </main>
  )
}
