import { cn } from "@/lib/utils"

interface ScoreBadgeProps {
  score: number
  size?: 'sm' | 'md' | 'lg'
  showLabel?: boolean
}

export function ScoreBadge({ score, size = 'md', showLabel = false }: ScoreBadgeProps) {
  const getColor = () => {
    if (score >= 90) return 'bg-green-100 text-green-800 border-green-200'
    if (score >= 70) return 'bg-blue-100 text-blue-800 border-blue-200'
    if (score >= 50) return 'bg-yellow-100 text-yellow-800 border-yellow-200'
    return 'bg-red-100 text-red-800 border-red-200'
  }

  const getLabel = () => {
    if (score >= 90) return 'Excellent'
    if (score >= 70) return 'Bon'
    if (score >= 50) return 'Moyen'
    return 'Faible'
  }

  const sizeClasses = {
    sm: 'text-xs px-1.5 py-0.5',
    md: 'text-sm px-2 py-1',
    lg: 'text-base px-3 py-1.5'
  }

  return (
    <span className={cn(
      'inline-flex items-center rounded-full border font-medium',
      getColor(),
      sizeClasses[size]
    )}>
      {score.toFixed(0)}%
      {showLabel && <span className="ml-1">({getLabel()})</span>}
    </span>
  )
}
