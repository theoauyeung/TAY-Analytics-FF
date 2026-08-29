import { NavLink } from 'react-router-dom'
import {
  BarChart3, Users, Trophy,
  PieChart, Settings, ClipboardList, TrendingUp,
} from 'lucide-react'
import clsx from 'clsx'

const NAV_ITEMS = [
  { to: '/rankings',   label: 'Rankings',         icon: BarChart3 },
  { to: '/draft',      label: 'Draft Assistant',  icon: ClipboardList },
  { to: '/mock-draft', label: 'Mock Draft',        icon: Trophy },
  { to: '/players',    label: 'Players',           icon: Users },
  { to: '/roster',     label: 'Roster Analyzer',  icon: PieChart },
  { to: '/analytics',  label: 'Analytics',         icon: TrendingUp },
  { to: '/settings',   label: 'Settings',          icon: Settings },
]

export default function Sidebar() {
  return (
    <aside className="fixed left-0 top-0 h-screen w-56 bg-bg-secondary border-r border-border flex flex-col z-40">
      {/* Logo */}
      <div className="h-16 flex items-center px-4 border-b border-border gap-3">
        <img src="/theo-logo.png" alt="THEO" className="h-8 w-8 object-contain" style={{ filter: 'invert(1) brightness(0.85)' }} />
        <span className="text-text-primary font-semibold text-sm tracking-wide">TAY Analytics</span>
      </div>

      {/* Nav */}
      <nav className="flex-1 py-3 overflow-y-auto">
        {NAV_ITEMS.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              clsx(
                'flex items-center gap-3 px-5 py-2.5 text-sm transition-colors border-l-2',
                isActive
                  ? 'text-text-primary border-accent bg-bg-elevated/50 font-medium'
                  : 'text-text-muted hover:text-text-secondary hover:bg-bg-elevated/30 border-transparent'
              )
            }
          >
            <Icon size={15} className="flex-shrink-0" />
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
