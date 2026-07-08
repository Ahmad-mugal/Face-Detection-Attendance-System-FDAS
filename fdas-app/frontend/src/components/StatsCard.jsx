/**
 * StatsCard — Reusable metric card matching Stitch design
 *
 * Props:
 *   title       - Card heading text
 *   value       - Main numeric or text value
 *   subtitle    - Optional secondary value (e.g., "88%")
 *   icon        - Material Symbols icon name
 *   iconColor   - Hex color for icon
 *   borderColor - Left border accent color (optional)
 *   topBorder   - Use top border instead of left (optional bool)
 *   filled      - Use filled icon variant (optional bool)
 */
export default function StatsCard({
  title,
  value,
  subtitle,
  icon,
  iconColor = '#D4A017',
  borderColor,
  topBorder = false,
  filled = false,
}) {
  const borderStyle = borderColor
    ? topBorder
      ? { borderTop: `3px solid ${borderColor}` }
      : { borderLeft: `4px solid ${borderColor}` }
    : {}

  return (
    <div
      className="rounded-xl p-5 flex flex-col justify-between min-h-[120px]"
      style={{
        backgroundColor: '#FFF0E6',
        boxShadow: '0 4px 15px rgba(232,146,74,0.15)',
        ...borderStyle,
      }}
    >
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-xs font-bold uppercase tracking-wider" style={{ color: '#55433b' }}>
          {title}
        </h3>
        <span
          className={`material-symbols-outlined text-[22px] ${filled ? 'filled' : ''}`}
          style={{ color: iconColor }}
        >
          {icon}
        </span>
      </div>
      <div className="flex items-baseline gap-2 mt-auto">
        <span className="text-3xl font-bold leading-tight" style={{ color: '#4A2B0F' }}>
          {value}
        </span>
        {subtitle && (
          <span className="text-xs font-semibold" style={{ color: iconColor }}>
            {subtitle}
          </span>
        )}
      </div>
    </div>
  )
}
