import math


def calculator(operation: str, a: float, b: float) -> str:
    """Perform an arithmetic calculation on two numbers.

    ALWAYS use this tool for any math — do not attempt mental arithmetic.

    Args:
        operation: The operation to perform. Must be one of:
            "add"       — a + b
            "subtract"  — a - b
            "multiply"  — a * b
            "divide"    — a / b
            "power"     — a raised to the power of b
            "modulo"    — a mod b (remainder of a / b)
        a: The first number (left operand).
        b: The second number (right operand).

    Returns:
        A string containing the numeric result, or an error message
        if the operation is invalid or mathematically undefined.
    """
    operations = {
        "add": lambda x, y: x + y,
        "subtract": lambda x, y: x - y,
        "multiply": lambda x, y: x * y,
        "divide": lambda x, y: x / y,
        "power": lambda x, y: x ** y,
        "modulo": lambda x, y: x % y,
    }

    if operation not in operations:
        return (
            f"Error: Unknown operation '{operation}'. "
            f"Supported operations: {', '.join(operations)}"
        )

    try:
        result = operations[operation](a, b)
    except ZeroDivisionError:
        return "Error: Division by zero is undefined."
    except OverflowError:
        return "Error: Result is too large to represent."

    # Return clean integers when the result has no fractional part
    if isinstance(result, float) and result.is_integer() and math.isfinite(result):
        return str(int(result))

    return str(result)
