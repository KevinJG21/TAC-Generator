import glob, os, random, sys, unittest, io, contextlib
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tacgen import compile_source, CompileError
from tacgen.lexer import tokenize
from tacgen.parser import parse_source
from tacgen.ast_nodes import Unary
from tacgen.formats import format_tac, format_ssa, build_triples
from tacgen.runtime import run_ast, run_tac, RuntimeFault
from tacgen.cfg import build_cfg
from tacgen.ssa import build_ssa

CONFIGS = [(o, m) for o in (False, True) for m in ("jump", "value")]


def tac_lines(src, **kw):
    return [l.strip() for l in format_tac(compile_source(src, **kw).code).splitlines()]


class LexerTests(unittest.TestCase):
    def test_tokens_and_positions(self):
        toks = tokenize("x = a<=b;")
        self.assertEqual([t.value for t in toks[:-1]], ["x", "=", "a", "<=", "b", ";"])
        self.assertEqual((toks[3].line, toks[3].col), (1, 6))

    def test_comments_and_lines(self):
        ids = [t for t in tokenize("// c\n/* a\nb */ x = 1; # tail\ny = 2;") if t.kind == "ID"]
        self.assertEqual([(t.value, t.line) for t in ids], [("x", 3), ("y", 4)])

    def test_errors(self):
        for bad in ["x = 3 @ 4;", "x = 1; /* oops", "t12 = 1;"]:
            with self.assertRaises(CompileError, msg=bad):
                tokenize(bad)


class ParserTests(unittest.TestCase):
    def expr(self, text):
        return parse_source(f"x = {text};").stmts[0].value

    def test_precedence_and_assoc(self):
        e = self.expr("1 + 2 * 3")
        self.assertEqual((e.op, e.right.op), ("+", "*"))
        e = self.expr("8 - 3 - 2")
        self.assertEqual((e.op, e.left.op), ("-", "-"))

    def test_logic_precedence(self):
        e = self.expr("a < b || c < d && !e")
        self.assertEqual((e.op, e.right.op), ("||", "&&"))
        self.assertIsInstance(e.right.right, Unary)
        self.assertEqual(self.expr("a + 1 < b * 2").op, "<")
        self.assertEqual(self.expr("(1 + 2) * 3").op, "*")

    def test_syntax_errors(self):
        for bad in ["x = ;", "x = 1", "x = (1 + 2;", "if x { }", "else y = 1;", "{ x = 1;"]:
            with self.assertRaises(CompileError, msg=bad):
                parse_source(bad)


class GoldenTACTests(unittest.TestCase):
    def test_arithmetic(self):
        self.assertEqual(tac_lines("a=1; b=2; c=3; x = a + b * c;"),
                         ["a = 1", "b = 2", "c = 3", "t1 = b * c", "t2 = a + t1", "x = t2"])

    def test_copy_elimination(self):
        self.assertEqual(tac_lines("a=1; b=2; c=3; x = a + b * c;", optimize=True),
                         ["a = 1", "b = 2", "c = 3", "t1 = b * c", "x = a + t1"])

    def test_unary_and_value_mode(self):
        self.assertEqual(tac_lines("a=1; x = -a;")[-2:], ["t1 = - a", "x = t1"])
        self.assertEqual(tac_lines("a=1; b=2; x = a < b;", bool_mode="value")[-2:], ["t1 = a < b", "x = t1"])

    def test_if_and_short_circuit(self):
        self.assertEqual(tac_lines("a=1; b=2; if (a < b) { a = 5; }")[2:], ["if a >= b goto L1", "a = 5", "L1:"])
        self.assertEqual(tac_lines("a=1; b=2; if (a < 1 && b > 0) { a = 5; }")[2:],
                         ["if a >= 1 goto L1", "if b <= 0 goto L1", "a = 5", "L1:"])
        self.assertEqual(tac_lines("a=1; b=2; if (a < 1 || b > 0) { a = 5; }")[2:],
                         ["if a < 1 goto L1", "if b <= 0 goto L2", "L1:", "a = 5", "L2:"])

    def test_while_shape(self):
        self.assertEqual(tac_lines("i=0; while (i < 3) { i = i + 1; }"),
                         ["i = 0", "L1:", "if i >= 3 goto L2", "t1 = i + 1", "i = t1", "goto L1", "L2:"])

    def test_constant_folding(self):
        self.assertEqual(tac_lines("x = 2 + 3 * 4; f = 1 < 2 && !(3 > 4);", optimize=True), ["x = 14", "f = 1"])

    def test_triples(self):
        t = build_triples(compile_source("a=1; b=2; c=3; x = a + b * c;").code)
        self.assertEqual((t[3], t[4], t[5]), (("*", "b", "c"), ("+", "a", "(3)"), ("=", "x", "(4)")))

    def test_cfg_has_branch_and_join(self):
        code = compile_source("a=1; b=2; if (a < b) { a = 5; } print a;").code
        blocks = build_cfg(code)
        self.assertGreaterEqual(len(blocks), 3)
        self.assertTrue(any(len(block.successors) == 2 for block in blocks))
        self.assertTrue(any(not block.successors for block in blocks))

    def test_ssa_has_phi_and_dominator_tree(self):
        code = compile_source("a=1; b=2; if (a < b) { a=3; } print a;").code
        rendered = format_ssa(code)
        self.assertIn("phi", rendered)
        self.assertIn("Dominator tree:", rendered)
        self.assertIn("a#3 = phi", rendered)

    def test_ssa_handles_loop_carried_value(self):
        code = compile_source("i=0; while (i < 3) { i=i+1; } print i;").code
        program = build_ssa(code)
        self.assertTrue(any(block.phis.get("i") for block in program.blocks))
        self.assertEqual(run_tac(code)[1], ["3"])

    def test_ssa_does_not_change_executable_tac(self):
        code = compile_source("x_1=2; if (x_1 > 1) { x_1=x_1+3; } print x_1;").code
        before = run_tac(code)
        format_ssa(code)
        self.assertEqual(before, run_tac(code))


