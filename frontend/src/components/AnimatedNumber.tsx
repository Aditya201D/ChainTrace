import { useEffect, useRef, useState } from 'react'

/* ── AnimatedNumber ─────────────────────────────────────────────────
   Counts from 0 → target value with ease-out cubic easing.
   Uses requestAnimationFrame for smooth 60fps animation.
   ────────────────────────────────────────────────────────────────── */

function easeOutCubic(t: number): number {
  return 1 - Math.pow(1 - t, 3)
}

export default function AnimatedNumber({
  value,
  duration = 900,
}: {
  value: number | undefined
  duration?: number
}) {
  const [display, setDisplay] = useState(0)
  const prevValue = useRef(0)
  const rafRef = useRef<number>()

  useEffect(() => {
    if (value === undefined) return

    const from = prevValue.current
    const to = value
    const startTime = performance.now()

    function tick(now: number) {
      const elapsed = now - startTime
      const progress = Math.min(elapsed / duration, 1)
      const eased = easeOutCubic(progress)
      const current = Math.round(from + (to - from) * eased)
      setDisplay(current)

      if (progress < 1) {
        rafRef.current = requestAnimationFrame(tick)
      } else {
        prevValue.current = to
      }
    }

    rafRef.current = requestAnimationFrame(tick)

    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current)
    }
  }, [value, duration])

  if (value === undefined) return <>—</>
  return <>{display.toLocaleString()}</>
}
