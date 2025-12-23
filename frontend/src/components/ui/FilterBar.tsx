import { X } from 'lucide-react'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Badge } from '@/components/ui/badge'

interface FilterConfig {
  key: string
  label: string
  type: 'text' | 'select'
  options?: { value: string; label: string }[]
  placeholder?: string
}

interface FilterBarProps {
  filters: FilterConfig[]
  values: Record<string, any>
  onChange: (key: string, value: any) => void
  onReset: () => void
}

export function FilterBar({ filters, values, onChange, onReset }: FilterBarProps) {
  const activeCount = Object.values(values).filter(v => v && v !== '').length

  return (
    <div className="flex items-center gap-3 p-4 bg-gray-50 rounded-lg mb-4">
      {filters.map((filter) => (
        <div key={filter.key} className="flex-1 max-w-xs">
          {filter.type === 'text' && (
            <Input
              placeholder={filter.placeholder || filter.label}
              value={values[filter.key] || ''}
              onChange={(e) => onChange(filter.key, e.target.value)}
            />
          )}
          {filter.type === 'select' && filter.options && (
            <Select
              value={values[filter.key] || ''}
              onValueChange={(v) => onChange(filter.key, v)}
            >
              <SelectTrigger>
                <SelectValue placeholder={filter.placeholder || filter.label} />
              </SelectTrigger>
              <SelectContent>
                {filter.options.map((opt) => (
                  <SelectItem key={opt.value} value={opt.value}>
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
        </div>
      ))}

      <div className="flex items-center gap-2">
        {activeCount > 0 && (
          <Badge variant="secondary">
            {activeCount} filtre{activeCount > 1 ? 's' : ''}
          </Badge>
        )}
        <Button variant="ghost" size="sm" onClick={onReset}>
          <X className="h-4 w-4 mr-1" />
          Reinitialiser
        </Button>
      </div>
    </div>
  )
}
