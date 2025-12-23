import { Check, Loader2, X, Circle } from "lucide-react"
import { cn } from "@/lib/utils"

interface Step {
  id: string
  label: string
  status: 'pending' | 'in_progress' | 'completed' | 'error'
  detail?: string
}

interface ProgressStepperProps {
  steps: Step[]
  orientation?: 'horizontal' | 'vertical'
}

export function ProgressStepper({ steps, orientation = 'horizontal' }: ProgressStepperProps) {
  const getIcon = (status: Step['status']) => {
    switch (status) {
      case 'completed':
        return <Check className="h-4 w-4 text-white" />
      case 'in_progress':
        return <Loader2 className="h-4 w-4 text-white animate-spin" />
      case 'error':
        return <X className="h-4 w-4 text-white" />
      default:
        return <Circle className="h-4 w-4 text-gray-400" />
    }
  }

  const getIconBg = (status: Step['status']) => {
    switch (status) {
      case 'completed':
        return 'bg-green-500'
      case 'in_progress':
        return 'bg-blue-500'
      case 'error':
        return 'bg-red-500'
      default:
        return 'bg-gray-200'
    }
  }

  if (orientation === 'vertical') {
    return (
      <div className="space-y-4">
        {steps.map((step, index) => (
          <div key={step.id} className="flex items-start gap-3" data-testid="progress-step">
            <div className="flex flex-col items-center">
              <div className={cn(
                'flex h-8 w-8 items-center justify-center rounded-full',
                getIconBg(step.status)
              )}>
                {getIcon(step.status)}
              </div>
              {index < steps.length - 1 && (
                <div className={cn(
                  'w-0.5 h-8 mt-1',
                  step.status === 'completed' ? 'bg-green-500' : 'bg-gray-200'
                )} />
              )}
            </div>
            <div>
              <p className={cn(
                'font-medium',
                step.status === 'pending' ? 'text-gray-400' : 'text-gray-900'
              )}>
                {step.label}
              </p>
              {step.detail && (
                <p className="text-sm text-gray-500">{step.detail}</p>
              )}
            </div>
          </div>
        ))}
      </div>
    )
  }

  return (
    <div className="flex items-center justify-between">
      {steps.map((step, index) => (
        <div key={step.id} className="flex items-center flex-1" data-testid="progress-step">
          <div className="flex flex-col items-center">
            <div className={cn(
              'flex h-8 w-8 items-center justify-center rounded-full',
              getIconBg(step.status)
            )}>
              {getIcon(step.status)}
            </div>
            <p className={cn(
              'text-xs mt-2 text-center',
              step.status === 'pending' ? 'text-gray-400' : 'text-gray-900'
            )}>
              {step.label}
            </p>
            {step.detail && (
              <p className="text-xs text-gray-500">{step.detail}</p>
            )}
          </div>
          {index < steps.length - 1 && (
            <div className={cn(
              'flex-1 h-0.5 mx-2',
              step.status === 'completed' ? 'bg-green-500' : 'bg-gray-200'
            )} />
          )}
        </div>
      ))}
    </div>
  )
}
