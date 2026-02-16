import uuid
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from sqlmodel import Session, select

from app.cli.utils.get_active_tags import get_active_tags
from app.cli.utils.xray_client import xray
from app.core.database import engine
from app.core.models import User
from app.utils.ipam import get_next_free_ip

app = typer.Typer(help="Управление пользователями")
console = Console()


@app.command("add")
def add_user(nickname: str, email: str):
    """Safe registration with full rollback on failure"""
    if not xray.check_connection():
        return

    with Session(engine) as session:
        # 1. IMMEDIATE Check (Before touching Xray)
        existing = session.exec(select(User).where(User.nickname == nickname)).first()
        if existing:
            console.print(f"[yellow]⚠ User {nickname} already exists.[/yellow]")
            return

        new_uuid = str(uuid.uuid4())
        new_ip = get_next_free_ip(session)
        active_tags = get_active_tags()

        added_tags = []  # Track where we actually succeeded

        try:
            # 2. Xray Sync Phase
            for tag in active_tags:
                if xray.add_user(inbound_tag=tag.value, email=email, user_uuid=new_uuid):
                    added_tags.append(tag.value)
                else:
                    raise Exception(f"Failed to add to inbound: {tag.value}")

            # 3. Database Phase
            user = User(nickname=nickname, email=email, uuid=new_uuid, internal_ip=new_ip)
            session.add(user)
            session.commit()
            console.print(f"[green]✔ {nickname} синхронизирован во всех транспортах.[/green]")

        except Exception as e:
            # 4. ROLLBACK PHASE (The "Safety Net")
            console.print(f"[bold red]❌ Sync Error: {e}[/bold red]")
            console.print("[yellow]🔄 Rolling back Xray changes...[/yellow]")

            for tag in added_tags:
                xray.remove_user(inbound_tag=tag, email=email)

            console.print("[red]Cleanup complete. No changes were saved.[/red]")


@app.command("list")
def list_users():
    """Показать всех участников сети"""
    with Session(engine) as session:
        users = session.exec(select(User)).all()
        table = Table(title="Azenord Mesh Residents")
        table.add_column("Nick", style="magenta")
        table.add_column("Internal IP", style="cyan")
        table.add_column("UUID", style="yellow")
        table.add_column("Status", style="bold")

        for u in users:
            status = "[green]Active[/green]" if u.is_active else "[red]Banned[/red]"
            table.add_row(u.nickname, u.internal_ip, u.uuid, status)
        console.print(table)


@app.command("remove")
def remove_user(nickname: str):
    """🗑 Полное удаление пользователя из всех 3 транспортов и БД"""
    with Session(engine) as session:
        user = session.exec(select(User).where(User.nickname == nickname)).first()
        if not user:
            console.print("[red]Юзер не найден.[/red]")
            return

        tags = ["vless-vision", "vless-h2", "vless-h3"]
        for tag in tags:
            xray.remove_user(tag, user.email)

        session.delete(user)
        session.commit()
        console.print(f"[green]✔ Юзер {nickname} полностью удален.[/green]")


@app.command("toggle")
def toggle_user(nickname: str):
    """🚫 Временная блокировка доступа (удаление/добавление в gRPC)"""
    with Session(engine) as session:
        user = session.exec(select(User).where(User.nickname == nickname)).first()
        if not user:
            return

        tags = ["vless-vision", "vless-h2", "vless-h3"]
        if user.is_active:
            # БАН: удаляем из памяти Xray
            for tag in tags:
                xray.remove_user(tag, user.email)
            user.is_active = False
            label = "[red]заблокирован[/red]"
        else:
            # РАЗБАН: возвращаем в память Xray
            for tag in tags:
                xray.add_user(tag, user.email, user.uuid)
            user.is_active = True
            label = "[green]активирован[/green]"

        session.add(user)
        session.commit()
        console.print(f"👤 Юзер {nickname} {label}.")


@app.command("info")
def user_info(nickname: str):
    """Детальная инфо и статистика трафика"""
    with Session(engine) as session:
        user = session.exec(select(User).where(User.nickname == nickname)).first()
        if not user:
            return console.print("[red]Юзер не найден[/red]")

        # Запрашиваем статы через gRPC
        all_stats = xray.get_traffic_stats()
        # Ищем ключ вида user>>>email>>>traffic>>>downlink
        down = all_stats.get(f"user>>>{user.email}>>>traffic>>>downlink", 0)
        up = all_stats.get(f"user>>>{user.email}>>>traffic>>>uplink", 0)

        table = Table(show_header=False, title=f"User Card: {nickname}")
        table.add_row("Email", user.email)
        table.add_row("Internal IP", user.internal_ip)
        table.add_row("UUID", user.uuid)
        table.add_row("Status", "[green]Active[/green]" if user.is_active else "[red]Banned[/red]")
        table.add_row("Traffic Down", f"{down / 1024**2:.2f} MB")
        table.add_row("Traffic Up", f"{up / 1024**2:.2f} MB")
        console.print(table)


@app.command("ban")
def user_ban(nickname: str):
    """Временная блокировка (toggle_user под капотом)"""
    # Вызываем нашу логику toggle с принудительным ban
    toggle_user_logic(nickname, force_state=False)


@app.command("unban")
def user_unban(nickname: str):
    """Восстановление доступа"""
    toggle_user_logic(nickname, force_state=True)


def toggle_user_logic(nickname: str, force_state: bool):
    with Session(engine) as session:
        user = session.exec(select(User).where(User.nickname == nickname)).first()
        if not user:
            console.print("[red]Юзер не найден[/red]")
            return

        tags = ["vless-vision", "vless-h2", "vless-h3"]
        if force_state is False:  # BAN
            for tag in tags:
                xray.remove_user(tag, user.email)
            user.is_active = False
            label = "[red]заблокирован[/red]"
        else:  # UNBAN
            for tag in tags:
                xray.add_user(tag, user.email, user.uuid)
            user.is_active = True
            label = "[green]активирован[/green]"

        session.add(user)
        session.commit()
        console.print(f"👤 Юзер {nickname} {label}.")
