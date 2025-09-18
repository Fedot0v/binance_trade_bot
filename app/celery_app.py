import os

from celery import Celery


celery_app = Celery(
    "binance_trade_bot",
    broker=os.environ.get("CELERY_BROKER_URL"),
    backend=os.environ.get("CELERY_BROKER_URL"),
    include=["tasks.trade_tasks", "tasks.backtest_tasks"]
)

celery_app.conf.beat_schedule = {
    'run-active-bots-every-30-seconds': {
        'task': 'tasks.trade_tasks.run_active_bots',
        'schedule': 60.0,
    },
    'watcher-update-deals-every-30-seconds': {
        'task': 'tasks.trade_tasks.watcher_update_deals',
        'schedule': 60.0,
    },
}


celery_app.conf.timezone = 'UTC'

print('BEAT_SCHEDULE:', celery_app.conf.beat_schedule)
