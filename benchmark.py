"""Small, reproducible benchmark and verification harness for the release.

Usage: ``python benchmark.py`` or ``python benchmark.py --repeat 20``.
It measures compilation plus TAC execution for every checked-in example in
both optimization modes and both Boolean modes, while also checking the VM
against the AST interpreter.
"""
import argparse
import glob
import os
import time

from tacgen import compile_source
from tacgen.parser import parse_source
from tacgen.runtime import run_ast, run_tac


def main(argv=None):
    parser = argparse.ArgumentParser(description="Benchmark and verify tacgen examples")
    parser.add_argument("--repeat", type=int, default=5, help="runs per configuration")
    args = parser.parse_args(argv)
    if args.repeat < 1:
        parser.error("--repeat must be positive")
    files = sorted(glob.glob(os.path.join(os.path.dirname(__file__), "examples", "[0-9]*.src")))
    total = 0
    failures = []
    print("example,optimize,bool_mode,mean_ms,verification")
    for filename in files:
        with open(filename, encoding="utf-8") as handle:
            source = handle.read()
        ref = run_ast(parse_source(source))
        for optimize in (False, True):
            for bool_mode in ("jump", "value"):
                elapsed = []
                result = "PASS"
                for _ in range(args.repeat):
                    start = time.perf_counter()
                    compiled = compile_source(source, optimize=optimize, bool_mode=bool_mode)
                    actual = run_tac(compiled.code)
                    elapsed.append((time.perf_counter() - start) * 1000)
                    if actual != ref:
                        result = "FAIL"
                mean = sum(elapsed) / len(elapsed)
                name = os.path.basename(filename)
                print(f"{name},{int(optimize)},{bool_mode},{mean:.3f},{result}")
                total += 1
                if result != "PASS":
                    failures.append(name)
    print(f"Configurations: {total}; failures: {len(failures)}; repeat: {args.repeat}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
