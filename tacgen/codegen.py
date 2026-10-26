"""Three Address Code generation.

* Arithmetic   : t = a op b          (one temporary per operator)
* Assignment   : x = t
* Booleans/relationals, two schemes (``bool_mode``):
    - "jump"  (default): short-circuit jumping code with fall-through (Aho et al., ch. 6.6)
    - "value": Booleans are 0/1 values:  t = a < b ,  t = a && b ,  t = ! a
* if / while use labels and the same jumping code.
"""
import re
from dataclasses import dataclass
from .ast_nodes import (Num, BoolLit, Var, Unary, Binary, Assign, Print,
                        ExprStmt, Block, If, While)
from .errors import CompileError
from .ops import ARITH, REL, LOGIC, NEG_REL

FALL = None
TEMP_RE = re.compile(r"^t\d+$")
LABEL_RE = re.compile(r"^L\d+$")


class Instr:
    """One three-address instruction stored as a quadruple (op, a1, a2, res)."""
    __slots__ = ("op", "a1", "a2", "res")

    def __init__(self, op, a1=None, a2=None, res=None):
        self.op, self.a1, self.a2, self.res = op, a1, a2, res

    def copy(self):
        return Instr(self.op, self.a1, self.a2, self.res)

    @property
    def is_cond_jump(self):
        return self.op in ("if_true", "if_false") or (self.op.startswith("if") and self.op[2:] in REL)

    @property
    def is_jump(self):
        return self.op == "goto" or self.is_cond_jump

    def text(self):
        op = self.op
        if op == "label":
            return f"{self.res}:"
        if op == "goto":
            return f"goto {self.res}"
        if op == "if_true":
            return f"if {self.a1} goto {self.res}"
        if op == "if_false":
            return f"ifFalse {self.a1} goto {self.res}"
        if self.is_cond_jump:
            return f"if {self.a1} {op[2:]} {self.a2} goto {self.res}"
        if op == "neg":
            return f"{self.res} = - {self.a1}"
        if op == "!":
            return f"{self.res} = ! {self.a1}"
        if op == "=":
            return f"{self.res} = {self.a1}"
        if op == "print":
            return f"print {self.a1}"
        return f"{self.res} = {self.a1} {op} {self.a2}"

    def quad(self):
        op = "uminus" if self.op == "neg" else self.op
        return (op, self.a1 or "", self.a2 or "", self.res or "")


@dataclass
class Symbol:
    type: str
    line: int


