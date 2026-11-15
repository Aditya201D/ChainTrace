import { ShieldAlert, ShieldCheck } from 'lucide-react'

/* ── VerifyStamp ────────────────────────────────────────────────────
   Ceremonial verification animation:
   1. Shield icon "stamps" in with scale + rotation.
   2. SVG checkmark draws itself via stroke-dashoffset.
   3. Particle burst of 12 dots radiating outward.
   ────────────────────────────────────────────────────────────────── */

export default function VerifyStamp({ passed }: { passed: boolean }) {
  return (
    <div className="stamp-wrap" aria-label={passed ? 'Verification passed' : 'Verification failed'}>
      {/* Particle burst — 12 dots */}
      <div className="stamp-particles" aria-hidden="true">
        {Array.from({ length: 12 }, (_, i) => (
          <span
            key={i}
            className={passed ? 'particle-pass' : 'particle-fail'}
            style={{ '--angle': `${i * 30}deg` } as React.CSSProperties}
          />
        ))}
      </div>

      {/* Stamp icon */}
      <span className={'stamp-icon ' + (passed ? 'stamp-pass' : 'stamp-fail')}>
        {passed ? <ShieldCheck size={34} /> : <ShieldAlert size={34} />}
      </span>

      {/* Animated checkmark / cross overlay */}
      {passed ? (
        <svg className="stamp-check" viewBox="0 0 40 40" width="28" height="28" aria-hidden="true">
          <path
            d="M11 21 L17 27 L29 14"
            fill="none"
            stroke="#83dcb0"
            strokeWidth="3"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      ) : (
        <svg className="stamp-check stamp-cross" viewBox="0 0 40 40" width="28" height="28" aria-hidden="true">
          <path
            d="M13 13 L27 27 M27 13 L13 27"
            fill="none"
            stroke="#efa6a6"
            strokeWidth="3"
            strokeLinecap="round"
          />
        </svg>
      )}
    </div>
  )
}
