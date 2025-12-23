"""
Logging centralisé avec métriques pour opérations critiques.
Adapté aux gros volumes (milliers de lignes).
"""
import logging
import time
from datetime import datetime
from typing import Optional, Dict, Any
from functools import wraps
import os

# Créer le dossier logs s'il n'existe pas
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

# Configuration du logger
def setup_logger(name: str) -> logging.Logger:
    """Configure un logger avec fichier et console."""
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    # Éviter les doublons de handlers
    if logger.handlers:
        return logger

    # Format avec timestamp et niveau
    formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Handler fichier (logs persistants)
    file_handler = logging.FileHandler(
        os.path.join(LOG_DIR, f"{name}.log"),
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    # Handler console (logs temps réel)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


class OperationMetrics:
    """
    Collecte les métriques d'une opération longue.
    Logue par batch pour éviter de flooder les logs.
    """

    def __init__(self, logger: logging.Logger, operation_name: str, total_items: int = 0, batch_size: int = 100):
        self.logger = logger
        self.operation_name = operation_name
        self.total_items = total_items
        self.batch_size = batch_size

        self.start_time = time.time()
        self.processed = 0
        self.success = 0
        self.errors = 0
        self.last_log_time = self.start_time
        self.custom_metrics: Dict[str, Any] = {}

    def start(self, **extra_info):
        """Log le début de l'opération."""
        msg = f"[START] {self.operation_name}"
        if self.total_items:
            msg += f" | {self.total_items} items à traiter"
        if extra_info:
            msg += f" | {extra_info}"
        self.logger.info(msg)

    def increment(self, success: bool = True, **metrics):
        """
        Incrémente le compteur. Logue tous les batch_size items.
        """
        self.processed += 1
        if success:
            self.success += 1
        else:
            self.errors += 1

        # Mettre à jour les métriques custom
        for key, value in metrics.items():
            if key not in self.custom_metrics:
                self.custom_metrics[key] = 0
            self.custom_metrics[key] += value if isinstance(value, (int, float)) else 1

        # Log tous les batch_size items
        if self.processed % self.batch_size == 0:
            self._log_progress()

    def _log_progress(self):
        """Log la progression."""
        elapsed = time.time() - self.start_time
        rate = self.processed / elapsed if elapsed > 0 else 0

        pct = (self.processed / self.total_items * 100) if self.total_items else 0
        eta = ((self.total_items - self.processed) / rate) if rate > 0 and self.total_items else 0

        msg = f"[PROGRESS] {self.operation_name} | {self.processed}"
        if self.total_items:
            msg += f"/{self.total_items} ({pct:.1f}%)"
        msg += f" | {rate:.1f}/s | ETA: {eta:.0f}s"

        if self.errors:
            msg += f" | errors: {self.errors}"

        self.logger.info(msg)

    def add_metric(self, name: str, value: Any):
        """Ajoute une métrique custom."""
        self.custom_metrics[name] = value

    def finish(self, **extra_info):
        """Log la fin de l'opération avec résumé complet."""
        elapsed = time.time() - self.start_time
        rate = self.processed / elapsed if elapsed > 0 else 0

        # Résumé principal
        summary = [
            f"[END] {self.operation_name}",
            f"durée: {elapsed:.2f}s",
            f"traités: {self.processed}",
            f"succès: {self.success}",
            f"erreurs: {self.errors}",
            f"vitesse: {rate:.1f}/s",
        ]

        # Métriques custom
        if self.custom_metrics:
            for key, value in self.custom_metrics.items():
                if isinstance(value, float):
                    summary.append(f"{key}: {value:.2f}")
                else:
                    summary.append(f"{key}: {value}")

        # Extra info
        if extra_info:
            for key, value in extra_info.items():
                summary.append(f"{key}: {value}")

        self.logger.info(" | ".join(summary))

        return {
            "duration_s": round(elapsed, 2),
            "processed": self.processed,
            "success": self.success,
            "errors": self.errors,
            "rate_per_s": round(rate, 1),
            **self.custom_metrics
        }


def log_operation(logger_name: str, operation_name: str):
    """
    Décorateur pour logger automatiquement une opération.
    """
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            logger = setup_logger(logger_name)
            start = time.time()
            logger.info(f"[START] {operation_name} | args: {kwargs.keys()}")
            try:
                result = await func(*args, **kwargs)
                elapsed = time.time() - start
                logger.info(f"[END] {operation_name} | durée: {elapsed:.2f}s | succès")
                return result
            except Exception as e:
                elapsed = time.time() - start
                logger.error(f"[ERROR] {operation_name} | durée: {elapsed:.2f}s | {str(e)}")
                raise

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            logger = setup_logger(logger_name)
            start = time.time()
            logger.info(f"[START] {operation_name} | args: {kwargs.keys()}")
            try:
                result = func(*args, **kwargs)
                elapsed = time.time() - start
                logger.info(f"[END] {operation_name} | durée: {elapsed:.2f}s | succès")
                return result
            except Exception as e:
                elapsed = time.time() - start
                logger.error(f"[ERROR] {operation_name} | durée: {elapsed:.2f}s | {str(e)}")
                raise

        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    return decorator


# Loggers pré-configurés pour chaque module critique
matching_logger = setup_logger("matching")
import_catalogue_logger = setup_logger("import_catalogue")
import_ventes_logger = setup_logger("import_ventes")
