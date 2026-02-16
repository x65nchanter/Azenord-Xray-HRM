import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

from rich.console import Console

console = Console()


def force_remove_readonly(func, path, excinfo):
    """
    Error handler for shutil.rmtree.
    If the error is due to a read-only file (common in .git),
    it changes the permission and tries again.
    """
    os.chmod(path, stat.S_IWRITE)
    func(path)


def generate_xray_proto():
    base_url = "https://github.com"
    repo_path = "/XTLS/Xray-core.git"
    full_url = f"{base_url}{repo_path}"

    proto_src = Path("proto_src")

    if proto_src.exists():
        console.print("[bold yellow]⚠️ Found old proto_src, forcing removal...[/bold yellow]")
        # Use the error handler here!
        shutil.rmtree(proto_src, onerror=force_remove_readonly)

    api_target = Path("app/core/xray_api")

    # 1. Clean up and setup directories
    console.print("[bold cyan]🧹 Cleaning up workspaces...[/bold cyan]")
    if proto_src.exists():
        shutil.rmtree(proto_src)
    api_target.mkdir(parents=True, exist_ok=True)

    # 2. Clone using Sparse-Checkout
    console.print("[bold blue]📡 Cloning Xray-core Protos...[/bold blue]")
    try:
        subprocess.run(
            [
                "git",
                "clone",
                "--depth",
                "1",
                "--filter=blob:none",
                "--sparse",
                full_url,
                str(proto_src),
            ],
            check=True,
        )

        subprocess.run(
            [
                "git",
                "-C",
                str(proto_src),
                "sparse-checkout",
                "set",
                "app",
                "common",
                "proxy",
                "transport",
                "core",
            ],
            check=True,
        )
    except subprocess.CalledProcessError:
        console.print(
            "[bold red]❌ Git clone failed. Check your internet/git installation.[/bold red]"
        )
        return

    # 3. Find all .proto files
    proto_files = [str(p) for p in proto_src.rglob("*.proto")]

    # 4. Compile via grpc_tools
    venv_bin = Path(sys.executable).parent

    def find_plugin(name):
        # Try venv with extensions (.exe for Windows, none for Linux)
        for ext in ["", ".exe", ".EXE"]:
            path = venv_bin / f"{name}{ext}"
            if path.exists():
                return str(path)
        # Fallback to system PATH
        return shutil.which(name)

    mypy_plugin = find_plugin("protoc-gen-mypy")
    mypy_grpc_plugin = find_plugin("protoc-gen-mypy_grpc")

    if not mypy_plugin:
        # Debug: let's see what's actually in that folder
        console.print(f"[bold red]❌ Plugins not found in {venv_bin}[/bold red]")
        return

    os.environ["TEMPORARY_DISABLE_PROTOBUF_VERSION_CHECK"] = "true"

    console.print("[bold magenta]⚙️ Compiling Protobuf files...[/bold magenta]")
    protoc_args = [
        sys.executable,
        "-m",
        "grpc_tools.protoc",
        f"--proto_path={proto_src}",
        f"--python_out={api_target}",
        f"--grpc_python_out={api_target}",
        f"--plugin=protoc-gen-mypy={mypy_plugin}",
        f"--plugin=protoc-gen-mypy_grpc={mypy_grpc_plugin}",
        f"--mypy_out={api_target}",
        f"--mypy_grpc_out={api_target}",
        *proto_files,
    ]
    subprocess.run(protoc_args, check=True)

    # 5. The "Surgical" Import Fix (Absolute Imports)
    console.print("[bold yellow]🧪 Fixing Python imports...[/bold yellow]")
    all_files = list(api_target.rglob("*.py")) + list(api_target.rglob("*.pyi"))

    for py_file in all_files:
        content = py_file.read_text()
        # Fix: from app... -> from app.core.xray_api.app...
        # Fix: import app... -> import app.core.xray_api.app...
        fixed_content = (
            content.replace("import app", "import app.core.xray_api.app")
            .replace("import common", "import app.core.xray_api.common")
            .replace("import proxy", "import app.core.xray_api.proxy")
            .replace("import transport", "import app.core.xray_api.transport")
            .replace("import core", "import app.core.xray_api.core")
            .replace("from app", "from app.core.xray_api.app")
            .replace("from common", "from app.core.xray_api.common")
            .replace("from proxy", "from app.core.xray_api.proxy")
            .replace("from transport", "from app.core.xray_api.transport")
            .replace("from core", "from app.core.xray_api.core")
        )
        py_file.write_text(fixed_content)

    # 6. Create __init__.py files
    for root, dirs, _ in os.walk(api_target):
        for d in dirs:
            (Path(root) / d / "__init__.py").touch()
    api_target.joinpath("__init__.py").touch()

    console.print("[bold green]✅ ПОБЕДА! Xray API successfully generated in Python.[/bold green]")


if __name__ == "__main__":
    generate_xray_proto()
