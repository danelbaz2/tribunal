import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { RunProvider } from './lib/runStore'
import { NewTrial } from './pages/NewTrial'
import { Courtroom } from './pages/Courtroom'
import { Judgment } from './pages/Judgment'

// Three routes, one per screen. `Comparison.tsx` (ARCHITECTURE Part 5) has no
// route yet: it is deliberately outside this handoff and is not designed.

export function App() {
  return (
    <RunProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<NewTrial />} />
          <Route path="/courtroom" element={<Courtroom />} />
          <Route path="/judgment" element={<Judgment />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </RunProvider>
  )
}
