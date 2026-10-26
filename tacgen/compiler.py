"""High-level driver: source text -> everything the CLI / tests need."""
from dataclasses import dataclass
from typing import List
from .lexer import tokenize
from .parser import Parser
from .optimizer import fold_program, peephole
from .codegen import CodeGenerator, renumber, Instr


@dataclass
class CompileResult:
    source: str
    tokens: list
    ast: object
    code: List[Instr]
    symtab: dict
    optimize: bool = False
    bool_mode: str = "jump"


def compile_source(source, optimize=False, bool_mode="jump"):
    tokens = tokenize(source)
    ast = Parser(tokens).parse()
    if optimize:
        ast = fold_program(ast)
    gen = CodeGenerator(bool_mode)
    code = gen.generate(ast)
    if optimize:
        code = peephole(code)
    return CompileResult(source, tokens, ast, renumber(code), gen.symtab, optimize, bool_mode)
