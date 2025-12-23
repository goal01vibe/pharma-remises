import { useState, useEffect, useCallback, useRef, useSyncExternalStore } from 'react'

// Custom hook to track pending state without triggering effect warnings
function usePendingState() {
  const pendingRef = useRef(false)
  const listenersRef = useRef(new Set<() => void>())

  const subscribe = useCallback((listener: () => void) => {
    listenersRef.current.add(listener)
    return () => listenersRef.current.delete(listener)
  }, [])

  const getSnapshot = useCallback(() => pendingRef.current, [])

  const setPending = useCallback((value: boolean) => {
    pendingRef.current = value
    listenersRef.current.forEach(listener => listener())
  }, [])

  const isPending = useSyncExternalStore(subscribe, getSnapshot, getSnapshot)

  return { isPending, setPending }
}

export function useDebounceSearch(
  searchFn: (query: string) => void,
  delay: number = 300
) {
  const [searchTerm, setSearchTerm] = useState('')
  const { isPending: isSearching, setPending } = usePendingState()
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    if (!searchTerm) {
      searchFn('')
      return
    }

    // Clear existing timeout
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current)
    }

    // Set pending via ref-based state
    setPending(true)

    timeoutRef.current = setTimeout(() => {
      searchFn(searchTerm)
      setPending(false)
      timeoutRef.current = null
    }, delay)

    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current)
        timeoutRef.current = null
      }
    }
  }, [searchTerm, delay, searchFn, setPending])

  const clearSearch = useCallback(() => {
    setSearchTerm('')
    setPending(false)
  }, [setPending])

  return { searchTerm, setSearchTerm, isSearching, clearSearch }
}
