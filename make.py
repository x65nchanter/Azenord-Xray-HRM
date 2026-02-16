import compileall
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import (
    Annotated,
    Optional,
)

import typer
from jinja2 import Template
from rich.console import Console

from app.core.config import settings
from app.utils.proto_gen import force_remove_readonly, generate_xray_proto

app = typer.Typer(help="Azenord Mesh Build & Dev Tools")
console = Console()


@app.command()
def install():
    """🚀 Smart Install: Auto-find paths, Backup old configs, and Deploy"""
    console.print("[bold cyan]🚀 Azenord HRM Installation Master[/bold cyan]")

    # --- 1. Helper for Backups ---
    def safe_copy(src: Path, dest_dir: str, filename: str):
        dest_path = Path(dest_dir) / filename
        if dest_path.exists():
            timestamp = time.strftime("%Y%m%d-%H%M%S")
            backup_path = Path(dest_dir) / f"{filename}.{timestamp}.bak"
            console.print(
                f"[yellow]📦 Backing up existing {filename} to {backup_path.name}[/yellow]"
            )
            subprocess.run(["sudo", "cp", str(dest_path), str(backup_path)], check=True)

        subprocess.run(["sudo", "cp", str(src), str(dest_path)], check=True)

    # --- 2. Auto-discovery of Paths ---
    nginx_bin = shutil.which("nginx") or "/usr/sbin/nginx"
    xray_bin = shutil.which("xray") or "/usr/local/bin/xray"

    def find_xray_dir():
        # Try to find config path from running service
        res = subprocess.run(
            ["systemctl", "show", "xray", "--property=ExecStart"], capture_output=True, text=True
        )
        import re

        match = re.search(r"-c\s+([^\s]+)", res.stdout)
        if match:
            return str(Path(match.group(1)).parent)
        return "/usr/local/etc/xray"

    suggested_xray = find_xray_dir()
    suggested_nginx = (
        "/etc/nginx/sites-available"
        if Path("/etc/nginx/sites-available").exists()
        else "/etc/nginx/conf.d"
    )

    # --- 3. User Confirmation ---
    nginx_path = typer.prompt("Nginx config path", default=suggested_nginx)
    xray_path = typer.prompt("Xray config path", default=suggested_xray)
    systemd_path = typer.prompt("Systemd path", default="/etc/systemd/system")

    # --- 4. Pre-flight Validation ---
    local_xray_json = Path("output/config.json")
    local_api_conf = Path("output/hrm_api.conf")
    local_service = Path("output/azenord-hrm.service")

    if local_xray_json.exists():
        check = subprocess.run(
            [xray_bin, "-test", "-config", str(local_xray_json)], capture_output=True
        )
        if check.returncode != 0:
            console.print(f"[bold red]❌ Xray config invalid: {check.stderr.decode()}[/bold red]")
            sys.exit(1)
        console.print("[green]✔ Xray configuration pre-test passed.[/green]")

    # --- 5. Execution ---
    try:
        # Xray
        if local_xray_json.exists():
            subprocess.run(["sudo", "mkdir", "-p", xray_path], check=True)
            safe_copy(local_xray_json, xray_path, "config.json")

        # Nginx
        if local_api_conf.exists():
            subprocess.run(["sudo", "mkdir", "-p", nginx_path], check=True)
            safe_copy(local_api_conf, nginx_path, "hrm_api.conf")

            # Auto-symlink for Debian/Ubuntu
            if "sites-available" in nginx_path:
                enabled = nginx_path.replace("sites-available", "sites-enabled")
                subprocess.run(["sudo", "mkdir", "-p", enabled], check=True)
                subprocess.run(
                    ["sudo", "ln", "-sf", f"{nginx_path}/hrm_api.conf", f"{enabled}/hrm_api.conf"],
                    check=True,
                )

        # Systemd
        if local_service.exists():
            safe_copy(local_service, systemd_path, "azenord-hrm.service")
            subprocess.run(["sudo", "systemctl", "daemon-reload"], check=True)

        # Final Verification & Reload
        if subprocess.run(["sudo", nginx_bin, "-t"], capture_output=True).returncode == 0:
            subprocess.run(["sudo", "systemctl", "reload", "nginx"], check=True)
            console.print("[bold green]✅ Nginx reloaded successfully.[/bold green]")

        subprocess.run(["sudo", "systemctl", "restart", "azenord-hrm"], check=True)
        console.print(
            "\n[bold black on green] 🎉 INSTALLATION & BACKUP COMPLETE [/bold black on green]"
        )

    except Exception as e:
        console.print(f"[bold red]❌ Deployment failed: {e}[/bold red]")
        sys.exit(1)


