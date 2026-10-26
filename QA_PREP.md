# Viva / Q&A preparation

1. **What is Three Address Code?** Linear IR where each instruction has at most one operator and three addresses (two operands, one result), e.g. `t1 = b * c`.
2. **Quadruples vs triples?** Quadruples store (op, arg1, arg2, result) and name temporaries explicitly; triples drop the result and refer to earlier instructions by index, so reordering is harder.
3. **How are Booleans translated?** Default is flow-of-control: `&&`/`||`/`!` become conditional jumps with true/false labels (short-circuit). `--bool-mode value` treats them as 0/1 values.
4. **What is fall-through?** The true (or false) branch is the next instruction, so only one conditional jump is emitted and no extra `goto`.
5. **Why negate the relational operator?** For `if (a < b) S`, we jump over S when the condition is false, so we emit `if a >= b goto L1`.
6. **How is precedence handled?** One recursive-descent function per precedence level; left-associative loops.
7. **What does -O do?** Constant folding on the AST, copy elimination (`t1 = a+b; x = t1` -> `x = a+b`), redundant goto and unused label removal.
8. **How do you know the output is correct?** The TAC is executed on a VM and compared with an AST interpreter; 300 random programs x 4 modes pass.
9. **Where are semantic errors caught?** Use before assignment; constant division by zero (with -O); runtime division by zero in the VM.
10. **Limitations / future work?** No functions, arrays or declared types; Review 2 adds basic blocks and CFG, while SSA and final packaging remain future work.
11. **What does the Review-2 CFG add?** It identifies leaders, groups TAC into basic blocks, and records directed successor edges. It is analysis output only; SSA and machine-code generation remain future work.
12. **What does Review 3 add?** SSA construction over the generated CFG: dominators, dominance frontiers, phi placement at joins, and version renaming. It is exposed with `--ssa` and does not alter the executable TAC.
13. **What is a phi node?** At a CFG join, `x = phi(B1: x_1, B2: x_2)` selects the reaching definition from the predecessor that transferred control. It makes merged data flow explicit.
14. **What is the final scope?** The defined educational language is complete and packaged. Functions, arrays, and machine-code emission are intentionally excluded rather than silently claimed as implemented.
