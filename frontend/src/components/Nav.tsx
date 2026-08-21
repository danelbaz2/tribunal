import { NavLink } from 'react-router-dom'

// The header bar, `.nav` from the design system. The right-hand slot carries
// the run's standing — "Run 24 · stage 1 of 2 · 3 of 4 statements in" — set
// tabular, because those are figures.

export function Nav({ status }: { status: string }) {
  return (
    <nav className="nav">
      <span className="nav-brand">Tribunal</span>
      <NavLink to="/">New trial</NavLink>
      <NavLink to="/courtroom">Courtroom</NavLink>
      <NavLink to="/judgment">Judgment</NavLink>
      <span className="text-muted tnum text-kicker">{status}</span>
    </nav>
  )
}
