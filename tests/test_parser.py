"""
Tests for the ``clingo_funasp`` parser.

These tests document the FASP encoding produced by the parser. The removed
tree-sitter parser produced custom FASP nodes (``AssignmentRule``,
``HeadSimpleAssignment``, ...) while the ``clingo_funasp`` parser
(``clingo_funasp.ast.parse_string``/``parse_files``, accessed through the
``funasp.util.ast`` wrappers) desugars assignments at parse time into
standard clingo AST nodes:

- ``a := 1 :- b.`` becomes ``Fa(1) :- b.``: a ``StatementRule`` whose head is
  a ``HeadSimpleLiteral``. The assignment is marked by the ``F`` prefix on the
  symbol name and the assigned value appended as the last argument.
- ``{ a := 1 } :- b.`` becomes ``{ Fa(1) } :- b.`` with a ``HeadSetAggregate``
  head.
- ``a := #sum{ X: p(X) }.`` becomes ``Fa = #sum { X: NONE: p(X) }.`` with a
  ``HeadAggregate`` head whose left guard is ``Fa`` with relation ``Equal``.
- ``color(X) := #some{r;g;b}.`` becomes ``FScolor(X) = #sum { ... }`` (note
  the ``FS`` prefix for ``#some`` assignments).
- ``#showf p/1.`` becomes ``#show Fp/2. [true]`` (arity is incremented for
  the value slot).
"""

import os
import textwrap
import unittest

from clingo_funasp import ast

from funasp.ast import parse_files, parse_string
from funasp.core import Library
from funasp.util.ast import ParsingException


