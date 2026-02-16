import os

import typer
from rich.console import Console
from rich.table import Table
from sqlmodel import Session, select

from app.cli.utils.xray_client import xray
from app.core.config import settings
from app.core.database import engine
from app.core.models import User

app = typer.Typer(help="Управление Mesh-сетью")
console = Console()


@app.command("status")  # Добавим явное имя для ясности
def mesh_status():
    """Проверка здоровья: gRPC адрес из .env и SQLite"""
    console.print(f"🔍 Цель: [bold]{settings.XRAY_GRPC_ADDR}[/bold]")
    if xray.check_connection():
        console.print("[green]✔ Xray gRPC: ONLINE[/green]")
        with Session(engine) as session:
            count = len(session.exec(select(User)).all())
            console.print(f"[green]✔ Database: OK ({count} users)[/green]")
    else:
        console.print("[red]✘ Xray gRPC: OFFLINE[/red]")


@app.command("stats")  # Оставляем одну главную команду stats
def mesh_stats():
    """Общая статистика потребления сети всей Mesh-сетью"""
    all_stats = xray.get_traffic_stats()
    if not all_stats:
        console.print("[yellow]Статистика недоступна (Xray offline?)[/yellow]")
        return

    total_down = sum(v for k, v in all_stats.items() if "downlink" in k)
    total_up = sum(v for k, v in all_stats.items() if "uplink" in k)

    console.print("📊 [bold]Mesh Total Traffic:[/bold]")
    console.print(f"⬇ Download: [cyan]{total_down / 1024**3:.2f}[/cyan] GB")
    console.print(f"⬆ Upload:   [magenta]{total_up / 1024**3:.2f}[/magenta] GB")


@app.command("user-stats")  # Переименовываем детальную таблицу
def user_stats():
    """📊 Детальная статистика трафика по каждому входу/юзеру"""
    data = xray.get_traffic_stats()
    if not data:
        console.print("[yellow]Нет данных.[/yellow]")
        return

    table = Table(title="Detailed Traffic Stats")
    table.add_column("Source", style="cyan")
    table.add_column("Direction", style="magenta")
    table.add_column("Value", style="green")

    for key, value in data.items():
        parts = key.split(">>>")
        name = parts[1] if len(parts) > 1 else key
        direction = parts[-1]
        table.add_row(name, direction, f"{value / 1024**2:.2f} MB")

    console.print(table)


@app.command("scan")
def mesh_scan():
    """Пинг всех активных IP в Mesh (10.0.8.0/24)"""
    console.print("[bold cyan]📡 Сканирование Mesh-сети...[/bold cyan]")
    with Session(engine) as session:
        users = session.exec(select(User).where(User.is_active)).all()
        for u in users:
            response = os.system(f"ping -n 1 -w 1000 {u.internal_ip} > nul")
            status = "[green]ONLINE[/green]" if response == 0 else "[red]OFFLINE[/red]"
            console.print(f"Resident: {u.nickname:15} | IP: {u.internal_ip:12} | {status}")
