import { useEffect, useRef } from 'react'

/* ── Ethereum Blockies ──────────────────────────────────────────────
   Deterministic 8×8 pixel-art identicon from an Ethereum address.
   Pure implementation – zero external dependencies.
   ────────────────────────────────────────────────────────────────── */

// Simple seedable PRNG (same one used by the original ethereum/blockies)
function createRng(seed: string) {
  const randseed = new Array(4).fill(0)
  for (let i = 0; i < seed.length; i++) {
    randseed[i % 4] = (randseed[i % 4] << 5) - randseed[i % 4] + seed.charCodeAt(i)
  }
  return function rand() {
    const t = randseed[0] ^ (randseed[0] << 11)
    randseed[0] = randseed[1]
    randseed[1] = randseed[2]
    randseed[2] = randseed[3]
    randseed[3] = randseed[3] ^ (randseed[3] >> 19) ^ t ^ (t >> 8)
    return (randseed[3] >>> 0) / ((1 << 31) >>> 0)
  }
}

function hsl(h: number, s: number, l: number): string {
  return `hsl(${Math.floor(h * 360)},${Math.floor(s * 100)}%,${Math.floor(l * 100)}%)`
}

function createColor(rand: () => number) {
  const h = rand()
  const s = rand() * 0.6 + 0.4
  const l = (rand() + rand() + rand() + rand()) * 0.25
  return hsl(h, s, l)
}

function createImageData(seed: string) {
  const rand = createRng(seed.toLowerCase())
  const color = createColor(rand)
  const bgColor = createColor(rand)
  const spotColor = createColor(rand)
  const size = 8
  const data: number[] = []
  for (let y = 0; y < size; y++) {
    const row: number[] = []
    for (let x = 0; x < Math.ceil(size / 2); x++) {
      const val = Math.floor(rand() * 2.3)
      row.push(val)
    }
    // Mirror horizontally
    const mirror = [...row].reverse().slice(size % 2 === 0 ? 0 : 1)
    data.push(...row, ...mirror)
  }
  return { data, color, bgColor, spotColor, size }
}

export default function Blockies({ address, size = 24 }: { address: string; size?: number }) {
  const ref = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = ref.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const img = createImageData(address)
    const scale = size / img.size

    canvas.width = size
    canvas.height = size

    for (let i = 0; i < img.data.length; i++) {
      const x = (i % img.size) * scale
      const y = Math.floor(i / img.size) * scale
      ctx.fillStyle = img.data[i] === 0 ? img.bgColor : img.data[i] === 1 ? img.color : img.spotColor
      ctx.fillRect(x, y, scale, scale)
    }
  }, [address, size])

  return <canvas ref={ref} className="blockies" width={size} height={size} title={address} />
}
