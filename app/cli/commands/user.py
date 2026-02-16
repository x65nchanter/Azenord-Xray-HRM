import uuid
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
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
def add_user(
    nickname: str,
    email: str,
    no_sync: Optional[bool] = typer.Option(
        None, "--no-sync", help="Skip Xray gRPC synchronization"
    ),
):
    """Safe registration with full rollback on failure"""
    if not xray.check_connection() and no_sync is not True:
        console.print("[bold red]❌ Xray gRPC is NOT reachable![/bold red]")
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
            if no_sync is True:
                console.print("[blue]ℹ Skipping Xray sync as requested.[/blue]")
            else:
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

            if no_sync is True:
                console.print("[blue]ℹ Skipping Xray sync as requested.[/blue]")
            else:
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

        down_mb = f"{down / 1024**2:.2f} MB"
        up_mb = f"{up / 1024**2:.2f} MB"

        table = Table(show_header=False, box=None, padding=(0, 2))

        # General Info
        table.add_row("[bold cyan]Email[/]", user.email)
        table.add_row("[bold cyan]Internal IP[/]", f"[magenta]{user.internal_ip}[/]")
        table.add_row("[bold cyan]DNS Name[/]", f"[yellow]{user.dns_name}[/]")
        table.add_row("[bold cyan]UUID[/]", user.uuid)
        table.add_row(
            "[bold cyan]Status[/]", "[green]● Active[/]" if user.is_active else "[red]○ Banned[/]"
        )

        table.add_section()  # Add a small separator

        # Traffic Info
        table.add_row("[bold blue]Traffic Down[/]", down_mb)
        table.add_row("[bold blue]Traffic Up[/]", up_mb)

        table.add_section()

        # Access Info
        table.add_row(
            "[bold yellow]Papers Token[/]",
            f"[gray]{user.papers_token[:8]}...{user.papers_token[-8:]}[/]",
        )
        table.add_row(
            "[bold yellow]Papers Link[/]", f"[link={user.papers_link}]{user.papers_link}[/]"
        )

        # Wrap everything in a nice Panel
        console.print(
            Panel(
                table,
                title=f"[bold white]Resident Card: {user.nickname}[/]",
                expand=False,
                border_style="bright_blue",
            )
        )


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


@app.command("sync")
def sync_all():
    """Force push all users from DB to Xray"""
    if not xray.check_connection():
        console.print("[bold red]❌ Cannot sync: Xray gRPC unreachable.[/bold red]")
        return

    active_tags = [t.value for t in get_active_tags()]

    with Session(engine) as session:
        users = session.exec(select(User)).all()
        if not users:
            console.print("[yellow]No users in database to sync.[/yellow]")
            return

        with console.status("[bold green]Syncing users to Xray..."):
            for user in users:
                for tag in active_tags:
                    success = xray.add_user(inbound_tag=tag, email=user.email, user_uuid=user.uuid)
                    if success:
                        console.print(f"[green]✔[/green] {user.nickname} -> {tag}")
                    else:
                        console.print(
                            f"[red]✘[/red] {user.nickname} -> {tag} (likely already exists)"
                        )

    console.print("[bold green]✅ Full sync complete.[/bold green]")


@app.command("link")
def get_user_link(nickname: str):
    """🔗 Вывести только прямую ссылку papers_link"""
    with Session(engine) as session:
        user = session.exec(select(User).where(User.nickname == nickname)).first()

        if not user:
            console.print(f"[bold red]❌ Resident '{nickname}' not found.[/bold red]")
            return

        # Выводим чистую ссылку без оберток, чтобы удобно было копировать в терминале
        # Мы используем [link], чтобы терминал понял, что это URL
        console.print(f"[link={user.papers_link}]{user.papers_link}[/link]")
