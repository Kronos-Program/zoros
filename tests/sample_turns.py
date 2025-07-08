"""Sample turn handlers used in tests."""

def add_numbers(ctx: dict) -> int:
    return ctx["a"] + ctx["b"]
