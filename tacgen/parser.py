"""Recursive-descent parser.

    program    -> statement* EOF
    statement  -> IDENT '=' expr ';' | 'print' expr ';'
                | 'if' '(' expr ')' statement [ 'else' statement ]
                | 'while' '(' expr ')' statement | '{' statement* '}' | expr ';'
    expr       -> or
    or         -> and ( '||' and )*
    and        -> equality ( '&&' equality )*
    equality   -> relational ( ('==' | '!=') relational )*
    relational -> additive ( ('<' | '<=' | '>' | '>=') additive )*
    additive   -> term ( ('+' | '-') term )*
    term       -> unary ( ('*' | '/' | '%') unary )*
    unary      -> ('-' | '!') unary | primary
    primary    -> NUM | 'true' | 'false' | IDENT | '(' expr ')'
"""
from .ast_nodes import (Num, BoolLit, Var, Unary, Binary, Assign, Print,
                        ExprStmt, Block, If, While, Program)
from .errors import CompileError
from .lexer import tokenize


class Parser:
    def __init__(self, tokens):
        self.toks = tokens
        self.pos = 0

    @property
    def cur(self):
        return self.toks[self.pos]

    def _is(self, value):
        t = self.cur
        return t.value == value and t.kind in ("OP", "KW")

    def _advance(self):
        t = self.cur
        if t.kind != "EOF":
            self.pos += 1
        return t

    def _match(self, *values):
        if self.cur.kind in ("OP", "KW") and self.cur.value in values:
            return self._advance()
        return None

    def _expect(self, value, context=""):
        if self._is(value):
            return self._advance()
        t = self.cur
        found = "end of input" if t.kind == "EOF" else f"'{t.value}'"
        raise CompileError("Syntax", f"expected '{value}' {context}but found {found}", t.line, t.col)

    def parse(self):
        stmts = []
        while self.cur.kind != "EOF":
            stmts.append(self.statement())
        return Program(stmts)

    def statement(self):
        t = self.cur
        if t.kind == "KW":
            if t.value == "if":
                self._advance()
                self._expect("(", "after 'if' ")
                cond = self.expr()
                self._expect(")", "after condition ")
                then = self.statement()
                other = self.statement() if self._match("else") else None
                return If(cond, then, other, t.line)
            if t.value == "while":
                self._advance()
                self._expect("(", "after 'while' ")
                cond = self.expr()
                self._expect(")", "after condition ")
                return While(cond, self.statement(), t.line)
            if t.value == "print":
                self._advance()
                e = self.expr()
                self._expect(";", "after print expression ")
                return Print(e, t.line)
            if t.value == "else":
                raise CompileError("Syntax", "'else' without matching 'if'", t.line, t.col)
        if self._is("{"):
            self._advance()
            stmts = []
            while not self._is("}"):
                if self.cur.kind == "EOF":
                    raise CompileError("Syntax", "missing '}' before end of input", self.cur.line, self.cur.col)
                stmts.append(self.statement())
            self._advance()
            return Block(stmts, t.line)
        nxt = self.toks[self.pos + 1]
        if t.kind == "ID" and nxt.kind == "OP" and nxt.value == "=":
            self._advance()
            self._advance()
            value = self.expr()
            self._expect(";", "after assignment ")
            return Assign(t.value, value, t.line)
        e = self.expr()
        self._expect(";", "after expression ")
        return ExprStmt(e, t.line)

    def expr(self):
        return self._binary_level(0)

    _LEVELS = [("||",), ("&&",), ("==", "!="), ("<", "<=", ">", ">="), ("+", "-"), ("*", "/", "%")]

    def _binary_level(self, level):
        if level == len(self._LEVELS):
            return self.unary()
        node = self._binary_level(level + 1)
        while self.cur.kind == "OP" and self.cur.value in self._LEVELS[level]:
            op = self._advance()
            node = Binary(op.value, node, self._binary_level(level + 1), op.line)
        return node

    def unary(self):
        t = self.cur
        if t.kind == "OP" and t.value in ("-", "!"):
            self._advance()
            return Unary(t.value, self.unary(), t.line)
        return self.primary()

    def primary(self):
        t = self.cur
        if t.kind == "NUM":
            self._advance()
            return Num(float(t.value) if "." in t.value else int(t.value), t.value, t.line)
        if t.kind == "KW" and t.value in ("true", "false"):
            self._advance()
            return BoolLit(t.value == "true", t.line)
        if t.kind == "ID":
            self._advance()
            return Var(t.value, t.line)
        if self._match("("):
            e = self.expr()
            self._expect(")", "to close '(' ")
            return e
        found = "end of input" if t.kind == "EOF" else f"'{t.value}'"
        raise CompileError("Syntax", f"unexpected {found}; expected an expression", t.line, t.col)


def parse_source(source):
    return Parser(tokenize(source)).parse()