class CodeGenerator:
    def __init__(self, bool_mode="jump"):
        if bool_mode not in ("jump", "value"):
            raise ValueError("bool_mode must be 'jump' or 'value'")
        self.bool_mode = bool_mode
        self.code, self.symtab = [], {}
        self._t = self._l = 0

    def emit(self, op, a1=None, a2=None, res=None):
        self.code.append(Instr(op, a1, a2, res))

    def new_temp(self):
        self._t += 1
        return f"t{self._t}"

    def new_label(self):
        self._l += 1
        return f"L{self._l}"

    def place(self, label):
        self.emit("label", res=label)

    def generate(self, program):
        for s in program.stmts:
            self.stmt(s)
        return self.code

    def stmt(self, s):
        if isinstance(s, Assign):
            v = self.expr(s.value)
            ty = self.type_of(s.value)
            self.emit("=", v, None, s.name)
            self.symtab.setdefault(s.name, Symbol(ty, s.line))
        elif isinstance(s, Print):
            self.emit("print", self.expr(s.value))
        elif isinstance(s, ExprStmt):
            self.expr(s.expr)
        elif isinstance(s, Block):
            for x in s.stmts:
                self.stmt(x)
        elif isinstance(s, If):
            if s.otherwise is None:
                l_end = self.new_label()
                self.cond(s.cond, FALL, l_end)
                self.stmt(s.then)
                self.place(l_end)
            else:
                l_else, l_end = self.new_label(), self.new_label()
                self.cond(s.cond, FALL, l_else)
                self.stmt(s.then)
                self.emit("goto", res=l_end)
                self.place(l_else)
                self.stmt(s.otherwise)
                self.place(l_end)
        elif isinstance(s, While):
            l_begin, l_end = self.new_label(), self.new_label()
            self.place(l_begin)
            self.cond(s.cond, FALL, l_end)
            self.stmt(s.body)
            self.emit("goto", res=l_begin)
            self.place(l_end)
        else:
            raise CompileError("Internal", f"unknown statement {type(s).__name__}")

    def expr(self, e):
        if isinstance(e, Num):
            return e.text
        if isinstance(e, BoolLit):
            return "1" if e.value else "0"
        if isinstance(e, Var):
            if e.name not in self.symtab:
                raise CompileError("Semantic", f"variable '{e.name}' used before assignment", e.line)
            return e.name
        if isinstance(e, Unary):
            if e.op == "!" and self.bool_mode == "jump":
                return self.materialize(e)
            a = self.expr(e.operand)
            t = self.new_temp()
            self.emit("neg" if e.op == "-" else "!", a, None, t)
            return t
        if isinstance(e, Binary):
            if e.op in ARITH or self.bool_mode == "value":
                a = self.expr(e.left)
                b = self.expr(e.right)
                t = self.new_temp()
                self.emit(e.op, a, b, t)
                return t
            return self.materialize(e)
        raise CompileError("Internal", f"unknown expression {type(e).__name__}")

    def materialize(self, e):
        t = self.new_temp()
        l_false, l_end = self.new_label(), self.new_label()
        self.cond(e, FALL, l_false)
        self.emit("=", "1", None, t)
        self.emit("goto", res=l_end)
        self.place(l_false)
        self.emit("=", "0", None, t)
        self.place(l_end)
        return t

    def cond(self, e, t, f):
        """Jump to t if e is true, to f if false; FALL = continue with the next instruction."""
        if isinstance(e, BoolLit):
            target = t if e.value else f
            if target is not FALL:
                self.emit("goto", res=target)
            return
        if self.bool_mode == "jump":
            if isinstance(e, Unary) and e.op == "!":
                return self.cond(e.operand, f, t)
            if isinstance(e, Binary) and e.op == "||":
                b1 = t if t is not FALL else self.new_label()
                self.cond(e.left, b1, FALL)
                self.cond(e.right, t, f)
                if t is FALL:
                    self.place(b1)
                return
            if isinstance(e, Binary) and e.op == "&&":
                b1 = f if f is not FALL else self.new_label()
                self.cond(e.left, FALL, b1)
                self.cond(e.right, t, f)
                if f is FALL:
                    self.place(b1)
                return
            if isinstance(e, Binary) and e.op in REL:
                a = self.expr(e.left)
                b = self.expr(e.right)
                if t is not FALL:
                    self.emit("if" + e.op, a, b, t)
                    if f is not FALL:
                        self.emit("goto", res=f)
                elif f is not FALL:
                    self.emit("if" + NEG_REL[e.op], a, b, f)
                return
        a = self.expr(e)
        if t is not FALL:
            self.emit("if_true", a, None, t)
            if f is not FALL:
                self.emit("goto", res=f)
        elif f is not FALL:
            self.emit("if_false", a, None, f)

    def type_of(self, e):
        if isinstance(e, Num):
            return "float" if isinstance(e.value, float) else "int"
        if isinstance(e, BoolLit):
            return "bool"
        if isinstance(e, Var):
            return self.symtab[e.name].type if e.name in self.symtab else "int"
        if isinstance(e, Unary):
            return "bool" if e.op == "!" else ("int" if self.type_of(e.operand) == "bool" else self.type_of(e.operand))
        if isinstance(e, Binary):
            if e.op in REL or e.op in LOGIC:
                return "bool"
            l, r = self.type_of(e.left), self.type_of(e.right)
            return "float" if "float" in (l, r) else "int"
        return "int"


def renumber(code):
    """Rename temporaries/labels to t1.. / L1.. in order of first appearance."""
    tmap, lmap = {}, {}

    def fix(x):
        if not isinstance(x, str):
            return x
        if TEMP_RE.match(x):
            return tmap.setdefault(x, f"t{len(tmap) + 1}")
        if LABEL_RE.match(x):
            return lmap.setdefault(x, f"L{len(lmap) + 1}")
        return x

    return [Instr(i.op, fix(i.a1), fix(i.a2), fix(i.res)) for i in code]
