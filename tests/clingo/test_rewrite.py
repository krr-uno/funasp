from itertools import chain
import textwrap
import unittest

from clingo_funasp import ast
from clingo_funasp import core
from clingo_funasp.core import Library


class TestRewrite(unittest.TestCase):

    def setUp(self):
        """Set up test fixtures for each test."""
        self.library = Library()

    def assertEqualRewritten(
        self,
        program,
        expected,
        expected_head_types=None,
        prerewrite_expected_head_types=None,
    ):
        """
        Helper method to assert that the syntactic checker finds the expected errors.

        Args:
            program (str): The program to check.
            expected_errors (list): The list of expected SyntacticError instances.
        """
        rewrite_context = ast.RewriteContext(self.library)
        statements = []

        ast.parse_string(self.library, program, statements.append)

        if prerewrite_expected_head_types is not None:
            for i, (statement, expected_head_type) in enumerate(
                zip(statements[1:], prerewrite_expected_head_types)
            ):
                self.assertIsInstance(
                    statement, ast.statements.StatementRule, f"Statement {i} is not a rule"
                )
                self.assertIsInstance(
                    statement.head,
                    expected_head_type,
                    f"Head of statement {i} is not of expected type {expected_head_type}",
                )

        statements = list(
            chain.from_iterable(
                ast.rewrite_statement(rewrite_context, s) for s in statements
            )
        )

        self.assertCountEqual(
            set(map(lambda x: str(x).strip(), statements)),
            set(l2 for l in expected.splitlines() if (l2 := l.strip())),
        )
        if expected_head_types is not None:
            for statement, expected_head_type in zip(
                statements[1:], expected_head_types
            ):
                self.assertIsInstance(
                    statement, ast.statements.StatementRule, f"Statement {i} is not a rule"
                )
                self.assertIsInstance(
                    statement.head,
                    expected_head_type,
                    f"Head of statement {i} is not of expected type {expected_head_type}",
                )

    def test_comparisons(self):
        """Test comparisons."""
        program = """\
        X = Y :- X = Z, not Y = W, p(X, Y, Z, W).
        X != Y :- X != Z, not Y != W, p(X, Y, Z, W).
        X < Y :- X < Z, not Y < W, p(X, Y, Z, W).
        """
        expected = """\
        #program base.
        :- p(Z,Y,Z,W); Y!=W; Z!=Y.
        :- p(W,W,Z,W); W!=Z.
        :- p(X,Y,Z,W); X<Z; Y>=W; X>=Y.
        """
        self.maxDiff = None
        self.assertEqualRewritten(program, expected)

    def test_aggregates(self):
        """Test aggregates."""
        program = """\
        { p(X,Y) } :- q(X,Y).
        { p(X,Y) = Z } :- q(X,Y,Z).
        #count { X,Y: p(X,Y) } :- q(X,Y).
        #count { X,Y: p(X,Y): r(X,Y) } :- q(X,Y).
        #sum { X,Y: p(X,Y) } :- q(X,Y).
        #sum { X,Y: p(X,Y): r(X,Y) } :- q(X,Y).
        """
        expected = """\
        #program base.
        #count { 0,p(X,Y): p(X,Y) } :- q(X,Y).
        #count { 3,X,Y,Z: #true: Z=p(X,Y) } :- q(X,Y,Z).
        #count { X,Y: p(X,Y) } :- q(X,Y).
        #count { X,Y: p(X,Y): r(X,Y) } :- q(X,Y).
        #sum { X,Y: p(X,Y) } :- q(X,Y).
        #sum { X,Y: p(X,Y): r(X,Y) } :- q(X,Y).
        """
        prerewrite_expected_head_types = [
            ast.head.HeadSetAggregate,
            ast.head.HeadSetAggregate,
            ast.head.HeadAggregate,
            ast.head.HeadAggregate,
            ast.head.HeadAggregate,
            ast.head.HeadAggregate,
        ]
        expected_head_types = [
            ast.head.HeadAggregate,
            ast.head.HeadAggregate,
            ast.head.HeadAggregate,
            ast.head.HeadAggregate,
            ast.head.HeadAggregate,
            ast.head.HeadAggregate,
        ]
        self.maxDiff = None
        self.assertEqualRewritten(
            program, expected, expected_head_types, prerewrite_expected_head_types
        )

    def test_safety_1(self):
        """Test safety 1."""
        program = """\
        a(X) :- b.
        """
        errors = []
        library = Library(logger=lambda t, msg: errors.append((t, msg)))
        rewrite_context = ast.RewriteContext(library)
        statement = ast.parse_statement(library, program)
        self.assertIsInstance(statement, ast.statements.StatementRule)
        self.assertEqual(str(statement), "a(X) :- b.")
        with self.assertRaises(Exception):
            result = ast.rewrite_statement(rewrite_context, statement)
        self.assertEqual(len(errors), 1)
        self.assertEqual(
            errors[0],
            (
                core.MessageType.Error,
                textwrap.dedent("""\
            <string>:1:9-19: error: unsafe variables in:
              a(X) :- b.
            note: the following variables are unsafe:
              X"""),
            ),
        )

    def test_safety_2(self):
        """Test safety 2."""
        errors = []
        library = Library(logger=lambda t, msg: errors.append((t, msg)))
        rewrite_context = ast.RewriteContext(library)
        program = """\
        p(Y) :- b(X); 5*Y+7=X*X.
        """
        statement = ast.parse_statement(library, program)
        self.assertIsInstance(statement, ast.statements.StatementRule)
        self.assertEqual(str(statement).strip(), "p(Y) :- b(X); 5*Y+7=X*X.")
        result = ast.rewrite_statement(rewrite_context, statement)
        self.assertEqual(str(result[0]).strip(), "p(Y) :- b(X); 5*Y+7=X*X.")
        program = """\
        p(Y) :- b(X); 0*Y+7=X*X.
        """
        statement = ast.parse_statement(library, program)
        self.assertIsInstance(statement, ast.statements.StatementRule)
        self.assertEqual(str(statement).strip(), "p(Y) :- b(X); 0*Y+7=X*X.")
        self.assertEqual(len(errors), 0)
        with self.assertRaises(Exception):
            ast.rewrite_statement(rewrite_context, statement)
        self.assertEqual(len(errors), 1)
        self.assertEqual(
            errors[0],
            (
                core.MessageType.Error,
                textwrap.dedent("""\
            <string>:1:9-33: error: unsafe variables in:
              p(Y) :- b(X); 0*Y+7=X*X.
            note: the following variables are unsafe:
              Y"""),
            ),
        )

    def test_pool_1(self):
        """Test pool 1."""
        program = """\
        p(X;Y,Z) :- q(X,Y,Z).
        """
        expected = """\
        #program base.
        p(X) :- q(X,Y,Z).
        p(Y,Z) :- q(X,Y,Z).
        """
        self.maxDiff = None
        self.assertEqualRewritten(program, expected)

    def test_pool_2(self):
        """Test pool 2."""
        program = """\
        p(X;(Y,Z)) :- q(X,Y,Z).
        """
        expected = """\
        #program base.
        p(X) :- q(X,Y,Z).
        p((Y,Z)) :- q(X,Y,Z).
        """
        self.maxDiff = None
        self.assertEqualRewritten(program, expected)

    def test_unary_operator(self):
        """Test unary operator."""
        program = """\
        p(--X) :- q(X).
        """
        expected = """\
        #program base.
        p(-(-X)) :- q(X).
        """
        self.maxDiff = None
        self.assertEqualRewritten(program, expected)

    def test_arithmetic_1(self):
        """Test arithmetic 1."""
        program = """\
        p(X) :- q(X).
        p(X+Y) :- q(X,Y).
        p(X-Y) :- q(X,Y).
        p(X*Y) :- q(X,Y).
        p(X/Y) :- q(X,Y).
        p(2*X+Y) :- q(X,Y).
        p(2*(X+Y)) :- q(X,Y).
        """
        expected = """\
        #program base.
        p(X) :- q(X).
        p(X+Y) :- q(X,Y).
        p(X-Y) :- q(X,Y).
        p(X*Y) :- q(X,Y).
        p(X/Y) :- q(X,Y).
        p(2*X+Y) :- q(X,Y).
        p(2*(X+Y)) :- q(X,Y).
        """
        self.maxDiff = None
        self.assertEqualRewritten(program, expected)

    def test_arithmetic_2(self):
        """Test arithmetic 2."""
        program = """\
        p(X) :- q(X).
        p(Z) :- q(X,Y); Z=X+Y.
        p(Z) :- q(X,Y); Z=X-Y.
        p(Z) :- q(X,Y); Z=X*Y.
        p(Z) :- q(X,Y); Z=X/Y.
        p(Z) :- q(X,Y); Z=2*X+Y.
        p(Z) :- q(X,Y); Z=2*(X+Y).
        """
        expected = """\
        #program base.
        p(X) :- q(X).
        p(Z) :- q(X,Y); Z=X+Y.
        p(Z) :- q(X,Y); Z=X-Y.
        p(Z) :- q(X,Y); Z=X*Y.
        p(Z) :- q(X,Y); Z=X/Y.
        p(Z) :- q(X,Y); Z=2*X+Y.
        p(Z) :- q(X,Y); Z=2*(X+Y).
        """
        self.maxDiff = None
        self.assertEqualRewritten(program, expected)

    def test_arithmetic_3(self):
        """Test arithmetic 3."""
        program = """\
        :- q1(X,Y,Z); W=3*X+5*Y+Z.
        :- q2(X,Y,Z); W=X+Y+Z.
        :- q3(X,Y); W+5=X+Y+5.
        :- q4(X,Y); W+5=X+5+Y.
        :- q5(X,Y,Z); W+5=X+Y+5+Z.
        """
        expected = """\
        #program base.
        :- q1(X,Y,Z); W=3*X+5*Y+Z.
        :- q2(X,Y,Z); W=X+Y+Z.
        :- q3(X,Y); 1*W+5=X+Y+5.
        :- q4(X,Y); 1*W+5=X+(Y+5).
        :- q5(X,Y,Z); 1*W+5=X+Y+5+Z.
        """
        self.maxDiff = None
        self.assertEqualRewritten(program, expected)

    def test_intervals(self):
        """Test intervals."""
        program = """\
        p1(X) :- q1(X, 1..3).
        p2(X..Y) :- q2(X, Y).
        p3(X) :- q3(X,Y, X..Y).
        p4(2*(X..Y)) :- q4(X, Y).
        """
        expected = """\
        #program base.
        p1(X) :- q1(X,1*__A_0+0); __A_0=1..3.
        p2(__A_1) :- q2(X,Y); __A_1=X..Y.
        p3(X) :- q3(X,Y,1*__A_2+0); __A_2=X..Y.
        p4(2*__A_3+0) :- q4(X,Y); __A_3=X..Y.
        """
        self.maxDiff = None
        self.assertEqualRewritten(program, expected)
