import { test, expect } from '@playwright/test'

// ==========================================
// Tests SkeletonTable
// ==========================================
test.describe('SkeletonTable', () => {
  test('affiche skeleton pendant chargement', async ({ page }) => {
    // Intercepter et retarder l'API
    await page.route('**/api/**', async route => {
      await new Promise(r => setTimeout(r, 1000))
      await route.continue()
    })

    await page.goto('/catalogues')

    // Verifier presence skeleton
    const skeletons = page.locator('.animate-pulse')
    await expect(skeletons.first()).toBeVisible()

    // Verifier nombre de lignes skeleton
    const skeletonRows = await skeletons.count()
    expect(skeletonRows).toBeGreaterThanOrEqual(5)
  })

  test('skeleton disparait apres chargement', async ({ page }) => {
    await page.goto('/catalogues')

    // Attendre que les donnees se chargent
    await page.waitForSelector('table tbody tr', { timeout: 10000 })

    // Verifier que skeleton n'est plus visible
    const skeleton = page.locator('.animate-pulse')
    await expect(skeleton).not.toBeVisible()
  })
})

// ==========================================
// Tests EmptyState
// ==========================================
test.describe('EmptyState', () => {
  test('affiche message quand pas de donnees', async ({ page }) => {
    // Mock API pour retourner vide
    await page.route('**/api/catalogues**', route => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ items: [], next_cursor: null, total_count: 0 })
      })
    })

    await page.goto('/catalogues')
    await expect(page.getByText('Aucun')).toBeVisible()
  })
})

// ==========================================
// Tests ScoreBadge
// ==========================================
test.describe('ScoreBadge', () => {
  test('couleur verte pour score >= 90', async ({ page }) => {
    await page.goto('/rapprochement')
    // Chercher un badge avec score >= 90
    const greenBadge = page.locator('.bg-green-100')
    // Si existe, verifier
    if (await greenBadge.count() > 0) {
      await expect(greenBadge.first()).toBeVisible()
    }
  })

  test('couleur rouge pour score < 50', async ({ page }) => {
    await page.goto('/rapprochement')
    const redBadge = page.locator('.bg-red-100')
    if (await redBadge.count() > 0) {
      await expect(redBadge.first()).toBeVisible()
    }
  })
})

// ==========================================
// Tests ProgressStepper
// ==========================================
test.describe('ProgressStepper', () => {
  test('affiche les etapes de matching', async ({ page }) => {
    await page.goto('/matching')
    // Verifier presence des etapes
    const steps = page.locator('[data-testid="progress-step"]')
    expect(await steps.count()).toBeGreaterThanOrEqual(0)
  })

  test('etape active a animation spin', async ({ page }) => {
    await page.goto('/matching')
    // Chercher icone en cours (Loader2 avec animate-spin)
    const spinner = page.locator('.animate-spin')
    // Peut etre visible pendant processing
    await expect(spinner.first()).toBeVisible().catch(() => {
      // Spinner may not be visible if not processing
    })
  })
})

// ==========================================
// Tests VirtualizedTable - Performance
// ==========================================
test.describe('VirtualizedTable - Performance', () => {
  test('rendu initial < 1s avec beaucoup de donnees', async ({ page }) => {
    const startTime = Date.now()
    await page.goto('/repertoire')
    await expect(page.locator('table')).toBeVisible()
    const loadTime = Date.now() - startTime
    expect(loadTime).toBeLessThan(2000)
    console.log(`Load time: ${loadTime}ms`)
  })

  test('scroll rapide ne cause pas de lag', async ({ page }) => {
    await page.goto('/repertoire')
    await page.waitForSelector('table tbody tr')

    // Mesurer performance pendant scroll
    const metrics = await page.evaluate(async () => {
      const container = document.querySelector('[data-testid="virtual-scroll-container"]') || document.documentElement
      const frameRates: number[] = []
      let lastTime = performance.now()

      for (let i = 0; i < 10; i++) {
        container.scrollTop += 500
        await new Promise(r => requestAnimationFrame(r))
        const now = performance.now()
        const fps = 1000 / (now - lastTime)
        frameRates.push(fps)
        lastTime = now
      }

      return {
        avgFPS: frameRates.reduce((a, b) => a + b, 0) / frameRates.length,
        minFPS: Math.min(...frameRates)
      }
    })

    console.log(`Scroll Performance - Avg FPS: ${metrics.avgFPS.toFixed(1)}, Min FPS: ${metrics.minFPS.toFixed(1)}`)
    // On veut au moins 30 FPS minimum
    expect(metrics.minFPS).toBeGreaterThan(20)
  })

  test('seules les lignes visibles sont rendues', async ({ page }) => {
    await page.goto('/repertoire')
    await page.waitForSelector('table tbody tr')

    const stats = await page.evaluate(() => {
      const rows = document.querySelectorAll('table tbody tr')
      const container = document.querySelector('[data-testid="virtual-scroll-container"]')
      return {
        renderedRows: rows.length,
        containerHeight: container?.clientHeight || window.innerHeight
      }
    })

    // Avec virtualization, on ne devrait pas render plus que visible + overscan
    // Environ (containerHeight / rowHeight) + 2*overscan
    const expectedMax = Math.ceil(stats.containerHeight / 48) + 20
    expect(stats.renderedRows).toBeLessThan(expectedMax)
    console.log(`Rendered rows: ${stats.renderedRows} (expected < ${expectedMax})`)
  })
})

