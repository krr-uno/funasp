"""
Tests for ``funasp.ast.ast_to_str``: rendering as-parsed
(F-encoded) statements back in FASP syntax for error messages.
"""

import unittest

from clingo_funasp import ast
from clingo_funasp.core import Location, Position

from funasp.ast import parse_string
from funasp.ast._core import _ast_to_str
from funasp.core import Library


class TestAstToStr(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures for each test."""
        self.lib = Library()

    def assertRoundTrip(self, program: str, expected: str | None = None):
        """Assert that parsing then printing yields the program back."""
        if expected is None:
            expected = program
        statements = [
            statement.original
            for statement in parse_string(self.lib, program)
            if not isinstance(statement.original, ast.statements.StatementProgram)
        ]
        self.assertEqual(len(statements), 1)
        self.assertEqual(_ast_to_str(statements[0]), expected)

    def test_simple_assignments(self):
        """Simple assignments round-trip."""
        self.assertRoundTrip("a := 1.")
        self.assertRoundTrip("f(1,2) := 3 :- b11; b12.")
        self.assertRoundTrip("b(X) := a+X :- b21(X); b22(X).")

    def test_choice_assignments(self):
        """Choice assignments round-trip, with guards normalized."""
        self.assertRoundTrip("{ a := 1 } :- b.")
        self.assertRoundTrip("{ a := 1: p, q; b(X) := f(X): r, not s } :- c(X).")
        self.assertRoundTrip("1 <= { a := 1 } <= 3 :- b.")
        self.assertRoundTrip("{ a := 1 } = 2.")
        self.assertRoundTrip("1{ a := 1 }3 :- b.", "1 <= { a := 1 } <= 3 :- b.")

    def test_aggregate_assignments(self):
        """Aggregate assignments round-trip for all aggregate functions."""
        self.assertRoundTrip("a := #sum{X: p(X); Y,X: q(X,Y)} :- b.")
        self.assertRoundTrip("f(Y) := #count{X: p(X)} :- b(Y).")
        self.assertRoundTrip("f(Y) := #min{X: p(X)}.")
        self.assertRoundTrip("f(Y) := #max{X: p(X)}.")

    def test_some_assignments(self):
        """#some assignments round-trip."""
        self.assertRoundTrip("color(X) := #some{r; g; b} :- country(X).")
        self.assertRoundTrip("a := #some{X: p(X)} :- b.")
        self.assertRoundTrip("a := #some{X,Y: p(X,Y)}.")

    def test_head_aggregate_assignments(self):
        """Assignments embedded in head aggregates round-trip."""
        self.assertRoundTrip(
            "#count{ 0,ass(king(C),X): king(C) := X: person(X) } :- country(C)."
        )
        self.assertRoundTrip("1 <= #count{ f(X): f(X) := Y: p(X,Y) } <= 1.")

    def test_showf(self):
        """#showf directives round-trip; plain #show statements do not change."""
        self.assertRoundTrip("#showf p/1.")
        self.assertRoundTrip("#show q/1.", "#show q/1. [true]")

    def test_pass_through(self):
        """Statements without assignment encodings are printed as-is."""
        self.assertRoundTrip("p(X) :- q(X).")
        self.assertRoundTrip(":- p(X); q(X).", " :- p(X); q(X).")
        self.assertRoundTrip("a | b :- c.", "a; b :- c.")
        self.assertRoundTrip("% comment")
        self.assertRoundTrip("#count{ X: p(X): q(X) }.", "#count { X: p(X): q(X) }.")
        self.assertRoundTrip("{ p(X): q(X) }.", "{ p(X): q(X) }.")

    def test_pooled_assignment2(self):
        """A pooled head atom with a common value prints as a pooled assignment.

        This is the form the parser produces for ``f(1;2) := 3.``.
        """
        self.assertRoundTrip("f(1;2) := 3.", "f(1;2) := 3.")
        self.assertRoundTrip("f(a;b) := #some{r; g}.", "f(a;b) := #some{r; g}.")

    def _pooled_atom(self, values: list[int]) -> ast.statements.Statement:
        """Build the statement ``Ff(1,v1;2,v2).`` with a pooled head atom."""
        library = self.lib.library
        position = Position(library, "<test>", 1, 1)
        location = Location(position, position)

        def number(value: int) -> ast.terms.TermSymbolic:
            from clingo_funasp.symbol import Number

            return ast.terms.TermSymbolic(library, location, Number(library, value))

        pool = [
            ast.terms.ArgumentTuple(library, [number(argument), number(value)])
            for argument, value in zip((1, 2), values)
        ]
        atom = ast.terms.TermFunction(library, location, "Ff", pool)
        literal = ast.literals.LiteralSymbolic(library, location, ast.literals.Sign.NoSign, atom)
        return ast.statements.StatementRule(
            library, location, ast.head.HeadSimpleLiteral(library, literal), []
        )

    def test_pooled_assignment(self):
        """A pooled head atom with a common value prints as a pooled assignment.

        This is the form the parser produces for ``f(1;2) := 3.``.
        """
        statement = self._pooled_atom([3, 3])
        self.assertEqual(_ast_to_str(statement), "f(1;2) := 3.")

    def test_pooled_assignment_differing_values(self):
        """A pooled atom with differing values cannot come from source: as-is."""
        statement = self._pooled_atom([3, 4])
        self.assertEqual(_ast_to_str(statement), "Ff(1,3;2,4).")
