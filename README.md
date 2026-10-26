# Three Address Code (TAC) Generator — Review 3 release

Compiler Design Lab (BCSE307P) project: a three-address-code generator for a language with
**arithmetic expressions, assignments, relational expressions and Boolean expressions**
(plus `if / else / while` and `print`, so Boolean code is actually exercised). Pure Python 3.8+.

## Run
```bash
python -m tacgen examples/03_boolean.src --all              # tokens, AST, TAC, quads, triples, symbol table, CFG, run
python -m tacgen examples/04_control_flow.src --run         # execute TAC on the VM, cross-check with AST interpreter
python -m tacgen examples/07_review2_demo.src --cfg --ssa --run  # CFG + SSA + execution evidence
python -m tacgen -e "x = 2 + 3 * 4;" -O                     # optimised
python -m tacgen examples/03_boolean.src --bool-mode value  # Booleans as 0/1 values
python -m unittest discover -s tests -v                     # 27 tests (incl. 300 random programs)
python benchmark.py --repeat 5                             # reproducible example benchmark
```

## Pipeline
| Phase | File | What it does |
|---|---|---|
| Lexical | `lexer.py` | regex scanner, line/col, comments, reserved `t<n>`/`L<n>` |
| Syntax | `parser.py`, `ast_nodes.py` | recursive descent, 6 precedence levels, AST |
| Semantic | `codegen.py` | use-before-assignment, constant /0, symbol table with inferred types |
| Optimise (`-O`) | `optimizer.py` | constant folding, copy elimination, redundant goto/label removal |
| Codegen | `codegen.py` | temporaries, labels, short-circuit jumping code |
| Output | `formats.py` | TAC, quadruples, triples |
| Verify | `runtime.py` | AST interpreter + TAC VM must agree |
| Control flow (Review 2) | `cfg.py` | basic blocks and CFG successors from TAC |
| SSA analysis (Review 3) | `ssa.py` | dominators, dominance frontiers, phi placement, renaming |

Review 3 completes the defined educational project scope: source-to-TAC
translation, multiple IR views, optimization, CFG/SSA inspection, VM
verification, regression tests, benchmark harness, and release packaging.
Functions, arrays, and machine-code emission are intentionally outside this
small language's scope.

## Language
```
statement -> id = expr ; | print expr ; | if (expr) stmt [else stmt] | while (expr) stmt | { stmt* } | expr ;
expr: || < && < == != < < <= > >= < + - < * / % < unary(- !) < primary(number|true|false|id|(expr))
```
Integer `/` and `%` follow C (truncate toward zero). Booleans are the integers 1 / 0.
