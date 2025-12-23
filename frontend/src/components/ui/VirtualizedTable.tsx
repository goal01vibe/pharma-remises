import { useRef } from 'react'
import { useVirtualizer } from '@tanstack/react-virtual'
import { SkeletonTable } from './SkeletonTable'
import { EmptyState } from './EmptyState'
import { cn } from '@/lib/utils'

interface Column<T> {
  key: string
  header: string
  width?: string
  render?: (item: T) => React.ReactNode
}

interface VirtualizedTableProps<T> {
  data: T[]
  columns: Column<T>[]
  rowHeight?: number
  overscan?: number
  containerHeight?: string
  onRowClick?: (row: T) => void
  selectedRowId?: string | number
  isLoading?: boolean
  emptyMessage?: string
  getRowId?: (row: T) => string | number
}

export function VirtualizedTable<T>({
  data,
  columns,
  rowHeight = 48,
  overscan = 5,
  containerHeight = 'calc(100vh - 200px)',
  onRowClick,
  selectedRowId,
  isLoading = false,
  emptyMessage = 'Aucune donnee',
  getRowId = (row: T) => (row as T & { id: string | number }).id
}: VirtualizedTableProps<T>) {
  const parentRef = useRef<HTMLDivElement>(null)

  const virtualizer = useVirtualizer({
    count: data.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => rowHeight,
    overscan
  })

  if (isLoading) {
    return <SkeletonTable columns={columns.length} rows={10} />
  }

  if (data.length === 0) {
    return <EmptyState title={emptyMessage} />
  }

  return (
    <div className="w-full border rounded-lg overflow-hidden">
      {/* Header */}
      <div className="flex bg-gray-50 border-b font-medium text-sm text-gray-700">
        {columns.map((col) => (
          <div
            key={col.key}
            className="px-4 py-3"
            style={{ width: col.width || 'auto', flex: col.width ? 'none' : 1 }}
          >
            {col.header}
          </div>
        ))}
      </div>

      {/* Virtualized Body */}
      <div
        ref={parentRef}
        className="overflow-auto"
        style={{ height: containerHeight }}
        data-testid="virtual-scroll-container"
      >
        <div
          style={{
            height: `${virtualizer.getTotalSize()}px`,
            width: '100%',
            position: 'relative'
          }}
        >
          {virtualizer.getVirtualItems().map((virtualRow) => {
            const item = data[virtualRow.index]
            const rowId = getRowId(item)
            const isSelected = rowId === selectedRowId

            return (
              <div
                key={virtualRow.key}
                className={cn(
                  'flex items-center border-b absolute w-full',
                  onRowClick && 'cursor-pointer hover:bg-gray-50',
                  isSelected && 'bg-blue-50'
                )}
                style={{
                  height: `${virtualRow.size}px`,
                  transform: `translateY(${virtualRow.start}px)`
                }}
                onClick={() => onRowClick?.(item)}
              >
                {columns.map((col) => (
                  <div
                    key={col.key}
                    className="px-4 py-2 truncate text-sm"
                    style={{ width: col.width || 'auto', flex: col.width ? 'none' : 1 }}
                  >
                    {col.render ? col.render(item) : String((item as Record<string, unknown>)[col.key] ?? '')}
                  </div>
                ))}
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
