"""Optional optimisations (-O): constant folding on the AST; peephole on the TAC
(copy elimination, redundant goto removal, unused label removal)."""
from collections import Counter
from .ast_nodes import (Num, BoolLit, Unary, Binary, Assign, Print,
                        ExprStmt, Block, If, While, Program)
from .codegen import TEMP_RE
from .errors import CompileError
from .ops import ARITH, REL, LOGIC, apply_binary


def _const(e):
    if isinstance(e, Num):
        return e.value
    if isinstance(e, BoolLit):
        return int(e.value)
    return None


def _mk_num(v):
    return Num(v, str(v))


def fold_expr(e):
    if isinstance(e, Unary):
        o = fold_expr(e.operand)
        c = _const(o)
        if c is not None:
            return _mk_num(-c) if e.op == "-" else BoolLit(not c, e.line)
        return Unary(e.op, o, e.line)
    if isinstance(e, Binary):
        l, r = fold_expr(e.left), fold_expr(e.right)
        cl, cr = _const(l), _const(r)
        if e.op == "&&" and cl is not None and not cl:
            return BoolLit(False, e.line)
        if e.op == "||" and cl is not None and cl:
            return BoolLit(True, e.line)
        if cl is not None and cr is not None:
            try:
                v = apply_binary(e.op, cl, cr)
            except ZeroDivisionError as ex:
                raise CompileError("Semantic", f"{ex} in constant expression", e.line)
            return _mk_num(v) if e.op in ARITH else BoolLit(bool(v), e.line)
        return Binary(e.op, l, r, e.line)
    return e


def fold_stmt(s):
    if isinstance(s, Assign):
        return Assign(s.name, fold_expr(s.value), s.line)
    if isinstance(s, Print):
        return Print(fold_expr(s.value), s.line)
    if isinstance(s, ExprStmt):
        return ExprStmt(fold_expr(s.expr), s.line)
    if isinstance(s, Block):
        return Block([fold_stmt(x) for x in s.stmts], s.line)
    if isinstance(s, If):
        return If(fold_expr(s.cond), fold_stmt(s.then),
                  fold_stmt(s.otherwise) if s.otherwise is not None else None, s.line)
    if isinstance(s, While):
        return While(fold_expr(s.cond), fold_stmt(s.body), s.line)
    return s


def fold_program(p):
    return Program([fold_stmt(s) for s in p.stmts])


_VALUE_OPS = ARITH | REL | LOGIC | {"neg", "!"}


def _copy_elimination(code):
    uses, defs = Counter(), Counter()
    for ins in code:
        for a in (ins.a1, ins.a2):
            if isinstance(a, str) and TEMP_RE.match(a):
                uses[a] += 1
        if ins.res and TEMP_RE.match(ins.res):
            defs[ins.res] += 1
    out, i = [], 0
    while i < len(code):
        cur = code[i]
        if i + 1 < len(code):
            nxt = code[i + 1]
            if (cur.op in _VALUE_OPS and cur.res and TEMP_RE.match(cur.res)
                    and nxt.op == "=" and nxt.a1 == cur.res and not TEMP_RE.match(nxt.res)
                    and uses[cur.res] == 1 and defs[cur.res] == 1):
                merged = cur.copy()
                merged.res = nxt.res
                out.append(merged)
                i += 2
                continue
        out.append(cur)
        i += 1
    return out


def _remove_goto_next(code):
    out = []
    for i, ins in enumerate(code):
        if ins.op == "goto":
            j, redundant = i + 1, False
            while j < len(code) and code[j].op == "label":
                if code[j].res == ins.res:
                    redundant = True
                    break
                j += 1
            if redundant:
                continue
        out.append(ins)
    return out


def _remove_unused_labels(code):
    used = {ins.res for ins in code if ins.is_jump}
    return [ins for ins in code if ins.op != "label" or ins.res in used]


def peephole(code):
    while True:
        before = len(code)
        code = _remove_unused_labels(_remove_goto_next(_copy_elimination(code)))
        if len(code) == before:
            return code
