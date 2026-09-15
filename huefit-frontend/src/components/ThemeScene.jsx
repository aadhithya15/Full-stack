import './ThemeScene.css'

export default function ThemeScene({ compact = false, caption = 'MIXED EDIT' }) {
  return (
    <div className={`theme-scene mixed-scene ${compact ? 'is-compact' : ''}`} aria-hidden="true">
      <div className="scene-stage">
        <i className="mix-glow" />
        <i className="mix-ring mix-ring-gold" />
        <i className="mix-ring mix-ring-steel" />
        <i className="mix-silk" />
        <i className="mix-glass" />
      </div>
      {caption ? <p className="scene-caption">{caption}</p> : null}
    </div>
  )
}
