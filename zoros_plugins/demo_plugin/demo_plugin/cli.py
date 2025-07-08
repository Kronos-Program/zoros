import typer

app = typer.Typer()

@app.command()
def say_hello() -> None:
    print("hello from plugin")

if __name__ == "__main__":
    app()
