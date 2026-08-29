import type { Tier } from '../../types'

export function TierSeparator({ tier }: { tier: Tier }) {
  return (
    <tr className="select-none">
      <td colSpan={20} className="py-0.5 px-3">
        <div className="flex items-center gap-3 py-1.5">
          <div className="h-px flex-1 bg-border/40" />
          <span className="text-[9px] font-condensed font-semibold tracking-[0.2em] text-text-muted/50 uppercase">
            {tier.label}
          </span>
          <div className="h-px flex-1 bg-border/40" />
        </div>
      </td>
    </tr>
  )
}
