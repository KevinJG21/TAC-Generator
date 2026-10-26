# Release checklist — Review 3

- [x] Lexer, parser, AST, semantic diagnostics, and inferred symbol table
- [x] Arithmetic, relational, Boolean, assignment, `if`/`else`, `while`, blocks, and `print`
- [x] TAC, quadruples, triples, short-circuit jump mode, and Boolean value mode
- [x] Constant folding, copy elimination, redundant jump, and unused-label cleanup
- [x] CFG basic blocks and successor edges
- [x] SSA renaming, phi placement, dominators, and dominance frontiers
- [x] AST interpreter versus TAC VM equivalence check
- [x] 27 automated tests, including randomized semantic checks
- [x] Reproducible example benchmark harness
- [x] CLI, examples, README, QA notes, and packaging metadata

The project is complete for its defined educational language scope. Functions,
arrays, and machine-code emission are intentionally outside that scope; they
would be a separate compiler-extension project rather than unfinished Review 3
requirements.
