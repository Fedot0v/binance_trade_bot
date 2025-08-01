from celery import Celery


celery_app = Celery(
    "binance_trade_bot",
    broker="redis://redis:6379/0",
    backend="redis://redis:6379/1",
    include=["tasks.trade_tasks"]
)

# РАСКОММЕНТИРУЙ и поправь расписание:
celery_app.conf.beat_schedule = {
    'run-active-bots-every-30-seconds': {
        'task': 'tasks.trade_tasks.run_active_bots',
        'schedule': 30.0,
    },
    'watcher-update-deals-every-30-seconds': {
        'task': 'tasks.trade_tasks.watcher_update_deals',
        'schedule': 30.0,
    },
}


celery_app.conf.timezone = 'UTC'

print('BEAT_SCHEDULE:', celery_app.conf.beat_schedule)
