from ast import literal_eval
import re
import math
import operator as op

name = "calculator"
description = "Performs basic math calculations"
pattern = r"(?:calculate|compute|what is|solve)\s+(?P<expression>.+)"

# Define safe operations
operators = {
    '+': op.add,
    '-': op.sub,
    '*': op.mul,
    '/': op.truediv,
    '**': op.pow,
    '%': op.mod,
    '//': op.floordiv
}

# Define safe functions
safe_functions = {
    'abs': abs,
    'round': round,
    'min': min,
    'max': max,
    'sum': sum,
    'sin': math.sin,
    'cos': math.cos,
    'tan': math.tan,
    'sqrt': math.sqrt,
    'log': math.log,
    'log10': math.log10,
    'exp': math.exp,
    'pi': math.pi,
    'e': math.e
}

def safe_eval(expr):
    """Safely evaluate a mathematical expression"""
    # Replace function names with their values from safe_functions
    for func_name, func_value in safe_functions.items():
        if callable(func_value):
            # For callable functions, don't replace yet
            continue
        # For constants like pi and e, replace with their values
        expr = expr.replace(func_name, str(func_value))

    # Handle functions like sin, cos, etc.
    for func_name, func in safe_functions.items():
        if not callable(func):
            continue
        # Find all instances of function calls like sin(...)
        pattern = r'\b' + func_name + r'\s*\(([^)]+)\)'
        matches = re.finditer(pattern, expr)
        for match in reversed(list(matches)):
            # Evaluate the inner expression first
            inner_expr = match.group(1)
            try:
                inner_result = safe_eval(inner_expr)
                # Replace the function call with its result
                result = func(inner_result)
                expr = expr[:match.start()] + str(result) + expr[match.end():]
            except Exception:
                # If evaluation fails, leave it as is
                continue

    # Use a safer approach for basic arithmetic
    try:
        # This will handle basic arithmetic operations
        return eval(expr, {"__builtins__": {}}, operators)
    except Exception as e:
        raise ValueError(f"Could not evaluate expression: {expr}. Error: {e}")

def action(user_input: str, expression: str) -> str:
    try:
        # Clean up the expression
        expression = expression.strip()
        # Remove common words and characters that might interfere
        expression = re.sub(r'equals|equal to|is', '', expression)
        expression = expression.strip()

        # Evaluate the expression
        result = safe_eval(expression)

        # Format the result
        if isinstance(result, float):
            # Check if it's close to an integer
            if result.is_integer():
                result = int(result)
            else:
                # Limit decimal places for readability
                result = round(result, 6)

        return f"The result of {expression} is {result}"
    except Exception as e:
        return f"Sorry, I couldn't calculate that. Error: {str(e)}"
