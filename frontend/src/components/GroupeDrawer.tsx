import { useQuery } from '@tanstack/react-query'
import { Sheet, SheetContent, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { Star, Copy, ExternalLink } from 'lucide-react'
import { toast } from 'sonner'
import api from '@/lib/api'

interface GroupeEquivalent {
  cip13: string
  denomination: string
  labo?: string
  pfht?: number
  conditionnement?: number
}

interface GroupePrinceps {
  cip13: string
  denomination: string
  pfht?: number
  conditionnement?: number
}

interface GroupeStats {
  nb_references: number
  nb_labos: number
}

interface GroupeDetailsResponse {
  princeps?: GroupePrinceps
  equivalents: GroupeEquivalent[]
  stats: GroupeStats
}

interface GroupeDrawerProps {
  groupeId: number | null
  currentCip?: string
  open: boolean
  onClose: () => void
}

export function GroupeDrawer({ groupeId, currentCip, open, onClose }: GroupeDrawerProps) {
  const { data, isLoading, error } = useQuery<GroupeDetailsResponse>({
    queryKey: ['groupe-details', groupeId],
    queryFn: () => api.get(`/api/groupe/${groupeId}/details`).then((r: { data: GroupeDetailsResponse }) => r.data),
    enabled: !!groupeId && open
  })

  const copyAllCips = () => {
    if (!data?.equivalents) return
    const cips = data.equivalents.map((e) => e.cip13).join('\n')
    navigator.clipboard.writeText(cips)
    toast.success('CIP copies dans le presse-papier')
  }

  const copyCip = (cip: string) => {
    navigator.clipboard.writeText(cip)
    toast.success('CIP copie')
  }

  return (
    <Sheet open={open} onOpenChange={() => onClose()}>
      <SheetContent className="w-[400px] sm:w-[540px] overflow-y-auto">
        <SheetHeader>
          <SheetTitle>Groupe Generique #{groupeId}</SheetTitle>
        </SheetHeader>

        {isLoading && (
          <div className="space-y-4 py-4">
            <Skeleton className="h-24 w-full" />
            <Skeleton className="h-8 w-40" />
            <div className="space-y-2">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-16 w-full" />
              ))}
            </div>
          </div>
        )}

        {error && (
          <div className="py-8 text-center text-red-600">
            Erreur lors du chargement
          </div>
        )}

        {data && (
          <div className="space-y-6 py-4">
            {/* Princeps */}
            {data.princeps && (
              <div>
                <h3 className="flex items-center gap-2 font-semibold mb-2">
                  <Star className="h-4 w-4 text-yellow-500" />
                  Princeps Referent
                </h3>
                <div className="p-3 bg-blue-50 rounded-lg border border-blue-200">
                  <p className="font-bold">
                    {data.princeps.denomination}
                    {data.princeps.conditionnement && (
                      <span className="ml-2 text-sm font-normal text-blue-600">
                        ({data.princeps.conditionnement} u.)
                      </span>
                    )}
                  </p>
                  <div className="flex items-center justify-between text-sm text-muted-foreground mt-1">
                    <span>CIP: {data.princeps.cip13}</span>
                    <span>PFHT: {data.princeps.pfht?.toFixed(2)} EUR</span>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="mt-2 h-7 text-xs"
                    onClick={() => data.princeps && copyCip(data.princeps.cip13)}
                  >
                    <Copy className="h-3 w-3 mr-1" />
                    Copier CIP
                  </Button>
                </div>
              </div>
            )}

            {/* Stats */}
            <div className="flex gap-4">
              <div className="bg-gray-100 rounded-lg px-4 py-2 text-center">
                <div className="text-2xl font-bold">{data.stats.nb_references}</div>
                <div className="text-xs text-gray-500">References</div>
              </div>
              <div className="bg-gray-100 rounded-lg px-4 py-2 text-center">
                <div className="text-2xl font-bold">{data.stats.nb_labos}</div>
                <div className="text-xs text-gray-500">Laboratoires</div>
              </div>
            </div>

            {/* Equivalents */}
            <div>
              <h3 className="font-semibold mb-2">
                Equivalents Generiques ({data.equivalents.length})
              </h3>
              <div className="space-y-1">
                {data.equivalents.map((equiv) => (
                  <div
                    key={equiv.cip13}
                    className={`p-2 rounded ${
                      equiv.cip13 === currentCip
                        ? 'bg-green-100 border border-green-300'
                        : 'bg-gray-50 hover:bg-gray-100'
                    }`}
                  >
                    <div className="flex justify-between items-start">
                      <div className="flex-1">
                        <p className="text-sm font-medium">
                          {equiv.denomination}
                          {equiv.conditionnement && (
                            <span className="ml-1 text-xs text-muted-foreground">
                              ({equiv.conditionnement} u.)
                            </span>
                          )}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          CIP: {equiv.cip13}
                        </p>
                      </div>
                      <div className="text-right flex items-center gap-2">
                        {equiv.labo && (
                          <Badge variant="outline" className="text-xs">
                            {equiv.labo}
                          </Badge>
                        )}
                        <span className="text-sm font-medium">
                          {equiv.pfht?.toFixed(2)} EUR
                        </span>
                      </div>
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="mt-1 h-6 text-xs"
                      onClick={() => copyCip(equiv.cip13)}
                    >
                      <Copy className="h-3 w-3 mr-1" />
                      Copier CIP
                    </Button>
                  </div>
                ))}
              </div>
            </div>

            {/* Actions */}
            <div className="flex gap-2 pt-4 border-t">
              <Button variant="outline" size="sm" onClick={copyAllCips}>
                <Copy className="h-4 w-4 mr-2" />
                Copier tous les CIP
              </Button>
              <Button variant="outline" size="sm" asChild>
                <a href={`/repertoire?groupe=${groupeId}`}>
                  <ExternalLink className="h-4 w-4 mr-2" />
                  Voir dans Repertoire
                </a>
              </Button>
            </div>
          </div>
        )}
      </SheetContent>
    </Sheet>
  )
}
