"""Lexical analysis: source text -> list of tokens (regex based scanner)."""
import re
from dataclasses import dataclass
from .errors import CompileError

KEYWORDS = {"if", "else", "while", "print", "true", "false"}
_RESERVED = re.compile(r"^[tL]\d+$")   # t<n> / L<n> belong to the compiler

_SPEC = [
    ("COMMENT",    r"//[^\n]*|#[^\n]*|/\*.*?\*/"),
    ("BADCOMMENT", r"/\*"),
    ("NEWLINE",    r"\n"),
    ("SKIP",       r"[ \t\r]+"),
    ("NUM",        r"\d+\.\d+|\d+"),
    ("ID",         r"[A-Za-z_][A-Za-z0-9_]*"),
    ("OP",         r"<=|>=|==|!=|&&|\|\||[-+*/%<>=!(){};]"),
    ("BAD",        r"."),
]
_SCANNER = re.compile("|".join(f"(?P<{n}>{p})" for n, p in _SPEC), re.DOTALL)


@dataclass(frozen=True)
class Token:
    kind: str    # NUM | ID | KW | OP | EOF
    value: str
    line: int
    col: int


def tokenize(source):
    tokens = []
    line, line_start = 1, 0
    for m in _SCANNER.finditer(source):
        kind, text = m.lastgroup, m.group()
        col = m.start() - line_start + 1
        if kind == "NEWLINE":
            line += 1
            line_start = m.end()
        elif kind == "SKIP":
            continue
        elif kind == "COMMENT":
            n = text.count("\n")
            if n:
                line += n
                line_start = m.start() + text.rfind("\n") + 1
        elif kind == "BADCOMMENT":
            raise CompileError("Lexical", "unterminated comment", line, col)
        elif kind == "BAD":
            raise CompileError("Lexical", f"unexpected character {text!r}", line, col)
        elif kind == "ID":
            if text in KEYWORDS:
                tokens.append(Token("KW", text, line, col))
            elif _RESERVED.match(text):
                raise CompileError("Lexical",
                                   f"identifier '{text}' is reserved for compiler temporaries/labels",
                                   line, col)
            else:
                tokens.append(Token("ID", text, line, col))
        else:
            tokens.append(Token(kind, text, line, col))
    tokens.append(Token("EOF", "", line, len(source) - line_start + 1))
    return tokens
