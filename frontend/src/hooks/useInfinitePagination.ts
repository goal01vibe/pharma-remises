import { useInfiniteQuery } from '@tanstack/react-query'

interface PaginatedResponse<T> {
  items: T[]
  next_cursor: string | null
  total_count: number
}

interface UseInfinitePaginationOptions {
  pageSize?: number
  staleTime?: number
  enabled?: boolean
}

export function useInfinitePagination<T>(
  queryKey: string[],
  fetchFn: (cursor: string | null) => Promise<PaginatedResponse<T>>,
  options: UseInfinitePaginationOptions = {}
) {
  const { staleTime = 30000, enabled = true } = options

  return useInfiniteQuery({
    queryKey,
    queryFn: ({ pageParam }) => fetchFn(pageParam),
    initialPageParam: null as string | null,
    getNextPageParam: (lastPage) => lastPage.next_cursor,
    staleTime,
    enabled,
    select: (data) => ({
      items: data.pages.flatMap(page => page.items),
      totalCount: data.pages[0]?.total_count ?? 0,
      pageCount: data.pages.length
    })
  })
}
