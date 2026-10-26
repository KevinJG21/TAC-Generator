"""Command line interface:  python -m tacgen [file] [options]"""
import argparse
import sys
from . import compile_source, CompileError
from .ast_nodes import dump
from .formats import (format_tokens, format_tac, format_quads, format_triples,
                       format_symtab, format_cfg, format_ssa)
from .runtime import run_ast, run_tac, RuntimeFault


def build_parser():
    p = argparse.ArgumentParser(prog="tacgen", description="Three Address Code generator for "
                                "arithmetic, assignment, relational and Boolean expressions.")
    p.add_argument("file", nargs="?", help="source file (default: stdin)")
    p.add_argument("-e", "--expr", help="compile this source text instead of a file")
    p.add_argument("-O", "--optimize", action="store_true", help="constant folding + peephole clean-up")
    p.add_argument("--bool-mode", choices=("jump", "value"), default="jump",
                   help="jump: short-circuit jumping code (default); value: Booleans as 0/1 values")
    p.add_argument("--tokens", action="store_true")
    p.add_argument("--ast", action="store_true")
    p.add_argument("--quads", action="store_true")
    p.add_argument("--triples", action="store_true")
    p.add_argument("--symtab", action="store_true")
    p.add_argument("--cfg", action="store_true", help="show basic blocks and CFG edges")
    p.add_argument("--ssa", action="store_true", help="show SSA renaming, phi nodes, and dominators")
    p.add_argument("--run", action="store_true", help="execute TAC on the VM and cross-check with the AST interpreter")
    p.add_argument("--all", action="store_true", help="show every phase")
    p.add_argument("-o", "--output", help="write the TAC listing to this file")
    return p


def section(title, body):
    print(f"\n=== {title} ===")
    print(body)


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.expr is not None:
        source = args.expr
    elif args.file:
        with open(args.file, encoding="utf-8") as f:
            source = f.read()
    else:
        source = sys.stdin.read()
    try:
        res = compile_source(source, optimize=args.optimize, bool_mode=args.bool_mode)
    except CompileError as e:
        print(e.render(source), file=sys.stderr)
        return 1
    show = args.all
    print("=== Source ===")
    print(source.rstrip())
    if show or args.tokens:
        section("Tokens", format_tokens(res.tokens))
    if show or args.ast:
        section("Abstract Syntax Tree" + (" (after constant folding)" if args.optimize else ""), dump(res.ast))
    section("Three Address Code" + (" (optimised)" if args.optimize else ""), format_tac(res.code))
    if show or args.quads:
        section("Quadruples", format_quads(res.code))
    if show or args.triples:
        section("Triples", format_triples(res.code))
    if show or args.symtab:
        section("Symbol Table", format_symtab(res.symtab))
    if show or args.cfg:
        section("Control-Flow Graph", format_cfg(res.code))
    if show or args.ssa:
        section("Static Single Assignment", format_ssa(res.code))
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(format_tac(res.code) + "\n")
    if show or args.run:
        try:
            env_ref, out_ref = run_ast(res.ast)
            env_tac, out_tac = run_tac(res.code)
        except RuntimeFault as e:
            print(f"\nRuntime error: {e}", file=sys.stderr)
            return 2
        section("Program output (TAC virtual machine)", "\n".join(out_tac) if out_tac else "(no output)")
        ok = env_ref == env_tac and out_ref == out_tac
        print(f"\nVerification against AST interpreter: {'PASS' if ok else 'FAIL'}")
        if env_tac:
            print("Final variables:", ", ".join(f"{k}={v}" for k, v in env_tac.items()))
        return 0 if ok else 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
