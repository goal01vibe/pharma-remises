# Workflow Claude Sandbox - Pharma Remises

## Structure des branches

```
main                        <- Code stable uniquement (production)
  └── dev                   <- Branche d'integration
        ├── feature/backend   <- Travail backend
        └── feature/frontend  <- Travail frontend
```

---

## Utilisation quotidienne

### 1. Lancer Claude en sandbox

```powershell
cd C:\pharma-remises
.\claude-sandbox.bat
```

**Premier lancement** : l'image Docker se construit automatiquement (~10 min)
**Lancements suivants** : instantane

### 2. Forcer la reconstruction de l'image

Si tu modifies `requirements.txt` ou `Dockerfile` :

```powershell
.\claude-sandbox.bat --build
```

---

## Workflow Git pour les agents

### Travailler sur le backend

```bash
git checkout feature/backend
# ... travail ...
git add .
git commit -m "feat: description"
git checkout dev
git merge feature/backend
```

### Travailler sur le frontend

```bash
git checkout feature/frontend
# ... travail ...
git add .
git commit -m "feat: description"
git checkout dev
git merge feature/frontend
```

### Merger vers main (quand tout est stable)

```bash
git checkout main
git merge dev
git push
```

---

## Ralph Loop (boucle autonome)

### Lancer une tache autonome

```bash
# Dans le container Docker
claude --dangerously-skip-permissions

# Puis dans Claude
/ralph-loop "Implemente tout le backend selon ARCHITECTURE_FUTURE.md" --promise "Backend termine"
```

Claude va boucler jusqu'a ce qu'il declare avoir termine.

### Arreter une boucle Ralph

```bash
/cancel-ralph
```

---

## Commandes utiles

| Commande | Description |
|----------|-------------|
| `.\claude-sandbox.bat` | Lancer Claude en sandbox |
| `.\claude-sandbox.bat --build` | Reconstruire l'image + lancer |
| `docker ps` | Voir containers actifs |
| `docker stop claude-sandbox` | Arreter le container |
| `docker images` | Voir images disponibles |
| `docker rmi claude-pharma` | Supprimer l'image |

---

## Fichiers crees

| Fichier | Role |
|---------|------|
| `Dockerfile` | Image Docker avec Python, Node, deps |
| `.dockerignore` | Fichiers exclus du build |
| `claude-sandbox.bat` | Script de lancement Windows |

---

## Securite

Le sandbox Docker :
- ✅ Isole Claude du reste du PC
- ✅ Limite l'acces a `C:\pharma-remises` uniquement
- ✅ Les erreurs restent dans le container
- ✅ `--dangerously-skip-permissions` est securise dans ce contexte

---

## Prerequis

- Docker Desktop installe et lance
- Variable `ANTHROPIC_API_KEY` configuree (ou dans `.env`)
- Git installe

---

## Depannage

### "Docker n'est pas lance"
→ Demarrer Docker Desktop

### "Image non trouvee"
→ Le script la construit automatiquement

### Erreur de build
→ Verifier `requirements.txt` et connexion internet

### Container qui ne demarre pas
→ `docker logs claude-sandbox` pour voir les erreurs
