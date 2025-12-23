import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act, waitFor } from '@testing-library/react'
import { useDebounceSearch } from '@/hooks/useDebounceSearch'

describe('useDebounceSearch', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('debounces search function calls', async () => {
    const searchFn = vi.fn()
    const { result } = renderHook(() => useDebounceSearch(searchFn, 300))

    // Type rapidly
    act(() => {
      result.current.setSearchTerm('t')
    })
    act(() => {
      result.current.setSearchTerm('te')
    })
    act(() => {
      result.current.setSearchTerm('tes')
    })
    act(() => {
      result.current.setSearchTerm('test')
    })

    // searchFn should not be called yet (except for initial empty call)
    expect(searchFn).toHaveBeenCalledTimes(1) // Initial empty call

    // Fast forward past debounce delay
    await act(async () => {
      vi.advanceTimersByTime(300)
    })

    // Now searchFn should be called with final value
    expect(searchFn).toHaveBeenCalledWith('test')
  })

  it('clears search term on clearSearch', () => {
    const searchFn = vi.fn()
    const { result } = renderHook(() => useDebounceSearch(searchFn))

    act(() => {
      result.current.setSearchTerm('test')
    })
    expect(result.current.searchTerm).toBe('test')

    act(() => {
      result.current.clearSearch()
    })
    expect(result.current.searchTerm).toBe('')
  })

  it('calls searchFn with empty string on empty searchTerm', () => {
    const searchFn = vi.fn()
    renderHook(() => useDebounceSearch(searchFn))

    expect(searchFn).toHaveBeenCalledWith('')
  })

  it('respects custom delay parameter', async () => {
    const searchFn = vi.fn()
    const { result } = renderHook(() => useDebounceSearch(searchFn, 500))

    act(() => {
      result.current.setSearchTerm('test')
    })

    // Advance by 300ms - should not have called yet
    await act(async () => {
      vi.advanceTimersByTime(300)
    })
    expect(searchFn).not.toHaveBeenCalledWith('test')

    // Advance by remaining 200ms
    await act(async () => {
      vi.advanceTimersByTime(200)
    })
    expect(searchFn).toHaveBeenCalledWith('test')
  })
})