class TestParseAssignment2(unittest.TestCase):

    def setUp(self):
        """Set up test fixtures for each test."""
        self.messages = []
        self.lib = Library(logger=lambda t, msg: self.messages.append((t, msg)))

    def parse(self, code: str) -> list[ast.statements.Statement]:
        """Parse code with the new parser, dropping the leading `#program base.`."""
        statements = [s.original for s in parse_string(self.lib, code)]
        if statements and isinstance(statements[0], ast.statements.StatementProgram):
            statements = statements[1:]
        return statements

    def assertEqualParse(self, code: str, expected: str):
        """Assert that parsing yields the expected desugared statements."""
        rules = self.parse(code)
        for rule in rules:
            self.assertIsInstance(rule, ast.statements.Statement)
        lines = [sl for l in expected.strip().splitlines() if (sl := l.strip())]
        self.assertEqual(list(map(str, rules)), lines)

    def test_parse_simple_assignment(self):
        """Test parse simple assignment.

        Old: AssignmentRule with HeadSimpleAssignment head.
        New: StatementRule with HeadSimpleLiteral head; symbol name `Fa` and
        the value as last argument.
        """
        code = textwrap.dedent("""\
            a := 1.
            """)
        rules = self.parse(code)
        self.assertEqual(len(rules), 1)
        rule = rules[0]
        self.assertEqual(str(rule), "Fa(1).")
        self.assertIsInstance(rule, ast.statements.StatementRule)
        self.assertEqual(str(rule.head), "Fa(1)")
        self.assertIsInstance(rule.head, ast.head.HeadSimpleLiteral)
        literal = rule.head.literal
        self.assertIsInstance(literal, ast.literals.LiteralSymbolic)
        self.assertIsInstance(literal.atom, ast.terms.TermFunction)
        self.assertEqual(literal.atom.name, "Fa")
        self.assertEqual([str(arg) for arg in literal.atom.pool], ["1"])

    def test_parse_simple_assignments(self):
        """Test parse simple assignments."""
        code = textwrap.dedent("""\
            a := 1 :- b11; b12.
            b(X) := a+X :- b21(X); b22(X).
            """)
        rules = self.parse(code)
        self.assertEqual(len(rules), 2)
        rule = rules[0]
        self.assertEqual(str(rule), "Fa(1) :- b11; b12.")
        self.assertIsInstance(rule, ast.statements.StatementRule)
        self.assertEqual(str(rule.head), "Fa(1)")
        self.assertIsInstance(rule.head, ast.head.HeadSimpleLiteral)
        self.assertEqual(rule.head.literal.atom.name, "Fa")
        self.assertEqual([str(arg) for arg in rule.head.literal.atom.pool], ["1"])
        rule = rules[1]
        self.assertEqual(str(rule), "Fb(X,a+X) :- b21(X); b22(X).")
        self.assertIsInstance(rule, ast.statements.StatementRule)
        self.assertEqual(str(rule.head), "Fb(X,a+X)")
        self.assertIsInstance(rule.head, ast.head.HeadSimpleLiteral)
        self.assertEqual(rule.head.literal.atom.name, "Fb")
        # The original arguments come first, the assigned value is last.
        arguments = rule.head.literal.atom.pool[0].arguments
        self.assertEqual([str(arg) for arg in arguments], ["X", "a+X"])
        self.assertIsInstance(arguments[1], ast.terms.TermBinaryOperation)

    def test_parse_simple_assignments_with_clingo(self):
        """Test parse simple assignments mixed with plain clingo rules."""
        code = textwrap.dedent("""\
            p(X) :- q(X).
            a := 1 :- b11; b12.
            r(X) :- t(X).
            b(X) := a+X :- b21(X); b22(X).
            t(1).
            """)
        rules = self.parse(code)
        self.assertEqual(len(rules), 5)
        # The single parser preserves statement order (no merge step needed).
        self.assertEqual(
            list(map(str, rules)),
            [
                "p(X) :- q(X).",
                "Fa(1) :- b11; b12.",
                "r(X) :- t(X).",
                "Fb(X,a+X) :- b21(X); b22(X).",
                "t(1).",
            ],
        )
        self.assertTrue(all(isinstance(r, ast.statements.StatementRule) for r in rules))
        # Plain clingo rules are unchanged (no F prefix).
        for index, name in ((0, "p"), (2, "r"), (4, "t")):
            self.assertEqual(rules[index].head.literal.atom.name, name)
        # Assignment rules carry the F-prefixed head.
        for index, name in ((1, "Fa"), (3, "Fb")):
            self.assertEqual(rules[index].head.literal.atom.name, name)

    def test_parse_locations(self):
        """Test parse locations."""
        code = textwrap.dedent("""\
            a := 1 :- b11; b12.
            b(X) := a+X :- b21(X); b22(X).  c := 3.
            """)
        rules = self.parse(code)
        self.assertEqual(len(rules), 3)
        rule = rules[0]
        self.assertEqual(rule.location.begin.line, 1)
        self.assertEqual(rule.location.begin.column, 1)
        self.assertEqual(rule.location.end.line, 1)
        self.assertEqual(rule.location.end.column, 20)
        head_location = rule.head.literal.location
        self.assertEqual(head_location.begin.line, 1)
        self.assertEqual(head_location.begin.column, 1)
        self.assertEqual(head_location.end.line, 1)
        self.assertEqual(head_location.end.column, 10)

        rule = rules[1]
        self.assertEqual(rule.location.begin.line, 2)
        self.assertEqual(rule.location.begin.column, 1)
        self.assertEqual(rule.location.end.line, 2)
        self.assertEqual(rule.location.end.column, 31)
        head_location = rule.head.literal.location
        self.assertEqual(head_location.begin.line, 2)
        self.assertEqual(head_location.begin.column, 1)
        self.assertEqual(head_location.end.line, 2)
        self.assertEqual(head_location.end.column, 15)

        rule = rules[2]
        self.assertEqual(rule.location.begin.line, 2)
        self.assertEqual(rule.location.begin.column, 33)
        self.assertEqual(rule.location.end.line, 2)
        self.assertEqual(rule.location.end.column, 40)
        head_location = rule.head.literal.location
        self.assertEqual(head_location.begin.line, 2)
        self.assertEqual(head_location.begin.column, 33)
        self.assertEqual(head_location.end.line, 2)
        self.assertEqual(head_location.end.column, 40)

    def test_assignment_aggregate(self):
        """Test assignment aggregate.

        Old: HeadAssignmentAggregate head.
        New: HeadAggregate head with a left guard `Ff(args) = #fun { ... }`.
        """
        self.assertEqualParse(
            textwrap.dedent("""\
                a := #sum{X: p(X); Y,X: q(X,Y)} :- b.
                f(Y) := #count{X: p(X)} :- b(Y).
                """),
            textwrap.dedent("""\
                Fa = #sum { X: NONE: p(X); Y,X: NONE: q(X,Y) } :- b.
                Ff(Y) = #count { X: NONE: p(X) } :- b(Y).
                """),
        )
        rules = self.parse("a := #sum{X: p(X)} :- b.")
        rule = rules[0]
        self.assertIsInstance(rule, ast.statements.StatementRule)
        head = rule.head
        self.assertIsInstance(head, ast.head.HeadAggregate)
        self.assertIsInstance(head.left, ast.literals.LeftGuard)
        self.assertIsInstance(head.left.term, ast.terms.TermFunction)
        self.assertEqual(str(head.left.term), "Fa")
        self.assertEqual(head.left.relation, ast.literals.Relation.Equal)
        self.assertIsNone(head.right)
        self.assertEqual(head.function, ast.aggregates.AggregateFunction.Sum)

    def test_assignment_choice(self):
        """Test assignment choice.

        Old: ChoiceAssignment head.
        New: HeadSetAggregate head with F-prefixed element atoms.
        """
        self.assertEqualParse("{ a := 1 } :- b.", "{ Fa(1) } :- b.")
        self.assertEqualParse("{ a := 1; b := 2 } :- c.", "{ Fa(1); Fb(2) } :- c.")
        self.assertEqualParse("{ a := 1: p, q } :- c.", "{ Fa(1): p, q } :- c.")
        self.assertEqualParse(
            "{ a := 1: p, q; b(X) := f(X): r, not s } :- c(X).",
            "{ Fa(1): p, q; Fb(X,f(X)): r, not s } :- c(X).",
        )
        self.assertEqualParse(
            "{ a := 1: p, q; p(X): r, not s } :- c(X).",
            "{ Fa(1): p, q; p(X): r, not s } :- c(X).",
        )
        self.assertEqualParse("1 <= { a := 1 } :- b.", "1 <= { Fa(1) } :- b.")
        self.assertEqualParse("{ a := 1 } <= 2 :- b.", "{ Fa(1) } <= 2 :- b.")
        self.assertEqualParse("1 <= { a := 1 } <= 3 :- b.", "1 <= { Fa(1) } <= 3 :- b.")
        self.assertEqualParse("1{ a := 1 }3 :- b.", "1 <= { Fa(1) } <= 3 :- b.")
        self.assertEqualParse(
            "1 { a := 1: p, q; b(X) := f(X): r, not s } 5 :- c(X).",
            "1 <= { Fa(1): p, q; Fb(X,f(X)): r, not s } <= 5 :- c(X).",
        )
        rules = self.parse("{ a := 1 } :- b.")
        rule = rules[0]
        self.assertIsInstance(rule, ast.statements.StatementRule)
        self.assertIsInstance(rule.head, ast.head.HeadSetAggregate)
        elements = rule.head.elements
        self.assertEqual(len(elements), 1)
        self.assertIsInstance(elements[0], ast.aggregates.SetAggregateElement)
        self.assertEqual(str(elements[0]), "Fa(1)")

    def test_some_assignment(self):
        """Test #some assignment.

        Old: ChoiceSomeAssignment head.
        New: HeadAggregate head with the `FS` prefix (instead of `F`).
        """
        self.assertEqualParse(
            "color(X) := #some{r;g;b} :- country(X).",
            "FScolor(X) = #sum { r: NONE; g: NONE; b: NONE } :- country(X).",
        )
        rules = self.parse("color(X) := #some{r;g;b} :- country(X).")
        rule = rules[0]
        self.assertIsInstance(rule, ast.statements.StatementRule)
        head = rule.head
        self.assertIsInstance(head, ast.head.HeadAggregate)
        self.assertEqual(str(head.left.term), "FScolor(X)")
        self.assertEqual(head.left.relation, ast.literals.Relation.Equal)

    def test_parse_order(self):
        """Test that statement order is preserved for mixed programs.

        Replaces the old parser's merge test: the new parser handles both
        assignment and plain statements in a single pass.
        """
        self.assertEqualParse(
            textwrap.dedent("""\
                a := 1 :- b.
                a := 2 :- b.
                b.
                c.
                """),
            textwrap.dedent("""\
                Fa(1) :- b.
                Fa(2) :- b.
                b.
                c.
                """),
        )
        self.assertEqualParse(
            textwrap.dedent("""\
                b.
                c.
                a := 1 :- b.
                a := 2 :- b.
                """),
            textwrap.dedent("""\
                b.
                c.
                Fa(1) :- b.
                Fa(2) :- b.
                """),
        )

    def test_parse_error_clingo(self):
        """Test parse error in plain clingo code."""
        code = textwrap.dedent("""\
            a :- b.
            d
            d.
            d
            e :- f.
            """)
        with self.assertRaises(ParsingException) as cm:
            _ = self.parse(code)
        errors = cm.exception.errors
        self.assertEqual(len(errors), 2)
        self.assertEqual(len(self.lib.error_messages), 0)
        self.assertEqual(errors[0].location.begin.line, 3)
        self.assertEqual(errors[1].location.begin.line, 5)

    def test_parse_error_assignment_number(self):
        """Test parse error assigning to a number."""
        code = textwrap.dedent("""\
            1 := 2.
            """)
        with self.assertRaises(ParsingException) as cm:
            _ = self.parse(code)
        errors = cm.exception.errors
        self.assertEqual(len(errors), 1)
        self.assertEqual(len(self.lib.error_messages), 0)
        self.assertEqual(errors[0].location.begin.line, 1)

    def test_parse_error_assignment(self):
        """Test parse error in an assignment rule (missing dot).

        Old: the tree-sitter parser reported the error on line 1 with the
        joined statement text as message. New: clingo-style error on line 2
        where the unexpected token appears.
        """
        code = textwrap.dedent("""\
            a := 2 :- b
            c.
            """)
        with self.assertRaises(ParsingException) as cm:
            _ = self.parse(code)
        errors = cm.exception.errors
        self.assertEqual(len(errors), 1)
        self.assertEqual(len(self.lib.error_messages), 0)
        self.assertEqual(errors[0].location.begin.line, 2)

    def test_parse_head_aggregate_assignment(self):
        """Test parse head aggregate assignment.

        Old: HeadAggregateAssignment head with assignment elements.
        New: plain HeadAggregate; the element assignments become F-prefixed
        atoms with the value as last argument.
        """
        self.assertEqualParse(
            "1 <= #count{ f(X): f(X) := Y } <= 1.",
            "1 <= #count { f(X): Ff(X,Y) } <= 1.",
        )
        self.assertEqualParse(
            "1 <= #count{ f(X): f(X) := Y: p(X,Y) } <= 1.",
            "1 <= #count { f(X): Ff(X,Y): p(X,Y) } <= 1.",
        )
        self.assertEqualParse(
            "1 <= #count{ f(X,Y),g(X): f(X) := Y: p(X); p(X): p(X) } <= 1.",
            "1 <= #count { f(X,Y),g(X): Ff(X,Y): p(X); p(X): p(X) } <= 1.",
        )
        self.assertEqualParse(
            "#count{ f(X,Y),g(X): f(X) := Y; p(X): p(X) }.",
            "#count { f(X,Y),g(X): Ff(X,Y); p(X): p(X) }.",
        )
        self.assertEqualParse(
            "1 <= #count{ f(X,Y): f(X) := Y: p(X,Y), not in(X); p(X): p(X): p(Y) } <= 1.",
            "1 <= #count { f(X,Y): Ff(X,Y): p(X,Y), not in(X); p(X): p(X): p(Y) } <= 1.",
        )
        self.assertEqualParse(
            "#count{ 0,ass(king(C),X): king(C) := X: person(X) } :- country(C).",
            "#count { 0,ass(king(C),X): Fking(C,X): person(X) } :- country(C).",
        )

    def test_showf_directive_signature(self):
        """Test showf directive signature.

        Old: ShowFDirective node. New: StatementShowSignature with the `F`
        prefix and the arity incremented for the value slot.
        """
        rules = self.parse("""
                           #showf p/1.
                           """)
        self.assertEqual(len(rules), 1)
        rule = rules[0]
        self.assertIsInstance(rule, ast.statements.StatementShowSignature)
        self.assertEqual(str(rule), "#show Fp/2. [true]")
        self.assertEqual(rule.name, "Fp")
        self.assertEqual(rule.arity, 2)
        self.assertTrue(rule.value)
        self.assertFalse(rule.sign)

    def test_parse_files(self):
        """Test that parse_files yields the same statements as parse_string."""
        import tempfile

        code = textwrap.dedent("""\
            a := 1 :- b11; b12.
            b(X) := a+X :- b21(X); b22(X).
            """)
        with tempfile.NamedTemporaryFile("w", suffix=".lp", delete=False) as file:
            file.write(code)
            file.flush()
        file.close()
        statements = parse_files(self.lib, [file.name])
        os.unlink(file.name)
        expected = parse_string(self.lib, code)
        self.assertEqual(
            [str(s.original) for s in statements],
            [str(e.original) for e in expected],
        )

    def test_parse_files_error(self):
        """Test that parse_files raises ParsingException on syntax errors."""
        import tempfile

        with tempfile.NamedTemporaryFile("w", suffix=".lp", delete=False) as file:
            file.write("1 := 2.\n")
            file.flush()
        file.close
        with self.assertRaises(ParsingException) as cm:
            _ = parse_files(self.lib, [file.name])
        os.unlink(file.name)
        errors = cm.exception.errors
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].location.begin.line, 1)
        # clingo may relativize the path; compare the file name only.
        self.assertTrue(
            errors[0].location.begin.file.endswith(os.path.basename(file.name))
        )


if __name__ == "__main__":
    unittest.main()  # pragma: no cover
