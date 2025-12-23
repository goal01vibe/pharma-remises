import { Skeleton } from "@/components/ui/skeleton"

interface SkeletonTableProps {
  columns: number
  rows?: number
  showHeader?: boolean
  rowHeight?: number
}

export function SkeletonTable({
  columns,
  rows = 10,
  showHeader = true,
  rowHeight = 48
}: SkeletonTableProps) {
  // Varied widths for realism
  const widths = ['60%', '80%', '40%', '70%', '50%', '90%', '35%', '65%']

  return (
    <div className="w-full">
      {showHeader && (
        <div className="flex border-b border-gray-200 bg-gray-50 py-3">
          {Array.from({ length: columns }).map((_, i) => (
            <div key={i} className="flex-1 px-4">
              <Skeleton className="h-4 w-20" />
            </div>
          ))}
        </div>
      )}
      <div>
        {Array.from({ length: rows }).map((_, rowIndex) => (
          <div
            key={rowIndex}
            className="flex border-b border-gray-100"
            style={{ height: rowHeight }}
          >
            {Array.from({ length: columns }).map((_, colIndex) => (
              <div key={colIndex} className="flex-1 px-4 py-3">
                <Skeleton
                  className="h-4"
                  style={{ width: widths[(rowIndex + colIndex) % widths.length] }}
                />
              </div>
            ))}
          </div>
        ))}
      </div>
    </div>
  )
}
