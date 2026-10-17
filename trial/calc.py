__all__ = ["divide", "percent"]


def divide(a, b):
    if b == 0:
        raise ValueError("division by zero")
    return a / b


def percent(part, whole):
    return divide(part, whole) * 100
