import { useState } from 'react'
import { Settings2 } from 'lucide-react'
import type { ColumnKey } from '../../types'
import { OPTIONAL_COLUMNS, COLUMN_LABELS } from '../../types'

interface Props {
  visibleColumns: ColumnKey[]
  onChange: (cols: ColumnKey[]) => void
}

export function ColumnToggle({ visibleColumns, onChange }: Props) {
  const [open, setOpen] = useState(false)

  function toggle(col: ColumnKey) {
    onChange(
      visibleColumns.includes(col)
        ? visibleColumns.filter((c) => c !== col)
        : [...visibleColumns, col]
    )
  }

  return (
    <div className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-text-secondary border border-border rounded-lg hover:text-text-primary hover:border-accent transition-colors"
      >
        <Settings2 size={13} />
        Columns
      </button>

      {open && (
        <div className="absolute right-0 top-9 z-50 w-48 bg-bg-elevated border border-border rounded-lg p-3 shadow-xl">
          <div className="text-xs font-medium text-text-secondary mb-2">Toggle Columns</div>
          {OPTIONAL_COLUMNS.map((col) => (
            <label key={col} className="flex items-center gap-2 py-1 cursor-pointer">
              <input
                type="checkbox"
                checked={visibleColumns.includes(col)}
                onChange={() => toggle(col)}
                className="accent-accent"
              />
              <span className="text-xs text-text-primary">{COLUMN_LABELS[col]}</span>
            </label>
          ))}
        </div>
      )}
    </div>
  )
}