@app.command()
def config():
    """⚙️ Генерация всей инфраструктуры (Xray, Nginx, Systemd) из шаблонов"""
    console.print("[bold cyan]⚙️ Начинаю генерацию конфигурационных файлов...[/bold cyan]")

    # Список кортежей: (путь_к_шаблону, путь_вывода)
    configs = [
        ("app/templates/xray_config.json.j2", "output/config.json"),
        ("app/templates/nginx_api_sub.j2", "output/hrm_api.conf"),
        ("app/templates/azenord_hrm.service.j2", "output/azenord-hrm.service"),
    ]

    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)

    success_count = 0
    for tmpl_path_str, out_path_str in configs:
        tmpl_path = Path(tmpl_path_str)
        out_path = Path(out_path_str)

        if not tmpl_path.exists():
            console.print(f"[yellow]⚠️ Шаблон не найден, пропускаю: {tmpl_path}[/yellow]")
            continue

        try:
            # Читаем и рендерим
            template = Template(tmpl_path.read_text(encoding="utf-8"))
            rendered = template.render(settings=settings)

            # Записываем результат
            out_path.write_text(rendered, encoding="utf-8")
            console.print(f"[bold green]✅ Сгенерирован: {out_path}[/bold green]")
            success_count += 1
        except Exception as e:
            console.print(f"[bold red]❌ Ошибка при генерации {out_path_str}: {e}[/bold red]")

    if success_count == len(configs):
        console.print("\n[bold white on green] ✨ ВСЕ КОНФИГИ ГОТОВЫ ✨ [/bold white on green]")
    else:
        console.print(
            f"\n[bold yellow]⚠️ Готово {success_count} из {len(configs)} файлов.[/bold yellow]"
        )


@app.command()
def init():
    """🐣 Первичная инициализация проекта (Папки, БД, Прото)"""
    console.print("[bold cyan]🐣 Начало инициализации Azenord HRM...[/bold cyan]")

    # 1. Создаем структуру папок
    Path("app/core/xray_api").mkdir(parents=True, exist_ok=True)

    # 2. Генерируем протоколы (фундамент)
    proto()
    config()

    # 3. Инициализируем БД (создаем таблицы)
    console.print("[bold yellow]🗄️ Создание таблиц базы данных...[/bold yellow]")
    from app.core.database import init_db

    init_db()

    console.print(
        "[bold green]✅ Проект готов к работе! Теперь можно запускать dev или test.[/bold green]"
    )


@app.command()
def clean():
    """🧹 Clean up caches, temp files, and proto sources"""
    console.print("[bold red]🧹 Cleaning project...[/bold red]")

    def force_delete(path):
        if path.exists():
            if path.is_dir():
                shutil.rmtree(path, onerror=force_remove_readonly)
            else:
                path.unlink()

    dirs_to_wipe = ["proto_src", "app/core/xray_api", ".pytest_cache", ".ruff_cache"]

    for d in dirs_to_wipe:
        force_delete(Path(d))

    # Clean __pycache__
    for p in Path(".").rglob("__pycache__"):
        shutil.rmtree(p, ignore_errors=True)

    console.print("[bold green]✨ Project is mint![/bold green]")


@app.command()
def proto():
    """🧬 Generate Xray API from Protos (Pure Python version)"""
    console.print("[bold blue]🧬 Generating Xray API from Protos...[/bold blue]")
    generate_xray_proto()


@app.command()
def lint():
    """🔍 Run Ruff (Linter + Formatter)"""
    console.print("[bold cyan]🔍 Running Ruff...[/bold cyan]")
    subprocess.run(["ruff", "check", "app", "--fix"], check=False)
    subprocess.run(["ruff", "format", "app"], check=False)


@app.command()
def types():
    """🧪 Type checking with Basedpyright"""
    console.print("[bold magenta]🧪 Checking types...[/bold magenta]")
    # Игнорируем xray_api в проверке типов, так как код генерируемый
    subprocess.run(["basedpyright", "app"], check=False)


@app.command()
def compile():
    """📦 Syntax check (Byte-code)"""
    console.print("[bold yellow]📦 Compiling project...[/bold yellow]")
    success = compileall.compile_dir("app", force=True, quiet=1)
    if not success:
        console.print("[bold red]✘ Compilation failed![/bold red]")
        sys.exit(1)
    console.print("[bold green]✔ Compiled![/bold green]")


@app.command()
def test(all_tests: Optional[bool] = typer.Option(None, "--all", help="Запустить все тесты")):
    """🧪 Тесты: Unit (по умолчанию), +Integration (с флагом --all)"""

    env_vars = os.environ.copy()
    env_vars["PYTHONPATH"] = os.getcwd()

    pytest_args = [sys.executable, "-m", "pytest", "tests", "-v"]

    # Если флаг не передан (None) или передан как False
    if all_tests is not True:
        pytest_args.extend(["-m", "not integration"])
        console.print("[yellow]⚠️ Режим DEV: Интеграционные тесты (gRPC) пропущены.[/yellow]")
    else:
        console.print("[blue]🔗 Режим PROD: Запуск полной проверки с gRPC...[/blue]")

    result = subprocess.run(pytest_args, env=env_vars, check=False)

    if result.returncode != 0 and result.returncode != 5:
        sys.exit(result.returncode)


@app.command()
def validate(
    all_tests: Annotated[
        Optional[bool], typer.Option("--all", help="Полная валидация с gRPC")
    ] = None,
):
    """🛡️ ПОЛНАЯ ПРОВЕРКА (Assemble -> Verify)"""
    console.print("[bold white on blue] 🛡️ STARTING VALIDATION PIPELINE [/bold white on blue]")

    clean()
    proto()  # Пересборка API
    config()  # Пересборка конфигурации
    compile()  # Проверка синтаксиса
    lint()  # Причесывание кода
    types()  # Проверка типов

    # Прокидываем значение флага дальше в функцию теста
    test(all_tests=all_tests)

    console.print("\n[bold black on green] ✅ VALIDATION SUCCESSFUL [/bold black on green]")


@app.command()
def dev():
    """🔥 Start FastAPI Dev Server"""
    subprocess.run(["uvicorn", "app.api.main:app", "--reload", "--port", "8000"])


if __name__ == "__main__":
    app()