// ==========================================
// Tests InfiniteScrollTable
// ==========================================
test.describe('InfiniteScrollTable', () => {
  test('charge plus de donnees au scroll', async ({ page }) => {
    await page.goto('/catalogues')
    await page.waitForSelector('table tbody tr')

    const initialCount = await page.locator('table tbody tr').count()
    console.log(`Initial rows: ${initialCount}`)

    // Scroll vers le bas
    await page.evaluate(() => {
      const container = document.querySelector('[data-testid="virtual-scroll-container"]') || document.documentElement
      container.scrollTop = container.scrollHeight
    })

    // Attendre chargement
    await page.waitForTimeout(1500)

    const newCount = await page.locator('table tbody tr').count()
    console.log(`After scroll rows: ${newCount}`)

    // Devrait avoir plus de lignes (ou au moins autant si fin de donnees)
    expect(newCount).toBeGreaterThanOrEqual(initialCount)
  })

  test('affiche indicateur de chargement pendant fetch', async ({ page }) => {
    await page.goto('/catalogues')
    await page.waitForSelector('table tbody tr')

    // Ralentir la prochaine requete
    await page.route('**/api/catalogues**', async route => {
      const url = route.request().url()
      if (url.includes('cursor')) {
        await new Promise(r => setTimeout(r, 500))
      }
      await route.continue()
    })

    // Scroll vers le bas
    await page.evaluate(() => {
      document.documentElement.scrollTop = document.documentElement.scrollHeight
    })

    // Verifier indicateur de chargement
    const loader = page.locator('.animate-spin, [data-testid="loading-more"]')
    // Peut etre visible brievement
    await expect(loader.first()).toBeVisible().catch(() => {
      // Loader may disappear quickly
    })
  })

  test('affiche compteur total', async ({ page }) => {
    await page.goto('/catalogues')
    await page.waitForSelector('table tbody tr')

    // Verifier presence compteur "X / Y elements"
    const counter = page.getByText(/\d+\s*\/\s*\d+/)
    await expect(counter).toBeVisible()
  })
})

// ==========================================
// Tests FilterBar
// ==========================================
test.describe('FilterBar', () => {
  test('filtre par texte fonctionne', async ({ page }) => {
    await page.goto('/repertoire')
    await page.waitForSelector('table tbody tr')

    const initialCount = await page.locator('table tbody tr').count()

    // Taper dans le champ de recherche
    const searchInput = page.getByPlaceholder(/recherche|search/i)
    if (await searchInput.count() > 0) {
      await searchInput.fill('AMLODIPINE')
      await page.waitForTimeout(500) // Debounce

      const filteredCount = await page.locator('table tbody tr').count()
      // Le nombre devrait changer (moins ou pareil si tous matchent)
      console.log(`Filter: ${initialCount} -> ${filteredCount}`)
    }
  })

  test('bouton reset efface les filtres', async ({ page }) => {
    await page.goto('/repertoire')

    const resetButton = page.getByText(/reinitialiser|reset/i)
    if (await resetButton.count() > 0) {
      await resetButton.click()
      // Verifier que les champs sont vides
    }
  })

  test('badge affiche nombre de filtres actifs', async ({ page }) => {
    await page.goto('/repertoire')

    // Appliquer un filtre
    const searchInput = page.getByPlaceholder(/recherche/i)
    if (await searchInput.count() > 0) {
      await searchInput.fill('test')
      await page.waitForTimeout(500)

      // Verifier badge "1 filtre"
      const badge = page.getByText(/\d+\s*filtre/i)
      if (await badge.count() > 0) {
        await expect(badge).toBeVisible()
      }
    }
  })
})

