import { useState } from 'react'
import clsx from 'clsx'

interface Props { onStart: (pickPosition: number) => void }

const PICK_POSITIONS = Array.from({ length: 12 }, (_, i) => i + 1)

export function PreDraftConfig({ onStart }: Props) {
  const [pickPos, setPickPos] = useState(6)

  return (
    <div className="flex flex-col items-center justify-center h-full gap-8 p-8">
      <div className="text-center">
        <h2 className="text-xl font-bold text-text-primary">Configure Mock Draft</h2>
        <p className="text-sm text-text-secondary mt-1">12-team PPR · 13 rounds</p>
      </div>

      <div>
        <div className="text-sm font-medium text-text-secondary mb-3 text-center">
          Your Draft Position
        </div>
        <div className="grid grid-cols-6 gap-2">
          {PICK_POSITIONS.map(n => (
            <button
              key={n}
              onClick={() => setPickPos(n)}
              className={clsx(
                'w-10 h-10 rounded-lg text-sm font-medium transition-colors',
                pickPos === n
                  ? 'bg-accent text-bg-primary'
                  : 'bg-bg-card border border-border text-text-secondary hover:text-text-primary hover:border-accent'
              )}
            >
              {n}
            </button>
          ))}
        </div>
      </div>

      <button
        onClick={() => onStart(pickPos)}
        className="px-8 py-3 bg-accent text-bg-primary text-sm font-semibold rounded-lg hover:opacity-90 transition-opacity"
      >
        Start Mock Draft
      </button>
    </div>
  )
}
