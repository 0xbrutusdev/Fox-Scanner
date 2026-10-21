"""Пути проекта в одном месте: бэкенд не ищет файлы относительно своих модулей.

  REPO_ROOT     корень репозитория (.env, data/)
  BACKEND_DIR   backend/ (пакет foxscanner, scripts/, tests/)
  FRONTEND_DIR  frontend/ (index.html, replay.html, static/) — то, что отдаёт server.py
  DATA_DIR      data/ — SQLite по умолчанию (DRAW_DB_PATH и другие пути из env важнее)
  ENV_FILE      .env в корне репозитория
"""
import os

PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(PACKAGE_DIR)
REPO_ROOT = os.path.dirname(BACKEND_DIR)
FRONTEND_DIR = os.path.join(REPO_ROOT, "frontend")
DATA_DIR = os.path.join(REPO_ROOT, "data")
ENV_FILE = os.path.join(REPO_ROOT, ".env")
