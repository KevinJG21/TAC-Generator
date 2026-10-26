"""Three Address Code (TAC) generator for a small expression language.

Pipeline:  source -> lexer -> parser (AST) -> [constant folding] -> TAC generator
           -> [peephole clean-up] -> quadruples / triples -> (optional) TAC virtual machine
"""
from .compiler import compile_source, CompileResult  # noqa: F401
from .errors import CompileError  # noqa: F401
from .cfg import BasicBlock, build_cfg  # noqa: F401
from .ssa import SSAProgram, SSABlock, build_ssa  # noqa: F401

__version__ = "2.0.0"
