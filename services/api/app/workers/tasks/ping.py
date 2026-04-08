from celery import shared_task


@shared_task(name="esn.ping")
def ping() -> str:
    return "pong"
