import { RunProvider } from './lib/runStore'
import { NewTrial } from './pages/NewTrial'

// One route. The trial is one continuous page: intake, then the advocates,
// then the judges, then the verdict — sections that appear as the run reaches
// them, not screens the user navigates between.

export function App() {
  return (
    <RunProvider>
      <NewTrial />
    </RunProvider>
  )
}
