class CompileError(Exception):
    """Raised for lexical, syntax and semantic errors, carrying a source position."""

    def __init__(self, phase, message, line=None, col=None):
        super().__init__(message)
        self.phase = phase
        self.message = message
        self.line = line
        self.col = col

    def __str__(self):
        where = f" at line {self.line}, col {self.col}" if self.line and self.col else (
            f" at line {self.line}" if self.line else "")
        return f"{self.phase} error{where}: {self.message}"

    def render(self, source):
        out = [str(self)]
        if self.line:
            lines = source.splitlines()
            if 1 <= self.line <= len(lines):
                out.append("    " + lines[self.line - 1])
                if self.col:
                    out.append("    " + " " * (self.col - 1) + "^")
        return "\n".join(out)
