import { useState, useEffect, useCallback } from 'react'

export function useDebounceSearch(
  searchFn: (query: string) => void,
  delay: number = 300
) {
  const [searchTerm, setSearchTerm] = useState('')
  const [isSearching, setIsSearching] = useState(false)

  useEffect(() => {
    if (!searchTerm) {
      searchFn('')
      return
    }

    setIsSearching(true)
    const timer = setTimeout(() => {
      searchFn(searchTerm)
      setIsSearching(false)
    }, delay)

    return () => clearTimeout(timer)
  }, [searchTerm, delay, searchFn])

  const clearSearch = useCallback(() => {
    setSearchTerm('')
  }, [])

  return { searchTerm, setSearchTerm, isSearching, clearSearch }
}
