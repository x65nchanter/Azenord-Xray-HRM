import typer

from app.cli.commands import mesh, route, sub, user

app = typer.Typer(help="Azenord Mesh HRM CLI Control")

app.add_typer(user.app, name="user")
app.add_typer(route.app, name="route")
app.add_typer(mesh.app, name="mesh")
app.add_typer(sub.app, name="sub")

if __name__ == "__main__":
    app()
