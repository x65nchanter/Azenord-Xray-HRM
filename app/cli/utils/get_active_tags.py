import typer
from rich.console import Console

from app.core.config import settings
from app.core.constants import InboundTag

console = Console()


def get_active_tags() -> list[InboundTag]:
    """Превращает список строк из .env в список объектов Enum"""
    try:
        # Пытаемся скастить каждую строку из конфига в наш Enum
        return [InboundTag(tag) for tag in settings.inbound_tags_list]
    except ValueError:
        console.print("[bold red]❌ Ошибка в .env![/bold red]")
        console.print(
            "[yellow]Один из тегов в ACTIVE_INBOUND_TAGS не поддерживается системой.[/yellow]"
        )
        raise typer.Exit(code=1)
