"""FoxScanner — бэкенд: HTTP API, скан токенов и фоновые сервисы (только стандартная библиотека).

  server.py   HTTP-сервер: API, страницы и /static/ из frontend/
  scan/       скан токена: engine (шаги и события), detect (детекторы), early (early buyers), market (цены, чарт)
  chains/     адаптеры сетей и лаунчпадов (BNB/four.meme, Robinhood, Solana, Flap, Bankr), общий EVM-клиент
  alerts/     Telegram alerts: logic (снимки и изменения), store, notify (отправка), recheck (перепроверки)
  draw/       розыгрыш среди холдеров: logic, service, store
  rewards/    Token Burn & Holder Rewards: logic, service, store
  history/    recent (лента сканов), opmem (память операторов), replay (Rug Replay)
  bot/        Telegram-бот, отдельный сервис и клиент API сайта
  db, env, memguard, paths, trade — общие помощники

Запуск из backend/: python -m foxscanner (сайт), python -m foxscanner.bot (бот).
"""
