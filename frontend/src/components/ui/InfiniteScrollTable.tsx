import { useEffect } from 'react'
import { useInView } from 'react-intersection-observer'
import { Loader2 } from 'lucide-react'
import { VirtualizedTable } from './VirtualizedTable'
import { useInfinitePagination } from '@/hooks/useInfinitePagination'

interface Column<T> {
  key: string
  header: string
  width?: string
  render?: (item: T) => React.ReactNode
}

interface PaginatedResponse<T> {
  items: T[]
  next_cursor: string | null
  total_count: number
}

interface InfiniteScrollTableProps<T> {
  queryKey: string[]
  queryFn: (cursor: string | null) => Promise<PaginatedResponse<T>>
  columns: Column<T>[]
  rowHeight?: number
  onRowClick?: (row: T) => void
  getRowId?: (row: T) => string | number
}

export function InfiniteScrollTable<T>({
  queryKey,
  queryFn,
  columns,
  rowHeight = 48,
  onRowClick,
  getRowId
}: InfiniteScrollTableProps<T>) {
  const { ref, inView } = useInView({ threshold: 0 })

  const {
    data,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
    isLoading,
    error
  } = useInfinitePagination<T>(queryKey, queryFn)

  useEffect(() => {
    if (inView && hasNextPage && !isFetchingNextPage) {
      fetchNextPage()
    }
  }, [inView, hasNextPage, isFetchingNextPage, fetchNextPage])

  if (error) {
    return (
      <div className="p-4 text-red-600">
        Erreur de chargement: {(error as Error).message}
      </div>
    )
  }

  return (
    <div className="w-full">
      <VirtualizedTable
        data={data?.items ?? []}
        columns={columns}
        rowHeight={rowHeight}
        onRowClick={onRowClick}
        isLoading={isLoading}
        getRowId={getRowId}
      />

      {/* Sentinel for infinite scroll */}
      <div ref={ref} className="h-4" />

      {/* Loading indicator */}
      {isFetchingNextPage && (
        <div className="flex items-center justify-center py-4" data-testid="loading-more">
          <Loader2 className="h-6 w-6 animate-spin text-gray-400" />
          <span className="ml-2 text-sm text-gray-500">Chargement...</span>
        </div>
      )}

      {/* Total counter */}
      {data && (
        <div className="text-sm text-gray-500 text-center py-2">
          {data.items.length} / {data.totalCount} elements
        </div>
      )}
    </div>
  )
}
