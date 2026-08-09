import { Outlet } from 'react-router-dom'

export default function Layout() {
  return (
    <div className="min-h-screen bg-bg-primary text-text-primary">
      <Outlet />
    </div>
  )
}
