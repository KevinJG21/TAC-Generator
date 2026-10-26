"""Static Single Assignment (SSA) construction over generated TAC.

The TAC generator deliberately keeps mutable source variables because that is
the clearest form for a first intermediate representation.  This module adds
the next compiler-analysis view: dominators, dominance frontiers, phi
placement, and renaming.  It is an analysis/rendering pass; the original TAC
and VM semantics are unchanged.
"""
from dataclasses import dataclass, field
from collections import defaultdict
import re

from .cfg import build_cfg


_NUMBER = re.compile(r"^-?\d+(\.\d+)?$")
_TEMP = re.compile(r"^t\d+$")


@dataclass
class SSABlock:
    number: int
    start: int
    end: int
    phis: dict = field(default_factory=dict)
    phi_results: dict = field(default_factory=dict)
    instructions: list = field(default_factory=list)
    successors: list = field(default_factory=list)


@dataclass
class SSAProgram:
    blocks: list
    dominators: dict
    idom: dict
    dominance_frontier: dict


def _is_jump(ins):
    return ins.op == "goto" or ins.is_cond_jump


def _defines(ins):
    return (ins.res is not None and ins.op not in ("label", "goto", "print")
            and not _is_jump(ins))


def _operand(value):
    return isinstance(value, str) and not _NUMBER.match(value) and not value.startswith("L")


def _base(value):
    if not isinstance(value, str):
        return value
    return value.split("#", 1)[0] if "#" in value and value.rsplit("#", 1)[1].isdigit() else value


def _dominators(cfg):
    n = len(cfg)
    preds = {i: [] for i in range(n)}
    for block in cfg:
        for succ in block.successors:
            preds[succ].append(block.number)
    dom = {0: {0}}
    for i in range(1, n):
        dom[i] = set(range(n))
    changed = True
    while changed:
        changed = False
        for i in range(1, n):
            incoming = preds[i]
            value = ({i} | set.intersection(*(dom[p] for p in incoming))) if incoming else {i}
            if value != dom[i]:
                dom[i] = value
                changed = True
    idom = {0: None}
    for i in range(1, n):
        strict = dom[i] - {i}
        candidates = [d for d in strict if not any(d != other and d in dom[other] for other in strict)]
        idom[i] = candidates[0] if candidates else None
    return dom, idom, preds


def _frontiers(cfg, idom, preds):
    df = {i: set() for i in range(len(cfg))}
    for i in range(len(cfg)):
        if len(preds[i]) >= 2:
            for runner in preds[i]:
                while runner is not None and runner != idom.get(i):
                    df[runner].add(i)
                    runner = idom.get(runner)
    return df


def build_ssa(code):
    """Build an SSA view from TAC and return an :class:`SSAProgram`.

    Definitions are renamed as ``name_version``.  Phi nodes are inserted at
    dominance frontiers and receive one incoming value per predecessor.  This
    makes joins and loop-carried values explicit while retaining the source
    TAC's block structure and branch targets.
    """
    cfg = build_cfg(code)
    if not cfg:
        return SSAProgram([], {}, {}, {})
    dom, idom, preds = _dominators(cfg)
    df = _frontiers(cfg, idom, preds)
    blocks = [SSABlock(b.number, b.start, b.end, successors=list(b.successors)) for b in cfg]

    defs_by_var = defaultdict(set)
    for block in cfg:
        for ins in block.code:
            if _defines(ins):
                defs_by_var[_base(ins.res)].add(block.number)

    phi_vars = {i: set() for i in range(len(cfg))}
    # Compiler temporaries are already single-definition names in TAC.  Phi
    # placement is therefore needed for source variables, not for t<n>; this
    # keeps the educational output focused on source-level data flow.
    for var, definition_blocks in defs_by_var.items():
        if _TEMP.match(var):
            continue
        work = list(definition_blocks)
        seen = set(definition_blocks)
        while work:
            x = work.pop()
            for y in df[x]:
                if var not in phi_vars[y]:
                    phi_vars[y].add(var)
                    if y not in seen:
                        seen.add(y)
                        work.append(y)
    for number, variables in phi_vars.items():
        for var in variables:
            blocks[number].phis[var] = []

    children = defaultdict(list)
    for block, parent in idom.items():
        if parent is not None:
            children[parent].append(block)
    for value in children.values():
        value.sort()

    counters = defaultdict(int)
    stacks = defaultdict(list)
    for var in defs_by_var:
        stacks[var].append(f"{var}#0")

    def new_name(var):
        counters[var] += 1
        name = f"{var}#{counters[var]}"
        stacks[var].append(name)
        return name

    def current(var):
        return stacks[var][-1] if stacks[var] else f"{var}#0"

    def rename_value(value):
        if not _operand(value):
            return value
        var = _base(value)
        return current(var) if var in defs_by_var else value

    def rename_block(number):
        block = blocks[number]
        pushed = []
        for var in sorted(phi_vars[number]):
            new_name(var)
            block.phi_results[var] = current(var)
            pushed.append(var)
        for ins in cfg[number].code:
            if ins.op == "label":
                block.instructions.append(ins)
                continue
            a1 = rename_value(ins.a1)
            a2 = rename_value(ins.a2)
            res = ins.res
            if _defines(ins):
                var = _base(res)
                res = new_name(var)
                pushed.append(var)
            block.instructions.append((ins.op, a1, a2, res))
        for succ in block.successors:
            for var in sorted(phi_vars[succ]):
                blocks[succ].phis[var].append((number, current(var)))
        for child in children[number]:
            rename_block(child)
        for var in reversed(pushed):
            stacks[var].pop()

    rename_block(0)
    for block in blocks:
        for var in phi_vars[block.number]:
            block.phis[var] = sorted(block.phis[var], key=lambda item: item[0])
    return SSAProgram(blocks, dom, idom, df)


def instruction_text(item):
    """Render either an original TAC instruction or a renamed SSA tuple."""
    if hasattr(item, "text"):
        return item.text()
    op, a1, a2, res = item
    if op == "label":
        return f"{res}:"
    if op == "goto":
        return f"goto {res}"
    if op == "if_true":
        return f"if {a1} goto {res}"
    if op == "if_false":
        return f"ifFalse {a1} goto {res}"
    if op.startswith("if"):
        return f"if {a1} {op[2:]} {a2} goto {res}"
    if op == "neg":
        return f"{res} = - {a1}"
    if op == "!":
        return f"{res} = ! {a1}"
    if op == "=":
        return f"{res} = {a1}"
    if op == "print":
        return f"print {a1}"
    return f"{res} = {a1} {op} {a2}"
