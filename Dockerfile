# Image Docker pour Claude Code Sandbox - Pharma Remises
# Build: docker build -t claude-pharma .
# Run: docker run -it --rm -v C:\pharma-remises:/workspace claude-pharma

FROM python:3.11-slim

# Variables d'environnement
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV NODE_VERSION=20

# Installation des dependances systeme
# - build-essential: compilation packages Python
# - libpq-dev: driver PostgreSQL
# - cairo, pango, gdk-pixbuf: pour WeasyPrint (PDF)
# - git: controle version
# - curl: telecharger Node
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    libcairo2 \
    libcairo2-dev \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf2.0-0 \
    libffi-dev \
    shared-mime-info \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Installation Node.js
RUN curl -fsSL https://deb.nodesource.com/setup_${NODE_VERSION}.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Installation Claude CLI
RUN npm install -g @anthropic-ai/claude-code

# Creer repertoire de travail
WORKDIR /workspace

# Copier et installer dependances Python
COPY backend/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Copier package.json pour installer deps Node (optionnel, peut etre fait via volume)
# Les node_modules seront dans le volume monte

# Exposer les ports (backend + frontend)
EXPOSE 8001 5173

# Commande par defaut
CMD ["bash"]
