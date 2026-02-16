from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.table import Table
from sqlmodel import Session, select

from app.cli.utils.xray_client import xray
from app.core.constants import InboundTag
from app.core.database import engine
from app.core.models import Route, RoutePolicy

app = typer.Typer(help="Управление маршрутизацией")
console = Console()


@app.command("add")
def add_route(
    pattern: str = typer.Option(None, "--pattern", help="Match pattern"),
    policy: RoutePolicy = typer.Option(RoutePolicy.proxy, "--policy", help="Action"),
    network: str = typer.Option(None, "--network", help="tcp or udp"),
    port: str = typer.Option(None, "--port", help="Port range"),
    process: str = typer.Option(None, "--process", help="Process name"),
    package: str = typer.Option(None, "--package", help="Package name"),
):
    """🌐 Add complex routing rules (Discord ports, GeoSite, App-based)"""
    with Session(engine) as session:
        route = Route(
            pattern=pattern,
            policy=policy,
            network=network,
            port=port,
            process_name=process,
            package_name=package,
        )
        session.add(route)
        session.commit()
        console.print(f"[green]✔ Rule added for {pattern or 'Port/App'} -> {policy.value}[/green]")


@app.command("remove")
def route_remove(route_id: int):
    """Удаление правила по ID"""
    with Session(engine) as session:
        route = session.get(Route, route_id)
        if route:
            session.delete(route)
            session.commit()
            console.print(f"[green]✔ Правило {route_id} удалено.[/green]")


@app.command("clear")
def route_clear():
    """Полная очистка таблицы маршрутов"""
    if typer.confirm("Вы уверены, что хотите УДАЛИТЬ ВСЕ маршруты?"):
        with Session(engine) as session:
            session.query(Route).delete()
            session.commit()
            console.print("[red]🗑 Таблица маршрутов очищена.[/red]")


@app.command()
def xray_raw_add(email: str, uuid_str: str, tag: InboundTag = InboundTag.VISION):
    """Прямое добавление. Typer сам подставит варианты из Enum!"""
    if xray.add_user(tag.value, email, uuid_str):
        print(f"✔ Добавлено в {tag.value}")


@app.command("list")
def list_routes():
    """🌐 Показать все правила маршрутизации с их ID"""
    with Session(engine) as session:
        routes = session.exec(select(Route)).all()

        if not routes:
            console.print("[yellow]Таблица маршрутов пуста.[/yellow]")
            return

        table = Table(title="Azenord Mesh Routing Table")
        table.add_column("ID", style="dim", width=4)
        table.add_column("Pattern/App", style="cyan")
        table.add_column("Policy", style="bold")
        table.add_column("Network", style="magenta")
        table.add_column("Port", style="yellow")
        table.add_column("Process/Package", style="blue")

        for r in routes:
            # Если паттерна нет (например, правило только для процесса), пишем "App Rule"
            display_pattern = r.pattern if r.pattern else "[dim]App/Port Rule[/dim]"

            # Раскрашиваем политику
            policy_color = "green" if r.policy == RoutePolicy.proxy else "yellow"
            policy_display = f"[{policy_color}]{r.policy.value}[/{policy_color}]"

            table.add_row(
                str(r.id),
                display_pattern,
                policy_display,
                r.network or "-",
                r.port or "-",
                r.process_name or r.package_name or "-",
            )

        console.print(table)