class SemanticTests(unittest.TestCase):
    def test_use_before_assignment(self):
        with self.assertRaises(CompileError) as cm:
            compile_source("x = y + 1;")
        self.assertEqual(cm.exception.phase, "Semantic")

    def test_division_by_zero(self):
        with self.assertRaises(CompileError):
            compile_source("x = 4 / (2 - 2);", optimize=True)
        with self.assertRaises(RuntimeFault):
            run_tac(compile_source("a = 0; x = 5 / a;").code)

    def test_symbol_types(self):
        res = compile_source("a = 1; b = 2.5; c = a < b; d = a + b;")
        self.assertEqual({k: v.type for k, v in res.symtab.items()},
                         {"a": "int", "b": "float", "c": "bool", "d": "float"})


class SemanticsPreservedTests(unittest.TestCase):
    def check(self, src):
        for opt, mode in CONFIGS:
            res = compile_source(src, optimize=opt, bool_mode=mode)
            env_a, out_a = run_ast(parse_source(src))
            env_t, out_t = run_tac(res.code)
            self.assertEqual(out_a, out_t, f"output differs (opt={opt}, mode={mode}) for {src}")
            self.assertEqual(env_a, env_t, f"env differs (opt={opt}, mode={mode}) for {src}")

    def test_examples(self):
        files = sorted(glob.glob(os.path.join(os.path.dirname(__file__), "..", "examples", "[0-9]*.src")))
        self.assertGreaterEqual(len(files), 6)
        for fn in files:
            with open(fn, encoding="utf-8") as handle:
                self.check(handle.read())

    def test_c_style_division(self):
        self.check("print 7 / 2; print -7 / 2; print 7 % 3; print -7 % 3; print 7.0 / 2;")

    def test_nested_control_flow(self):
        self.check("""i = 0; evens = 0; odds = 0;
            while (i < 20) {
                if (i % 2 == 0) { evens = evens + 1; } else { odds = odds + 1; }
                if (!(i < 5) && i != 7 || i == 2) { print i; }
                i = i + 1;
            }
            print evens; print odds;""")

    def test_random_expressions(self):
        rng = random.Random(2026)
        names = ["a", "b", "c"]

        def gen(d):
            if d == 0 or rng.random() < 0.2:
                return rng.choice(names + [str(rng.randint(0, 9)), "true", "false"])
            k = rng.random()
            if k < 0.12:
                return f"!({gen(d - 1)})"
            if k < 0.20:
                return f"-({gen(d - 1)})"
            op = rng.choice(["+", "-", "*", "<", "<=", ">", ">=", "==", "!=", "&&", "||", "/2", "%3"])
            if op in ("/2", "%3"):
                return f"(({gen(d - 1)}) {op[0]} {op[1]})"
            return f"({gen(d - 1)} {op} {gen(d - 1)})"

        for _ in range(300):
            e = gen(4)
            self.check(f"a = {rng.randint(-5, 5)}; b = {rng.randint(-5, 5)}; c = {rng.randint(-5, 5)};"
                       f" r = {e}; print r; if ({e}) {{ print 1; }} else {{ print 0; }}")

    def test_short_circuit_avoids_div_zero(self):
        res = compile_source("a = 0; if (a != 0 && 10 / a > 1) { print 1; } else { print 0; }")
        self.assertEqual(run_tac(res.code)[1], ["0"])


class CLITests(unittest.TestCase):
    def test_cli(self):
        from tacgen.__main__ import main
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = main(["-e", "a = 3; b = a * 2 + 1; print b;", "--run"])
        self.assertEqual(rc, 0)
        self.assertIn("PASS", buf.getvalue())

    def test_cli_ssa(self):
        from tacgen.__main__ import main
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = main(["-e", "a=1; b=2; if(a<b){a=3;} print a;", "--ssa"])
        self.assertEqual(rc, 0)
        self.assertIn("Static Single Assignment", buf.getvalue())
        self.assertIn("phi", buf.getvalue())


if __name__ == "__main__":
    unittest.main(verbosity=2)
