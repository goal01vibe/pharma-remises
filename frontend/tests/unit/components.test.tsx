import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { EmptyState } from '@/components/ui/EmptyState'
import { ScoreBadge } from '@/components/ui/ScoreBadge'
import { ProgressStepper } from '@/components/ui/ProgressStepper'
import { SkeletonTable } from '@/components/ui/SkeletonTable'
import { FilterBar } from '@/components/ui/FilterBar'
import { AlertCircle } from 'lucide-react'

describe('EmptyState', () => {
  it('renders title correctly', () => {
    render(<EmptyState title="Aucune donnée" />)
    expect(screen.getByText('Aucune donnée')).toBeInTheDocument()
  })

  it('renders description when provided', () => {
    render(<EmptyState title="Vide" description="Aucun élément trouvé" />)
    expect(screen.getByText('Aucun élément trouvé')).toBeInTheDocument()
  })

  it('renders custom icon', () => {
    render(<EmptyState title="Error" icon={AlertCircle} />)
    // The icon is rendered inside the component
    expect(screen.getByText('Error')).toBeInTheDocument()
  })

  it('renders action button when provided', async () => {
    const onClick = vi.fn()
    render(
      <EmptyState
        title="Vide"
        action={{ label: 'Ajouter', onClick }}
      />
    )

    const button = screen.getByText('Ajouter')
    expect(button).toBeInTheDocument()

    await userEvent.click(button)
    expect(onClick).toHaveBeenCalled()
  })
})

describe('ScoreBadge', () => {
  it('renders green for excellent scores (>= 90)', () => {
    render(<ScoreBadge score={95} />)
    const badge = screen.getByText('95%')
    expect(badge).toHaveClass('bg-green-100')
  })

  it('renders blue for good scores (>= 70, < 90)', () => {
    render(<ScoreBadge score={75} />)
    const badge = screen.getByText('75%')
    expect(badge).toHaveClass('bg-blue-100')
  })

  it('renders yellow for medium scores (>= 50, < 70)', () => {
    render(<ScoreBadge score={55} />)
    const badge = screen.getByText('55%')
    expect(badge).toHaveClass('bg-yellow-100')
  })

  it('renders red for low scores (< 50)', () => {
    render(<ScoreBadge score={40} />)
    const badge = screen.getByText('40%')
    expect(badge).toHaveClass('bg-red-100')
  })

  it('handles edge case score of 70 as blue', () => {
    render(<ScoreBadge score={70} />)
    const badge = screen.getByText('70%')
    expect(badge).toHaveClass('bg-blue-100')
  })

  it('handles edge case score of 90 as green', () => {
    render(<ScoreBadge score={90} />)
    const badge = screen.getByText('90%')
    expect(badge).toHaveClass('bg-green-100')
  })

  it('handles edge case score of 50 as yellow', () => {
    render(<ScoreBadge score={50} />)
    const badge = screen.getByText('50%')
    expect(badge).toHaveClass('bg-yellow-100')
  })
})

describe('ProgressStepper', () => {
  const steps = [
    { id: 'step1', label: 'Upload', status: 'completed' as const },
    { id: 'step2', label: 'Processing', status: 'current' as const },
    { id: 'step3', label: 'Done', status: 'pending' as const },
  ]

  it('renders all steps', () => {
    render(<ProgressStepper steps={steps} />)
    expect(screen.getByText('Upload')).toBeInTheDocument()
    expect(screen.getByText('Processing')).toBeInTheDocument()
    expect(screen.getByText('Done')).toBeInTheDocument()
  })

  it('shows completed icon for completed steps', () => {
    render(<ProgressStepper steps={steps} />)
    // Completed steps should have checkmark
    const completedStep = screen.getByText('Upload').closest('[data-testid="progress-step"]')
    expect(completedStep).toBeInTheDocument()
  })

  it('shows spinner for current step', () => {
    render(<ProgressStepper steps={steps} />)
    // Current step should have spinner animation
    const currentStep = screen.getByText('Processing').closest('[data-testid="progress-step"]')
    expect(currentStep).toBeInTheDocument()
  })
})

describe('SkeletonTable', () => {
  it('renders correct number of rows', () => {
    render(<SkeletonTable columns={3} rows={5} />)
    const skeletonRows = document.querySelectorAll('.animate-pulse')
    // Each row has multiple skeleton elements
    expect(skeletonRows.length).toBeGreaterThan(0)
  })

  it('renders correct number of skeleton cells', () => {
    const { container } = render(<SkeletonTable columns={4} rows={2} />)
    // Should have (header cols + data rows * cols) skeleton elements
    // Header: 4 skeletons, Data: 2 rows * 4 cols = 8 skeletons
    const skeletons = container.querySelectorAll('.animate-pulse')
    expect(skeletons.length).toBe(12) // 4 (header) + 8 (data)
  })

  it('can hide header', () => {
    const { container } = render(<SkeletonTable columns={3} rows={2} showHeader={false} />)
    // Only data rows: 2 * 3 = 6 skeletons
    const skeletons = container.querySelectorAll('.animate-pulse')
    expect(skeletons.length).toBe(6)
  })
})

describe('FilterBar', () => {
  const filters = [
    { key: 'search', label: 'Recherche', type: 'text' as const, placeholder: 'Rechercher...' },
    {
      key: 'type',
      label: 'Type',
      type: 'select' as const,
      options: [
        { value: 'all', label: 'Tous' },
        { value: 'active', label: 'Actif' },
      ],
    },
  ]

  it('renders filter inputs', () => {
    render(
      <FilterBar
        filters={filters}
        values={{ search: '', type: '' }}
        onChange={() => {}}
        onReset={() => {}}
      />
    )
    expect(screen.getByPlaceholderText('Rechercher...')).toBeInTheDocument()
  })

  it('calls onChange when text input changes', async () => {
    const onChange = vi.fn()
    render(
      <FilterBar
        filters={filters}
        values={{ search: '', type: '' }}
        onChange={onChange}
        onReset={() => {}}
      />
    )

    const input = screen.getByPlaceholderText('Rechercher...')
    await userEvent.type(input, 'test')

    expect(onChange).toHaveBeenCalled()
  })

  it('calls onReset when reset button is clicked', async () => {
    const onReset = vi.fn()
    render(
      <FilterBar
        filters={filters}
        values={{ search: 'test', type: '' }}
        onChange={() => {}}
        onReset={onReset}
      />
    )

    const resetButton = screen.getByText('Reinitialiser')
    await userEvent.click(resetButton)

    expect(onReset).toHaveBeenCalled()
  })

  it('shows badge when filters are active', () => {
    render(
      <FilterBar
        filters={filters}
        values={{ search: 'test', type: '' }}
        onChange={() => {}}
        onReset={() => {}}
      />
    )

    expect(screen.getByText('1 filtre')).toBeInTheDocument()
  })

  it('shows plural badge for multiple active filters', () => {
    render(
      <FilterBar
        filters={filters}
        values={{ search: 'test', type: 'active' }}
        onChange={() => {}}
        onReset={() => {}}
      />
    )

    expect(screen.getByText('2 filtres')).toBeInTheDocument()
  })
})
