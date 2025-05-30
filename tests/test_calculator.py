import pytest
from tools.calculator import action, safe_eval

def test_calculator_basic_operations():
    # Test addition
    assert "result of 2+2 is 4" in action("calculate 2+2", "2+2")

    # Test subtraction
    assert "result of 10-5 is 5" in action("calculate 10-5", "10-5")

    # Test multiplication
    assert "result of 3*4 is 12" in action("calculate 3*4", "3*4")

    # Test division
    assert "result of 10/2 is 5" in action("calculate 10/2", "10/2")

    # Test power
    assert "result of 2**3 is 8" in action("calculate 2**3", "2**3")

    # Test modulo
    assert "result of 10%3 is 1" in action("calculate 10%3", "10%3")

    # Test floor division
    assert "result of 10//3 is 3" in action("calculate 10//3", "10//3")

def test_calculator_complex_expressions():
    # Test order of operations
    assert "result of 2+3*4 is 14" in action("calculate 2+3*4", "2+3*4")

    # Test parentheses
    assert "result of (2+3)*4 is 20" in action("calculate (2+3)*4", "(2+3)*4")

    # Test nested parentheses
    assert "result of (2+(3*4)) is 14" in action("calculate (2+(3*4))", "(2+(3*4))")

def test_calculator_functions():
    # Test abs function
    assert "result of abs(-5) is 5" in action("calculate abs(-5)", "abs(-5)")

    # Test round function
    assert "result of round(3.7) is 4" in action("calculate round(3.7)", "round(3.7)")

    # Test min function
    assert "result of min(3, 7) is 3" in action("calculate min(3, 7)", "min(3, 7)")

    # Test max function
    assert "result of max(3, 7) is 7" in action("calculate max(3, 7)", "max(3, 7)")

    # Test sqrt function
    assert "result of sqrt(9) is 3" in action("calculate sqrt(9)", "sqrt(9)")

def test_calculator_constants():
    # Test pi constant (approximately)
    result = action("calculate pi", "pi")
    assert "result of pi is 3.14159" in result

    # Test e constant (approximately)
    result = action("calculate e", "e")
    assert "result of e is 2.71828" in result

def test_calculator_error_handling():
    # Test division by zero
    result = action("calculate 1/0", "1/0")
    assert "couldn't calculate" in result.lower()
    assert "error" in result.lower()

    # Test invalid expression
    result = action("calculate 1+", "1+")
    assert "couldn't calculate" in result.lower()
    assert "error" in result.lower()

def test_safe_eval_security():
    # Test that safe_eval doesn't allow arbitrary code execution
    with pytest.raises(Exception):
        safe_eval("__import__('os').system('echo hacked')")

    with pytest.raises(Exception):
        safe_eval("open('/etc/passwd').read()")
