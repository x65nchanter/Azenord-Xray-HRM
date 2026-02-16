import qrcode
import typer
from rich.console import Console
from sqlmodel import Session, select

from app.core.config import settings
from app.core.database import engine
from app.core.models import User

app = typer.Typer(help="Управление подписками")
console = Console()


@app.command("link")
def get_link(nickname: str):
    """🎫 Сгенерировать и вывести прямую ссылку на подписку"""
    with Session(engine) as session:
        user = session.exec(select(User).where(User.nickname == nickname)).first()

        if not user:
            console.print(f"[red]❌ Ошибка: Пользователь '{nickname}' не найден в базе.[/red]")
            raise typer.Exit(code=1)

        if not user.is_active:
            console.print(
                f"[yellow]⚠ Внимание: Пользователь {nickname} заблокирован. Ссылка может не работать.[/yellow]"
            )

        # Формируем ссылку на основе данных из .env
        sub_url = f"https://{settings.SERVER_ADDR}/v1/sub/{user.uuid}"

        console.print(f"\n[bold green]✅ Подписка для {nickname} готова:[/bold green]")
        console.print(f"[cyan underline]{sub_url}[/cyan underline]\n")
        console.print("[dim]Скопируйте эту ссылку в v2rayN, Nekoray или Shadowrocket.[/dim]")


@app.command("qr")
def get_qr(nickname: str):
    """📸 Сгенерировать QR-код подписки прямо в терминале"""
    if qrcode is None:
        console.print(
            "[red]Ошибка: библиотека 'qrcode' не установлена. Выполните pip install qrcode[/red]"
        )
        return

    with Session(engine) as session:
        user = session.exec(select(User).where(User.nickname == nickname)).first()
        if not user:
            console.print(f"[red]Пользователь '{nickname}' не найден.[/red]")
            return

        sub_url = f"https://{settings.SERVER_ADDR}/v1/sub/{user.uuid}"

        console.print(f"\n[bold]QR-код для {nickname}:[/bold]")

        qr = qrcode.QRCode()
        qr.add_data(sub_url)
        # print_ascii(invert=True) лучше всего читается в темных терминалах (VS Code, Windows Terminal)
        qr.print_ascii(invert=True)

        console.print(f"\n[dim]URL: {sub_url}[/dim]")
