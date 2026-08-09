import type { Tier } from '../../types'

export function TierSeparator({ tier }: { tier: Tier }) {
  return (
    <tr className="select-none">
      <td colSpan={20} className="py-1 px-3">
        <div className="flex items-center gap-3">
          <div className="h-px flex-1 bg-border" />
          <span className="text-xs font-bold tracking-widest text-text-muted uppercase">
            {tier.label}
          </span>
          <div className="h-px flex-1 bg-border" />
        </div>
      </td>
    </tr>
  )
}
