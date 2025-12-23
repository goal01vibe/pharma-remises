import { RefObject } from 'react'
import { useVirtualizer } from '@tanstack/react-virtual'

interface UseTableVirtualizationOptions {
  rowHeight: number
  overscan?: number
}

export function useTableVirtualization<T>(
  data: T[],
  containerRef: RefObject<HTMLElement>,
  options: UseTableVirtualizationOptions
) {
  const { rowHeight, overscan = 5 } = options

  const virtualizer = useVirtualizer({
    count: data.length,
    getScrollElement: () => containerRef.current,
    estimateSize: () => rowHeight,
    overscan
  })

  return {
    virtualRows: virtualizer.getVirtualItems(),
    totalSize: virtualizer.getTotalSize(),
    scrollToIndex: virtualizer.scrollToIndex
  }
}
