# Image Docker pour Claude Code Sandbox - Pharma Remises
# Build: docker build -t claude-pharma .
# Run: docker run -it --rm -v C:\pharma-remises:/workspace claude-pharma

FROM python:3.11-slim

# Variables d'environnement
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV NODE_VERSION=20
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# Installation des dependances systeme
# - build-essential: compilation packages Python
# - libpq-dev: driver PostgreSQL
# - cairo, pango, gdk-pixbuf: pour WeasyPrint (PDF)
# - git: controle version
# - curl: telecharger Node
# - Playwright deps: navigateurs headless
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    libcairo2 \
    libcairo2-dev \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    libffi-dev \
    shared-mime-info \
    git \
    curl \
    # Playwright dependencies
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpangocairo-1.0-0 \
    libgtk-3-0 \
    libx11-xcb1 \
    libxcb-dri3-0 \
    libxshmfence1 \
    && rm -rf /var/lib/apt/lists/*

# Installation Node.js
RUN curl -fsSL https://deb.nodesource.com/setup_${NODE_VERSION}.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Installation Claude CLI
RUN npm install -g @anthropic-ai/claude-code

# Installation Playwright globalement avec navigateurs
RUN npm install -g playwright && playwright install chromium

# Creer utilisateur non-root pour Claude
RUN useradd -m -s /bin/bash claude && \
    mkdir -p /home/claude/.claude && \
    chown -R claude:claude /home/claude

# Creer repertoire de travail
WORKDIR /workspace

# Copier et installer dependances Python
COPY backend/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Installer pytest et outils de test Python
RUN pip install --no-cache-dir \
    pytest \
    pytest-asyncio \
    pytest-cov \
    pytest-benchmark \
    httpx \
    respx

# Donner acces au workspace pour l'utilisateur claude
RUN chown -R claude:claude /workspace

# Exposer les ports (backend + frontend)
EXPOSE 8001 5173

# Passer a l'utilisateur non-root
USER claude

# Commande par defaut
CMD ["bash"]
