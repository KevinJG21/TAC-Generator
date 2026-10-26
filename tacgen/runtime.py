"""Executors used to verify the generator: an AST interpreter and a TAC virtual machine."""
import re
from .ast_nodes import (Num, BoolLit, Var, Unary, Binary, Assign, Print,
                        ExprStmt, Block, If, While)
from .ops import apply_binary, apply_unary

_NUM = re.compile(r"^-?\d+(\.\d+)?$")
MAX_STEPS = 1_000_000


class RuntimeFault(Exception):
    pass


def run_ast(program, max_steps=MAX_STEPS):
    env, out, steps = {}, [], [0]

    def tick():
        steps[0] += 1
        if steps[0] > max_steps:
            raise RuntimeFault("step limit exceeded (possible infinite loop)")

    def ev(e):
        if isinstance(e, Num):
            return e.value
        if isinstance(e, BoolLit):
            return int(e.value)
        if isinstance(e, Var):
            return env[e.name]
        if isinstance(e, Unary):
            return apply_unary(e.op, ev(e.operand))
        if isinstance(e, Binary):
            if e.op == "&&":
                return int(bool(ev(e.left)) and bool(ev(e.right)))
            if e.op == "||":
                return int(bool(ev(e.left)) or bool(ev(e.right)))
            try:
                return apply_binary(e.op, ev(e.left), ev(e.right))
            except ZeroDivisionError as ex:
                raise RuntimeFault(str(ex))
        raise RuntimeFault(f"bad expression {e}")

    def ex(s):
        tick()
        if isinstance(s, Assign):
            env[s.name] = ev(s.value)
        elif isinstance(s, Print):
            out.append(str(ev(s.value)))
        elif isinstance(s, ExprStmt):
            ev(s.expr)
        elif isinstance(s, Block):
            for x in s.stmts:
                ex(x)
        elif isinstance(s, If):
            if ev(s.cond):
                ex(s.then)
            elif s.otherwise is not None:
                ex(s.otherwise)
        elif isinstance(s, While):
            while ev(s.cond):
                ex(s.body)
                tick()

    for s in program.stmts:
        ex(s)
    return env, out


def run_tac(code, max_steps=MAX_STEPS):
    labels = {ins.res: i for i, ins in enumerate(code) if ins.op == "label"}
    env, out = {}, []

    def val(x):
        if _NUM.match(x):
            return float(x) if "." in x else int(x)
        try:
            return env[x]
        except KeyError:
            raise RuntimeFault(f"read of undefined name '{x}'")

    pc = steps = 0
    while pc < len(code):
        steps += 1
        if steps > max_steps:
            raise RuntimeFault("step limit exceeded (possible infinite loop)")
        ins = code[pc]
        op = ins.op
        pc += 1
        if op == "label":
            continue
        if op == "goto":
            pc = labels[ins.res]
        elif op == "if_true":
            if val(ins.a1):
                pc = labels[ins.res]
        elif op == "if_false":
            if not val(ins.a1):
                pc = labels[ins.res]
        elif ins.is_cond_jump:
            if apply_binary(op[2:], val(ins.a1), val(ins.a2)):
                pc = labels[ins.res]
        elif op == "=":
            env[ins.res] = val(ins.a1)
        elif op in ("neg", "!"):
            env[ins.res] = apply_unary(op, val(ins.a1))
        elif op == "print":
            out.append(str(val(ins.a1)))
        else:
            try:
                env[ins.res] = apply_binary(op, val(ins.a1), val(ins.a2))
            except ZeroDivisionError as ex:
                raise RuntimeFault(str(ex))
    return {k: v for k, v in env.items() if not (k.startswith("t") and k[1:].isdigit())}, out
