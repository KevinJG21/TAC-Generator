"""Operator semantics shared by the constant folder, the AST interpreter and the TAC VM."""
import math

ARITH = {"+", "-", "*", "/", "%"}
REL = {"<", "<=", ">", ">=", "==", "!="}
LOGIC = {"&&", "||"}
NEG_REL = {"<": ">=", "<=": ">", ">": "<=", ">=": "<", "==": "!=", "!=": "=="}


def apply_binary(op, a, b):
    if op == "+":
        return a + b
    if op == "-":
        return a - b
    if op == "*":
        return a * b
    if op == "/":
        if b == 0:
            raise ZeroDivisionError("division by zero")
        if isinstance(a, int) and isinstance(b, int):      # C-style truncation
            q = abs(a) // abs(b)
            return q if (a < 0) == (b < 0) else -q
        return a / b
    if op == "%":
        if b == 0:
            raise ZeroDivisionError("modulo by zero")
        if isinstance(a, int) and isinstance(b, int):      # sign follows dividend
            r = abs(a) % abs(b)
            return -r if a < 0 else r
        return math.fmod(a, b)
    if op == "<":
        return int(a < b)
    if op == "<=":
        return int(a <= b)
    if op == ">":
        return int(a > b)
    if op == ">=":
        return int(a >= b)
    if op == "==":
        return int(a == b)
    if op == "!=":
        return int(a != b)
    if op == "&&":
        return int(bool(a) and bool(b))
    if op == "||":
        return int(bool(a) or bool(b))
    raise ValueError(f"unknown operator {op}")


def apply_unary(op, a):
    if op in ("-", "neg"):
        return -a
    if op == "!":
        return int(not a)
    raise ValueError(f"unknown unary operator {op}")
