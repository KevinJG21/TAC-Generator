"""Abstract syntax tree node classes and a tree printer."""
from dataclasses import dataclass, field
from typing import List, Optional, Union


@dataclass
class Num:
    value: Union[int, float]
    text: str
    line: int = 0


@dataclass
class BoolLit:
    value: bool
    line: int = 0


@dataclass
class Var:
    name: str
    line: int = 0


@dataclass
class Unary:
    op: str
    operand: object
    line: int = 0


@dataclass
class Binary:
    op: str
    left: object
    right: object
    line: int = 0


@dataclass
class Assign:
    name: str
    value: object
    line: int = 0


@dataclass
class Print:
    value: object
    line: int = 0


@dataclass
class ExprStmt:
    expr: object
    line: int = 0


@dataclass
class Block:
    stmts: List[object] = field(default_factory=list)
    line: int = 0


@dataclass
class If:
    cond: object
    then: object
    otherwise: Optional[object] = None
    line: int = 0


@dataclass
class While:
    cond: object
    body: object
    line: int = 0


@dataclass
class Program:
    stmts: List[object] = field(default_factory=list)


def dump(node, indent=0):
    pad = "  " * indent
    if isinstance(node, Num):
        return f"{pad}Num({node.text})"
    if isinstance(node, BoolLit):
        return f"{pad}Bool({str(node.value).lower()})"
    if isinstance(node, Var):
        return f"{pad}Var({node.name})"
    if isinstance(node, Unary):
        return f"{pad}Unary({node.op})\n{dump(node.operand, indent + 1)}"
    if isinstance(node, Binary):
        return (f"{pad}Binary({node.op})\n{dump(node.left, indent + 1)}\n"
                f"{dump(node.right, indent + 1)}")
    if isinstance(node, Assign):
        return f"{pad}Assign({node.name})\n{dump(node.value, indent + 1)}"
    if isinstance(node, Print):
        return f"{pad}Print\n{dump(node.value, indent + 1)}"
    if isinstance(node, ExprStmt):
        return f"{pad}ExprStmt\n{dump(node.expr, indent + 1)}"
    if isinstance(node, (Block, Program)):
        kids = "\n".join(dump(s, indent + 1) for s in node.stmts)
        return f"{pad}{type(node).__name__}" + (f"\n{kids}" if kids else "")
    if isinstance(node, If):
        s = f"{pad}If\n{pad}  cond:\n{dump(node.cond, indent + 2)}\n{pad}  then:\n{dump(node.then, indent + 2)}"
        if node.otherwise is not None:
            s += f"\n{pad}  else:\n{dump(node.otherwise, indent + 2)}"
        return s
    if isinstance(node, While):
        return (f"{pad}While\n{pad}  cond:\n{dump(node.cond, indent + 2)}\n"
                f"{pad}  body:\n{dump(node.body, indent + 2)}")
    return f"{pad}{type(node).__name__}"
