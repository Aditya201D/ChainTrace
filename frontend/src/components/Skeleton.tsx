/* ── Skeleton Loading Placeholders ───────────────────────────────────
   Shimmer rectangles that match the shape of real content.
   ──────────────────────────────────────────────────────────────────── */

export function Skeleton({
  width,
  height = 14,
  borderRadius = 4,
  style,
}: {
  width?: number | string
  height?: number | string
  borderRadius?: number
  style?: React.CSSProperties
}) {
  return (
    <span
      className="skeleton"
      style={{ width, height, borderRadius, display: 'inline-block', ...style }}
    />
  )
}

export function SkeletonTable({ rows = 5 }: { rows?: number }) {
  return (
    <div className="skeleton-table" role="status" aria-label="Loading">
      <div className="skeleton-thead">
        <Skeleton width="12%" height={10} />
        <Skeleton width="22%" height={10} />
        <Skeleton width="10%" height={10} />
        <Skeleton width="10%" height={10} />
        <Skeleton width={20} height={10} />
      </div>
      {Array.from({ length: rows }, (_, i) => (
        <div className="skeleton-row" key={i} style={{ animationDelay: `${i * 60}ms` }}>
          <div className="skeleton-cell-artifact">
            <Skeleton width={35} height={35} borderRadius={8} />
            <div>
              <Skeleton width={80} height={11} />
              <Skeleton width={120} height={9} style={{ marginTop: 6 }} />
            </div>
          </div>
          <Skeleton width="55%" height={11} />
          <Skeleton width={70} height={11} />
          <Skeleton width={75} height={22} borderRadius={5} />
          <Skeleton width={20} height={20} borderRadius={4} />
        </div>
      ))}
    </div>
  )
}

export function SkeletonStatCard() {
  return (
    <div className="stat-card skeleton-stat">
      <div className="stat-top">
        <Skeleton width={90} height={11} />
        <Skeleton width={18} height={18} borderRadius={4} />
      </div>
      <div style={{ margin: '15px 0 7px' }}>
        <Skeleton width={60} height={34} borderRadius={6} />
      </div>
      <Skeleton width={130} height={10} />
    </div>
  )
}
