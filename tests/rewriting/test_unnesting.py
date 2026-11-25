"""
Unit tests for ``funasp.ast._rewritings.unnesting`` paths that the integrated
pipeline cannot reach (negated body literals are converted to conditional
literals before unnesting runs there).
"""

import unittest

from clingo_funasp import ast, symbol
from clingo_funasp.core import Location, Position

from funasp.ast import RewriteContext, parse_string
from funasp.ast._rewritings.collectors import collect_variables
from funasp.ast._rewritings.literals import UnnestFunctionsInLiteralsTransformer
from funasp.ast._rewritings.types import SymbolSignature
from funasp.ast._rewritings.unnesting import unnest_statement
from funasp.core import Library
from funasp.util.ast import AST, FreshVariableGenerator


class TestUnnestStatement(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures for each test."""
        self.lib = Library()

    def unnest(self, code: str, intensional: set[str]) -> list[str]:
        """Parse a program and unnest each statement directly."""
        context = RewriteContext(
            self.lib,
            "F",
            intensional_functions={
                SymbolSignature(name, int(arity))
                for name, arity in (s.split("/") for s in intensional)
            },
        )
        statements = parse_string(self.lib, code)
        return [str(unnest_statement(context, s.original)) for s in statements[1:]]

    def test_negated_body_literal(self):
        """A negated body literal with an intensional function becomes conditional."""
        self.assertEqual(
            self.unnest("p(X) :- q(X); not r(f(X)).", {"f/1"}),
            ["p(X) :- q(X); #false: r(FUN), f(X)=FUN."],
        )

    def test_negated_body_literal_no_change(self):
        """A negated body literal without intensional functions is unchanged."""
        self.assertEqual(
            self.unnest("p(X) :- q(X); not r(X).", {"f/1"}),
            ["p(X) :- q(X); not r(X)."],
        )

    def test_unchanged_statements_are_identical(self):
        """Statements without intensional functions are returned as is."""
        context = RewriteContext(
            self.lib, "F", intensional_functions={SymbolSignature("f", 1)}
        )
        statements = parse_string(
            self.lib,
            """
            p(X) :- q(X).
            a :- #sum { X: q(X) } > 2.
            #sum { X: q(X) } > 2 :- a.
            { r(X): q(X) } :- a.
            #minimize { X: q(X) }.
            :~ q(X). [X]
            """,
        )
        for statement in statements[1:]:
            with self.subTest(statement=str(statement.original)):
                self.assertIs(
                    unnest_statement(context, statement.original), statement.original
                )

    def test_symbolic_function(self):
        """An intensional function nested in a symbolic term is unnested.

        The parser does not produce symbolic function terms, but
        programmatically constructed ASTs may contain them.
        """
        library = self.lib.library
        position = Position(library, "<test>", 1, 1)
        location = Location(position, position)
        inner = symbol.Function(library, "f", [symbol.Number(library, 1)])
        outer = symbol.Function(library, "g", [inner, symbol.Number(library, 2)])
        term = ast.terms.TermSymbolic(library, location, outer)
        transformer = UnnestFunctionsInLiteralsTransformer(
            library, {SymbolSignature("f", 1)}, FreshVariableGenerator()
        )
        unnested = transformer.unnest(term, False)
        self.assertEqual(str(unnested), "g(FUN,2)")
        self.assertEqual(
            [str(c) for c in transformer.pop_all_unnested_functions()],
            ["f(1)=FUN"],
        )

    def test_symbolic_nested_intensional(self):
        """Intensional functions nested inside another intensional symbolic term.

        Regression test: the inner replacement must be substituted into the
        comparison generated for the outer term, i.e. ``f(FUN)=FUN2`` and not
        ``f(f(1))=FUN2``.
        """
        library = self.lib.library
        position = Position(library, "<test>", 1, 1)
        location = Location(position, position)
        inner = symbol.Function(library, "f", [symbol.Number(library, 1)])
        middle = symbol.Function(library, "f", [inner])
        outer = symbol.Function(library, "g", [middle, symbol.Number(library, 2)])
        term = ast.terms.TermSymbolic(library, location, outer)
        transformer = UnnestFunctionsInLiteralsTransformer(
            library, {SymbolSignature("f", 1)}, FreshVariableGenerator()
        )
        unnested = transformer.unnest(term, False)
        self.assertEqual(str(unnested), "g(FUN2,2)")
        self.assertEqual(
            [str(c) for c in transformer.pop_all_unnested_functions()],
            ["f(1)=FUN", "f(FUN)=FUN2"],
        )

    def assertEqualUnnesting(
        self,
        node: AST,
        evaluable_functions: list[str],
        expected_node: AST | None,
        outer: bool = False,
        unnest_left_guard_equality: bool = False,
        expected_unnested_functions: list[str] | None = None,
    ):
        """Assert equal unnesting."""
        eval_sigs = {
            SymbolSignature(name, int(arity))
            for name, arity in (s.split("/") for s in evaluable_functions)
        }

        variableGenerator = FreshVariableGenerator(collect_variables(node))
        transformer = UnnestFunctionsInLiteralsTransformer(
            self.lib.library,
            eval_sigs,
            variableGenerator,
            unnest_left_guard_equality=unnest_left_guard_equality,
        )
        new_node = transformer.unnest(
            node,
            outer,
        )
        if expected_node is not None:
            self.assertIsNotNone(new_node)
            self.assertEqual(new_node, expected_node, f"{new_node} != {expected_node}")
        else:
            self.assertIsNone(new_node)
        if expected_unnested_functions is not None:
            self.assertEqual(
                [str(c) for c in transformer.pop_all_unnested_functions()],
                expected_unnested_functions,
            )

    def assertEqualUnnestingTerm(
        self,
        term_str: str,
        evaluable_functions: list[str],
        expected_term_str: str | None,
        outer: bool = False,
        expected_unnested_functions: list[str] | None = None,
    ):
        """Assert equal unnesting term."""
        term = ast.parse_term(self.lib.library, term_str)
        expected_term = (
            ast.parse_term(self.lib.library, expected_term_str)
            if expected_term_str is not None
            else None
        )
        self.assertEqualUnnesting(
            term,
            evaluable_functions,
            expected_term,
            outer,
            expected_unnested_functions=expected_unnested_functions,
        )

    def assertEqualUnnestingLiteral(
        self,
        literal_str: str,
        evaluable_functions: list[str],
        expected_literal_str: str | None,
        unnest_left_guard_equality: bool = False,
        expected_unnested_functions: list[str] | None = None,
    ):
        """Assert equal unnesting literal."""
        literal = ast.parse_literal(self.lib.library, literal_str)
        expected_literal = (
            ast.parse_literal(self.lib.library, expected_literal_str)
            if expected_literal_str is not None
            else None
        )
        self.assertEqualUnnesting(
            literal,
            evaluable_functions,
            expected_literal,
            outer=False,
            unnest_left_guard_equality=unnest_left_guard_equality,
            expected_unnested_functions=expected_unnested_functions,
        )

    def test_function(self):
        """Test function."""
        self.assertEqualUnnestingTerm("a", ["a/0"], "FUN")
        self.assertEqualUnnestingTerm("a", ["a/0"], None, outer=True)
        self.assertEqualUnnestingTerm("a", [], None)
        self.assertEqualUnnestingTerm("f(a)", ["f/1"], "FUN")
        self.assertEqualUnnestingTerm("f(a)", ["f/1"], None, outer=True)
        self.assertEqualUnnestingTerm("f(a)", [], None)

    def test_nested_function(self):
        """Test nested function."""
        self.assertEqualUnnestingTerm(
            "g(f(g(f(a))))",
            ["f/1"],
            "g(FUN2)",
            expected_unnested_functions=["f(a)=FUN", "f(g(FUN))=FUN2"],
        )

    def test_arithmetic(self):
        """Test nested function."""
        self.assertEqualUnnestingTerm("f(a) + g(f(a))", ["f/1"], "FUN+g(FUN2)")

    def test_symbolic_literal1(self):
        """Test symbolic literal1."""
        self.assertEqualUnnestingLiteral("a(a)", ["a/0"], "a(FUN)")
        self.assertEqualUnnestingLiteral("a(a)", ["a/0", "a/1"], "a(FUN)")

    def test_symbolic_literal_hamiltonian1(self):
        """Test symbolic literal hamiltonian1."""
        self.assertEqualUnnestingLiteral(
            "visited(next(start))",
            ["next/1", "start/0"],
            "visited(FUN2)",
            expected_unnested_functions=["start=FUN", "next(FUN)=FUN2" ],
        )

    def test_comparison_with_pool(self):
        """Test symbolic literal1."""
        self.assertEqualUnnestingLiteral("a(1;2,3) = a(4;5,6)", ["a/2"], "a(1;2,3) = FUN", expected_unnested_functions=["a(4;5,6)=FUN"])