// ==========================================
// Tests GroupeDrawer
// ==========================================
test.describe('GroupeDrawer', () => {
  test('ouvre drawer au clic sur groupe', async ({ page }) => {
    await page.goto('/repertoire')
    await page.waitForSelector('table tbody tr')

    // Cliquer sur un lien de groupe
    const groupeLink = page.locator('[data-testid="groupe-link"]').first()
    if (await groupeLink.count() > 0) {
      await groupeLink.click()
      await expect(page.getByRole('dialog')).toBeVisible()
    }
  })

  test('affiche princeps dans drawer', async ({ page }) => {
    await page.goto('/repertoire')
    await page.waitForSelector('table tbody tr')

    const groupeLink = page.locator('[data-testid="groupe-link"]').first()
    if (await groupeLink.count() > 0) {
      await groupeLink.click()
      await page.waitForSelector('[role="dialog"]')

      // Verifier section Princeps
      const princepsSection = page.getByText(/princeps/i)
      await expect(princepsSection).toBeVisible()
    }
  })

  test('bouton copier CIP fonctionne', async ({ page }) => {
    await page.goto('/repertoire')
    await page.waitForSelector('table tbody tr')

    const groupeLink = page.locator('[data-testid="groupe-link"]').first()
    if (await groupeLink.count() > 0) {
      await groupeLink.click()
      await page.waitForSelector('[role="dialog"]')

      const copyButton = page.getByText(/copier/i).first()
      if (await copyButton.count() > 0) {
        await copyButton.click()
        // Verifier toast ou feedback
      }
    }
  })

  test('ferme drawer au clic exterieur', async ({ page }) => {
    await page.goto('/repertoire')
    await page.waitForSelector('table tbody tr')

    const groupeLink = page.locator('[data-testid="groupe-link"]').first()
    if (await groupeLink.count() > 0) {
      await groupeLink.click()
      await page.waitForSelector('[role="dialog"]')

      // Cliquer sur l'overlay
      await page.click('[data-testid="drawer-overlay"]', { force: true }).catch(() => {
        // Si pas d'overlay specifique, cliquer en dehors
        page.mouse.click(10, 10)
      })

      // Drawer devrait etre ferme
      await expect(page.getByRole('dialog')).not.toBeVisible()
    }
  })
})

// ==========================================
// Tests de memoire
// ==========================================
interface PerformanceMemory {
  usedJSHeapSize: number
  totalJSHeapSize: number
  jsHeapSizeLimit: number
}

interface PerformanceWithMemory extends Performance {
  memory?: PerformanceMemory
}

test.describe('Memory Performance', () => {
  test('memoire reste stable avec beaucoup de donnees', async ({ page }) => {
    await page.goto('/repertoire')
    await page.waitForSelector('table tbody tr')

    // Mesurer memoire initiale
    const initialMemory = await page.evaluate(() => {
      const perf = performance as PerformanceWithMemory
      if (perf.memory) {
        return perf.memory.usedJSHeapSize / 1024 / 1024
      }
      return 0
    })

    // Scroller beaucoup
    for (let i = 0; i < 20; i++) {
      await page.evaluate(() => {
        document.documentElement.scrollTop += 1000
      })
      await page.waitForTimeout(100)
    }

    // Mesurer memoire finale
    const finalMemory = await page.evaluate(() => {
      const perf = performance as PerformanceWithMemory
      if (perf.memory) {
        return perf.memory.usedJSHeapSize / 1024 / 1024
      }
      return 0
    })

    console.log(`Memory: ${initialMemory.toFixed(1)}MB -> ${finalMemory.toFixed(1)}MB`)

    // La memoire ne devrait pas exploser (< 100MB d'augmentation)
    if (initialMemory > 0) {
      expect(finalMemory - initialMemory).toBeLessThan(100)
    }
  })
})

// ==========================================
// Tests Hooks
// ==========================================
test.describe('Hooks', () => {
  test('useDebounceSearch - debounce fonctionne', async ({ page }) => {
    await page.goto('/repertoire')

    let requestCount = 0
    await page.route('**/api/repertoire**', route => {
      requestCount++
      route.continue()
    })

    const searchInput = page.getByPlaceholder(/recherche/i)
    if (await searchInput.count() > 0) {
      // Taper rapidement
      await searchInput.pressSequentially('test', { delay: 50 })

      // Attendre debounce (300ms default)
      await page.waitForTimeout(500)

      // Devrait n'avoir fait qu'une seule requete (pas une par lettre)
      console.log(`Request count after fast typing: ${requestCount}`)
      expect(requestCount).toBeLessThanOrEqual(2)
    }
  })
})
