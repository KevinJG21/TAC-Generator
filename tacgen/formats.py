"""Text renderings: token table, TAC listing, quadruples, triples, symbol table."""
from collections import Counter
from .codegen import TEMP_RE
from .ops import ARITH, REL, LOGIC
from .cfg import build_cfg
from .ssa import build_ssa, instruction_text


def table(headers, rows):
    rows = [[str(c) for c in r] for r in rows]
    widths = [max([len(h)] + [len(r[i]) for r in rows]) for i, h in enumerate(headers)]
    line = "+-" + "-+-".join("-" * w for w in widths) + "-+"
    fmt = "| " + " | ".join("{:<%d}" % w for w in widths) + " |"
    out = [line, fmt.format(*headers), line] + [fmt.format(*r) for r in rows] + [line]
    return "\n".join(out)


def format_tokens(tokens):
    kind_names = {
        "OP": "operator",
        "ID": "identifier",
        "NUM": "number",
        "KW": "keyword",
        "EOF": "end of file",
    }
    return table(["Line", "Col", "Kind", "Lexeme"],
                 [(t.line, t.col, kind_names.get(t.kind, t.kind), t.value)
                  for t in tokens if t.kind != "EOF"])


def format_tac(code):
    return "\n".join(i.text() if i.op == "label" else "    " + i.text() for i in code)


def format_quads(code):
    return table(["#", "op", "arg1", "arg2", "result"], [(i, *ins.quad()) for i, ins in enumerate(code)])


def format_symtab(symtab):
    return table(["Name", "Type", "First assigned (line)"], [(n, s.type, s.line) for n, s in symtab.items()])


def format_cfg(code):
    """Render the basic blocks and directed CFG edges for a TAC listing."""
    blocks = build_cfg(code)
    if not blocks:
        return "(empty CFG)"
    rows = []
    for block in blocks:
        body = " | ".join(ins.text() for ins in block.code)
        succ = ", ".join(f"B{n}" for n in block.successors) or "(exit)"
        rows.append((f"B{block.number}", f"{block.start}-{block.end - 1}", body, succ))
    return table(["Block", "TAC range", "Instructions", "Successors"], rows)


def format_ssa(code):
    """Render the SSA analysis view, including phi nodes and dominator data."""
    program = build_ssa(code)
    if not program.blocks:
        return "(empty SSA)"
    lines = []
    for block in program.blocks:
        succ = ", ".join(f"B{n}" for n in block.successors) or "exit"
        lines.append(f"B{block.number}  [succ: {succ}]")
        for var in sorted(block.phis):
            incoming = ", ".join(f"B{pred}: {value}" for pred, value in block.phis[var])
            result = block.phi_results.get(var, var)
            lines.append(f"    {result} = phi({incoming})")
        for ins in block.instructions:
            lines.append("    " + instruction_text(ins))
    lines.append("Dominator tree: " + ", ".join(
        f"B{child}<-B{parent}" for child, parent in sorted(program.idom.items()) if parent is not None))
    return "\n".join(lines)


_VALUE_OPS = ARITH | REL | LOGIC | {"neg", "!"}


def build_triples(code):
    """Triples (op, arg1, arg2); single-definition temporaries are referenced by triple index."""
    defs = Counter(i.res for i in code if i.res and TEMP_RE.match(i.res) and i.op != "label")
    triples, label_at, temp_idx = [], {}, {}

    def ref(x):
        if x is None:
            return ""
        return f"({temp_idx[x]})" if x in temp_idx else x

    def add(op, a1="", a2=""):
        triples.append([op, a1, a2])
        return len(triples) - 1

    for ins in code:
        op = ins.op
        if op == "label":
            label_at[ins.res] = len(triples)
        elif op == "goto":
            add("goto", ("LABEL", ins.res))
        elif op in ("if_true", "if_false"):
            add("ifTrue" if op == "if_true" else "ifFalse", ref(ins.a1), ("LABEL", ins.res))
        elif ins.is_cond_jump:
            k = add(op[2:], ref(ins.a1), ref(ins.a2))
            add("ifTrue", f"({k})", ("LABEL", ins.res))
        elif op == "print":
            add("print", ref(ins.a1))
        elif op == "=":
            add("=", ins.res, ref(ins.a1))
        elif op in _VALUE_OPS:
            k = add("uminus" if op == "neg" else op, ref(ins.a1), ref(ins.a2) if ins.a2 is not None else "")
            if TEMP_RE.match(ins.res) and defs[ins.res] == 1:
                temp_idx[ins.res] = k
            else:
                add("=", ins.res, f"({k})")
    if any(v == len(triples) for v in label_at.values()):
        add("nop")
    fix = lambda x: f"({label_at[x[1]]})" if isinstance(x, tuple) else x
    return [(op, fix(a), fix(b)) for op, a, b in triples]


def format_triples(code):
    return table(["#", "op", "arg1", "arg2"], [(i, *t) for i, t in enumerate(build_triples(code))])
