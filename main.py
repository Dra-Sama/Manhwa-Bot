
import asyncio
import shutil
from collections.abc import Awaitable, Callable

try:
    import uvloop

    uvloop.install()
except ImportError:
    pass

try:
    import resource

    resource.setrlimit(resource.RLIMIT_NOFILE, (65535, 65535))
except (ImportError, ValueError, OSError):
    pass

from pyrogram import filters

from bot import Bot, Vars, logger
from TG.auto import get_updates_users, update_worker
from TG.migration_alert import schedule_migration_alerts
from Tools.db import database
from Tools.ihandler import ihandler
from Tools.redis_queue import close_redis_queue, init_redis_queue

# Seconds between runs. Adjust to whatever cadence each job really needs.
UPDATE_WORKER_INTERVAL = 60 * 60
UPDATE_USERS_INTERVAL = 60 * 60
TELEMETRY_INTERVAL = 300

shutil.rmtree("Process", ignore_errors=True)
try:
    _loop = asyncio.get_event_loop()
except (RuntimeError, DeprecationWarning):
    _loop = asyncio.new_event_loop()
    asyncio.set_event_loop(_loop)

_job_tasks: list[asyncio.Task] = []


@Bot.on_message(filters.private)
async def private_chat(client, message) -> bool:
    listener = client.listerner.get(getattr(message.from_user, "id", None))

    if not listener:
        message.continue_propagation()

    future = listener["future"]

    if future.done():
        return False

    custom_filter = listener.get("filters")

    if custom_filter and not await custom_filter(client, message):
        return False

    # The future may have timed out while the filter was awaiting
    if future.done():
        return False

    future.set_result(message)
    return True


async def telemetry_job() -> None:
    try:
        import psutil

        proc = psutil.Process()
        mem = psutil.virtual_memory()

        # cpu_percent(interval=1) sleeps for 1s, so keep it off the event loop
        cpu = await asyncio.to_thread(psutil.cpu_percent, 1)
        open_fds = proc.num_fds() if hasattr(proc, "num_fds") else 0
        tasks = len(asyncio.all_tasks())

        logger.info(
            f"Telemetry: CPU={cpu}%, RAM={mem.percent}% "
            f"({mem.used / 1024 / 1024:.2f}MB), Tasks={tasks}, FDs={open_fds}"
        )
        await ihandler.purge_expired()
    except Exception as e:
        logger.error(f"Telemetry error: {e}")


async def _run_periodic(
    func: Callable[[], Awaitable],
    name: str,
    seconds: float,
) -> None:
    """Run `func` every `seconds`, never overlapping, skipping missed ticks."""
    loop = asyncio.get_running_loop()
    next_run = loop.time() + seconds  # first run after one interval

    while True:
        await asyncio.sleep(max(0.0, next_run - loop.time()))
        try:
            await func()
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"[Job:{name}] failed: {e}")

        next_run += seconds
        now = loop.time()
        if next_run <= now:  # job overran: coalesce missed runs
            next_run = now + seconds


def setup_scheduler_jobs() -> None:
    jobs = (
        (update_worker, "update_worker", UPDATE_WORKER_INTERVAL),
        (get_updates_users, "get_updates_users", UPDATE_USERS_INTERVAL),
        (telemetry_job, "telemetry_task", TELEMETRY_INTERVAL),
    )
    for func, name, seconds in jobs:
        _job_tasks.append(
            asyncio.create_task(_run_periodic(func, name, seconds), name=name)
        )


async def _stop_jobs() -> None:
    for task in _job_tasks:
        task.cancel()
    await asyncio.gather(*_job_tasks, return_exceptions=True)
    _job_tasks.clear()


async def worker_tasks() -> None:
    await init_redis_queue()
    await database.auto_update_links()
    schedule_migration_alerts()

    from Tools.user_clients import user_client_manager

    if getattr(Vars, "USE_SHARED_WORKERS", False):
        import Tools.cworker

        Tools.cworker._shared_pool = Tools.cworker.SharedWorkerPool(num_workers=15)
        Tools.cworker._shared_pool.start()

    setup_scheduler_jobs()

    logger.info(
        "[Startup] Periodic jobs registered "
        "(update_worker, get_updates_users, telemetry_task). "
        "Idle checker running. Per-user download workers spawn on demand."
    )

    try:
        await user_client_manager.start_idle_checker()
    finally:
        await _stop_jobs()
        await close_redis_queue()

        try:
            await user_client_manager.stop_all()
        except Exception as e:
            logger.error(f"Error stopping user clients: {e}")


if __name__ == "__main__":
    _loop.create_task(worker_tasks())
    Bot.run()
