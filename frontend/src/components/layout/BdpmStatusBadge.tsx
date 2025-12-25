import { useRef, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Database, AlertTriangle, CheckCircle, Clock, Upload, Loader2 } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { repertoireApi } from '@/lib/api'
import { toast } from 'sonner'

export function BdpmStatusBadge() {
  const queryClient = useQueryClient()
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [isUploading, setIsUploading] = useState(false)

  const { data: status, isLoading } = useQuery({
    queryKey: ['bdpm-status'],
    queryFn: repertoireApi.getBdpmStatus,
    refetchInterval: 60000, // Refresh every minute
    staleTime: 30000,
  })

  const uploadMutation = useMutation({
    mutationFn: (files: File[]) => repertoireApi.uploadBdpmFiles(files),
    onMutate: () => setIsUploading(true),
    onSuccess: (data) => {
      setIsUploading(false)
      queryClient.invalidateQueries({ queryKey: ['bdpm-status'] })
      queryClient.invalidateQueries({ queryKey: ['repertoire-stats'] })
      queryClient.invalidateQueries({ queryKey: ['repertoire-list'] })

      const successFiles = data.files_uploaded.filter(f => f.status === 'ok')
      const errorFiles = data.files_uploaded.filter(f => f.status === 'error')

      if (successFiles.length > 0) {
        toast.success(`${successFiles.length} fichier(s) importe(s)`, {
          description: data.integration
            ? `${data.integration.new_cips || 0} nouveaux CIP`
            : undefined
        })
      }
      if (errorFiles.length > 0) {
        toast.error(`${errorFiles.length} fichier(s) en erreur`, {
          description: errorFiles.map(f => f.message).join(', ')
        })
      }
    },
    onError: (error) => {
      setIsUploading(false)
      toast.error('Erreur lors de l\'upload', {
        description: error instanceof Error ? error.message : 'Erreur inconnue'
      })
    }
  })

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files
    if (files && files.length > 0) {
      uploadMutation.mutate(Array.from(files))
    }
    // Reset input to allow re-uploading same files
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }

  if (isLoading) {
    return (
      <Badge variant="outline" className="gap-1">
        <Database className="h-3 w-3" />
        BDPM...
      </Badge>
    )
  }

  const getStatusConfig = () => {
    switch (status?.status) {
      case 'ok':
        return {
          variant: 'default' as const,
          icon: CheckCircle,
          className: 'bg-green-100 text-green-800 border-green-200',
        }
      case 'warning':
        return {
          variant: 'secondary' as const,
          icon: Clock,
          className: 'bg-yellow-100 text-yellow-800 border-yellow-200',
        }
      case 'outdated':
        return {
          variant: 'destructive' as const,
          icon: AlertTriangle,
          className: 'bg-red-100 text-red-800 border-red-200',
        }
      default:
        return {
          variant: 'outline' as const,
          icon: Database,
          className: '',
        }
    }
  }

  const config = getStatusConfig()
  const Icon = config.icon

  return (
    <div className="flex items-center gap-1">
      <Badge
        variant={config.variant}
        className={`gap-1 cursor-pointer ${config.className}`}
        title={status?.message || 'BDPM'}
      >
        <Icon className="h-3 w-3" />
        <span className="hidden sm:inline">{status?.message || 'BDPM'}</span>
        <span className="sm:hidden">BDPM</span>
      </Badge>

      {/* Bouton upload manuel BDPM */}
      <input
        ref={fileInputRef}
        type="file"
        multiple
        accept=".txt"
        onChange={handleFileChange}
        className="hidden"
      />
      <Button
        variant="ghost"
        size="icon"
        className="h-7 w-7"
        onClick={() => fileInputRef.current?.click()}
        disabled={isUploading}
        title="Importer fichiers BDPM manuellement (CIS_bdpm.txt, CIS_CIP_bdpm.txt, CIS_GENER_bdpm.txt)"
      >
        {isUploading ? (
          <Loader2 className="h-4 w-4 animate-spin" />
        ) : (
          <Upload className="h-4 w-4" />
        )}
      </Button>
    </div>
  )
}
