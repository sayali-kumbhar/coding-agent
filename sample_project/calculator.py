from app import divide


def calculate(a: float, b: float) -> str:
    return f"{a} / {b} = {divide(a, b)}"