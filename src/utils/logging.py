"""Structured logging with Rich console output."""

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.table import Table
import time
from functools import wraps

console = Console()


def section(title: str):
    console.rule(f"[bold blue]{title}")


def success(msg: str):
    console.print(f"[green]{msg}")


def warn(msg: str):
    console.print(f"[yellow]{msg}")


def error(msg: str):
    console.print(f"[red]{msg}")


def info(msg: str):
    console.print(f"[cyan]{msg}")


def make_progress():
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    )


def timed(label: str):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            start = time.perf_counter()
            result = fn(*args, **kwargs)
            elapsed = time.perf_counter() - start
            info(f"{label}: {elapsed:.1f}s")
            return result
        @wraps(fn)
        async def async_wrapper(*args, **kwargs):
            start = time.perf_counter()
            result = await fn(*args, **kwargs)
            elapsed = time.perf_counter() - start
            info(f"{label}: {elapsed:.1f}s")
            return result
        import asyncio
        if asyncio.iscoroutinefunction(fn):
            return async_wrapper
        return wrapper
    return decorator
