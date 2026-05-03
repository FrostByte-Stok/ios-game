# ❄️ FrostByte v2 + iOS-Game

Telegram-бот + сайт для команды. Версия 2: без префикса "worker", 60% по умолчанию.

## 🚀 Запуск бота

```bash
pip install -r requirements.txt
python main.py
```

## 🌐 Деплой сайта на GitHub Pages

1. Создай репозиторий `ios-game` на GitHub (имя **точно** `ios-game`)
2. Залей файлы из `website/` в корень репозитория
3. Settings → Pages → Source: Deploy from a branch → main / root
4. Сайт будет доступен по адресу: `https://frostbyte-team.github.io/ios-game/`
5. В `config.py` укажи свой `GITHUB_USERNAME`

## ⚠️ Важно

- Бот должен быть админом в чате и канале
- Для API сайта сервер должен быть доступен из интернета (Render, Railway, VPS)
- Если бот на ПК — используй ngrok для теста
- Старые данные в `frostbyte.db` сохранятся (добавится колонка `worker_username`)
