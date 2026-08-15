import { NavLink } from 'react-router-dom'
import {
  BarChart3, Users, Trophy,
  PieChart, Settings, Zap,
} from 'lucide-react'
import clsx from 'clsx'

const NAV_ITEMS = [
  { to: '/rankings',   label: 'Rankings',         icon: BarChart3 },
  { to: '/draft',      label: 'Draft Assistant',  icon: Zap },
  { to: '/mock-draft', label: 'Mock Draft',        icon: Trophy },
  { to: '/players',    label: 'Players',           icon: Users },
  { to: '/roster',     label: 'Roster Analyzer',  icon: PieChart },
  { to: '/settings',   label: 'Settings',          icon: Settings },
]

export default function Sidebar() {
  return (
    <aside className="fixed left-0 top-0 h-screen w-56 bg-bg-secondary border-r border-border flex flex-col z-40">
      {/* Logo */}
      <div className="h-16 flex items-center px-5 border-b border-border">
        <span className="text-accent font-bold text-lg tracking-tight">TAY</span>
        <span className="text-text-primary font-bold text-lg ml-1">Analytics</span>
      </div>

      {/* Nav */}
      <nav className="flex-1 py-4 overflow-y-auto">
        {NAV_ITEMS.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              clsx(
                'flex items-center gap-3 px-5 py-2.5 text-sm transition-colors',
                isActive
                  ? 'text-accent bg-accent-muted border-r-2 border-accent'
                  : 'text-text-secondary hover:text-text-primary hover:bg-bg-elevated'
              )
            }
          >
            <Icon size={16} />
            {label}
          </NavLink>
        ))}
      </nav>

      {/* Footer */}
      <div className="p-4 border-t border-border">
        <div className="text-xs text-text-muted">
          <div>Model v0.1-mock</div>
          <div>2026 Season</div>
        </div>
      </div>
    </aside>
  )
}
