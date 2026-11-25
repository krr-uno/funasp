from itertools import chain
import unittest

from clingo_funasp import ast
from clingo_funasp.core import Location, Position, Library
from clingo_funasp.symbol import Symbol, SymbolType, parse_term, parse_term

from funasp import core
from funasp.ast import parse_string
from funasp.util.ast import (
    ParsingException,
    SyntacticCheckVisitor,
    SyntacticError,
)
from funasp.ast._rewritings.collectors import collect_variables
from funasp.util import ast as util_ast

INVALID_ASTTYPES = {
    ast.head.HeadSetAggregate,
    ast.body.BodyConditionalLiteral,
    ast.head.HeadDisjunction,
}

LOC = Location(Position(Library(), "<test>", 1, 1), Position(Library(), "<test>", 1, 1))


def parse_symbolic_term(lib, term_str):
    """Parse a symbolic term from a string."""
    term = parse_term(lib, term_str)
    return ast.terms.TermSymbolic(lib, LOC, term)


class TestSyntacticChecker(unittest.TestCase):
    """
    Test class for the syntactic checker.
    """

    def setUp(self):
        """Set up test fixtures for each test."""
        self.lib = Library()

    def assertEqualErrors(self, program, expected_errors):
        """
        Helper method to assert that the syntactic checker finds the expected errors.

        Args:
            program (str): The program to check.
            expected_errors (list): The list of expected SyntacticError instances.
        """

        syntactic_checker = SyntacticCheckVisitor(INVALID_ASTTYPES)

        def callback(statement):
            """Handle callback output for the current test."""
            statement.visit(syntactic_checker)

        ast.parse_string(self.lib, program, callback)
        self.assertCountEqual(syntactic_checker.errors, expected_errors)

    def test_correct(self):
        """Test syntax checking with a correct program snippet."""
        program = """
            #program actions.
            a :- b.
            b :- not c.
            c :- c.
            f = 1 :- g = h.
            f = 1 :- not g = h.
        """
        self.assertEqualErrors(program, [])

    def test_incorrect(self):
        """Test syntax checking with an incorrect program snippet."""
        program = """
            #program actions.
            a :- b : c.
            a, c :- b.
            {b} :- not c.
            c :- c.
            f = 1 :- g = h.
            f = 1 :- not g = h.
        """
        expected_errors = [
            SyntacticError(
                Location(
                    Position(self.lib, "<string>", 3, 18),
                    Position(self.lib, "<string>", 3, 24),
                ),
                "unexpected b: c",
                ast.body.BodyConditionalLiteral,
            ),
            SyntacticError(
                Location(
                    Position(self.lib, "<string>", 4, 13),
                    Position(self.lib, "<string>", 4, 20),
                ),
                "unexpected a; c",
                ast.head.HeadDisjunction,
            ),
            SyntacticError(
                Location(
                    Position(self.lib, "<string>", 5, 13),
                    Position(self.lib, "<string>", 5, 16),
                ),
                "unexpected { b }",
                ast.head.HeadSetAggregate,
            ),
        ]
        self.maxDiff = None
        self.assertEqualErrors(program, expected_errors)


class TestVariableManager(unittest.TestCase):
    """Tests VariableCollector and FreshVariableGenerator."""

    def setUp(self):
        """Set up test fixtures for each test."""
        self.lib = Library()
        self.loc = Location(
            Position(self.lib, "<stdin>", 1, 1),
            Position(self.lib, "<stdin>", 1, 1),
        )
        self.ast = ast

    def parse_program(self, program: str):
        """Parse program."""
        stmts = []
        self.ast.parse_string(self.lib, program, stmts.append)
        return stmts

    # VariableCollector tests

    # FreshVariableGenerator tests

    def test_fresh_variable_simple_and_numbered(self):
        """Test fresh variable simple and numbered."""
        gen = util_ast.FreshVariableGenerator({"X"})
        v1 = gen.fresh_variable(self.lib, self.loc, name="X")
        v2 = gen.fresh_variable(self.lib, self.loc, name="X")
        v3 = gen.fresh_variable(self.lib, self.loc, name="Z")

        self.assertEqual(v1.name, "X2")
        self.assertEqual(v2.name, "X3")
        self.assertEqual(v3.name, "Z")

    def test_fresh_variable_with_empty_used(self):
        """Test fresh variable with empty used."""
        gen = util_ast.FreshVariableGenerator()
        v = gen.fresh_variable(self.lib, self.loc, name="Y")
        self.assertEqual(v.name, "Y")

    def test_generator_isolated_instances(self):
        """Test generator isolated instances."""
        gen1 = util_ast.FreshVariableGenerator({"X"})
        gen2 = util_ast.FreshVariableGenerator({"Y"})

        v1 = gen1.fresh_variable(self.lib, self.loc, "X")
        v2 = gen2.fresh_variable(self.lib, self.loc, "Y")

        self.assertTrue(v1.name.startswith("X2"))
        self.assertTrue(v2.name.startswith("Y2"))

    # VariableCollector and FreshVariableGenerator integration tests

    def test_pipeline_basic_program(self):
        """Collector should feed into generator with proper fresh variables."""
        stmts = self.parse_program("p(X,Y). q(Z).")
        used = set(chain.from_iterable(collect_variables(stmt) for stmt in stmts))
        self.assertEqual(used, {"X", "Y", "Z"})

        gen = util_ast.FreshVariableGenerator(used)
        v1 = gen.fresh_variable(self.lib, self.loc, "X")
        v2 = gen.fresh_variable(self.lib, self.loc, "Y")
        v3 = gen.fresh_variable(self.lib, self.loc, "W")

        self.assertEqual(v1.name, "X2")
        self.assertEqual(v2.name, "Y2")
        self.assertEqual(v3.name, "W")

    def test_pipeline_multiple_rules(self):
        """Variables across multiple rules should all be collected and respected."""
        stmts = self.parse_program("p(A). q(B,C). r(D,E,F).")
        used = set(chain.from_iterable(collect_variables(stmt) for stmt in stmts))
        self.assertEqual(used, {"A", "B", "C", "D", "E", "F"})

        gen = util_ast.FreshVariableGenerator(used)
        v1 = gen.fresh_variable(self.lib, self.loc, "A")
        v2 = gen.fresh_variable(self.lib, self.loc, "C")
        v3 = gen.fresh_variable(self.lib, self.loc, "G")

        self.assertEqual(v1.name, "A2")
        self.assertEqual(v2.name, "C2")
        self.assertEqual(v3.name, "G")


class TestParseString(unittest.TestCase):
    """Tests for funasp.ast.parse_string."""

    def setUp(self):
        """Set up test fixtures for each test."""
        self.lib = core.Library()

    def assertCorrectParsing(self, program):
        """Assert correct parsing."""
        statements = [s.original for s in parse_string(self.lib, program)]
        statements = statements[1:]
        lines = program.strip().splitlines()
        lines = [sl for line in lines if (sl := line.strip())]
        self.assertEqual(list(map(str, statements)), lines)
        for stmt in statements:
            self.assertIsInstance(stmt, ast.statements.StatementRule)

    def test_parse_string_correct(self):
        """Test parse string correct."""
        self.assertCorrectParsing("""
            a :- b.
            b :- not c.
            c :- c.
            f=1 :- g=h.
            f=1 :- not g=h.
        """)

    def assertParsingException(self, program, expected_errors):
        """Assert parsing exception."""
        with self.assertRaises(ParsingException) as cm:
            parse_string(self.lib, program)
        self.assertEqual(cm.exception.errors, expected_errors)

    def test_parse_string_errors(self):
        """Test parse string errors."""
        self.assertParsingException(
            """\
            a :- b.
            c
            d.
            """,
            [
                SyntacticError(
                    location=Location(
                        Position(self.lib.library, "string", 3, 13),
                        Position(self.lib.library, "string", 3, 14),
                    ),
                    message="expected one of ':-' '.' but got <identifier>",
                    information=None,
                )
            ],
        )

        self.assertParsingException(
            """\
            a :- b.
            c d.
            """,
            [
                SyntacticError(
                    location=Location(
                        Position(self.lib.library, "string", 2, 15),
                        Position(self.lib.library, "string", 2, 16),
                    ),
                    message="expected one of ':-' '.' but got <identifier>",
                    information=None,
                )
            ],
        )

        self.assertParsingException(
            """\
            a :- b.
            c d.
            e
            f.
            """,
            [
                SyntacticError(
                    location=Location(
                        Position(self.lib.library, "string", 2, 15),
                        Position(self.lib.library, "string", 2, 16),
                    ),
                    message="expected one of ':-' '.' but got <identifier>",
                    information=None,
                ),
                SyntacticError(
                    location=Location(
                        Position(self.lib.library, "string", 4, 13),
                        Position(self.lib.library, "string", 4, 14),
                    ),
                    message="expected one of ':-' '.' but got <identifier>",
                    information=None,
                ),
            ],
        )


class TestFunctionArguments(unittest.TestCase):
    """Tests for the function_arguments helper."""

    def setUp(self):
        """Set up test fixtures for each test."""
        self.lib = Library()

    def test_term_tuple(self):
        """A term tuple has an empty name and its arguments."""
        position = Position(self.lib, "<test>", 1, 1)
        location = Location(position, position)
        terms = [
            ast.terms.TermVariable(self.lib, location, "X"),
            ast.terms.TermVariable(self.lib, location, "Y"),
        ]
        tuple_term = ast.terms.TermTuple(
            self.lib, location, [ast.terms.ArgumentTuple(self.lib, terms)]
        )
        name, arguments = util_ast.function_arguments(tuple_term)
        self.assertEqual(name, "")
        self.assertEqual([str(a) for a in arguments], ["X", "Y"])


class TestSymbolSignature(unittest.TestCase):
    """Tests for the SymbolSignature type."""

    def test_str(self):
        """The string form is name/arity."""
        from funasp.ast._rewritings.types import SymbolSignature

        self.assertEqual(str(SymbolSignature("f", 2)), "f/2")


class TestTermTransformer(unittest.TestCase):
    """Tests for the TermTransformer class."""

    def setUp(self):
        """Set up test fixtures for each test."""
        self.lib = Library()

    def assertTransformed(self, term, expected_str, function):
        """Assert that the term is transformed correctly."""
        transformer = util_ast.TermTransformer(self.lib, function)
        transformed_term = transformer(term)
        if expected_str is None:
            self.assertIsNone(transformed_term)
        else:
            self.assertEqual(str(transformed_term), expected_str)

    def test_transform_order(self):
        """Test that the transformation is applied in the correct order."""
        names = []

        def function(term, depth, loc, fun):
            # print(f"Visiting term: {term} --- {type(term)} --- {term.type if isinstance(term, Symbol) else 'N/A'}")
            if isinstance(term, ast.terms.TermFunction):
                names.append(("F" + term.name, depth))
            elif isinstance(term, Symbol) and term.type == SymbolType.Function:
                names.append(("S" + term.name, depth))
            return None

        self.assertTransformed(
            ast.parse_term(self.lib, "a(b(c(X),d(Y)),e(Z))"), None, function
        )
        self.assertEqual(names, [("Fa", 0), ("Fb", 1), ("Fc", 2), ("Fd", 2), ("Fe", 1)])

        names = []
        self.assertTransformed(
            parse_symbolic_term(self.lib, "a(b(c,d),e)"), None, function
        )
        self.assertEqual(names, [("Sa", 0), ("Sb", 1), ("Sc", 2), ("Sd", 2), ("Se", 1)])

    def test_replacement(self):
        """Test that the transformation can replace terms."""
        traversed_terms = []

        def function(term, depth, loc, fun):
            # print(f"Visiting term: {term} --- {type(term)} --- {term.type if isinstance(term, Symbol) else 'N/A'}")
            traversed_terms.append(term)
            if isinstance(term, ast.terms.TermFunction) and term.name == "b":
                return ast.terms.TermFunction(self.lib, term.location, "x", term.pool)
            if (
                isinstance(term, Symbol)
                and term.type == SymbolType.Function
                and term.name == "b"
            ):
                return ast.terms.TermFunction(self.lib, LOC, "x", [])
            return None

        self.assertTransformed(
            ast.parse_term(self.lib, "a(b(c,d),e)"), "a(x(c,d),e)", function
        )
        self.assertEqual(
            [str(t) for t in traversed_terms], ["a(b(c,d),e)", "b(c,d)", "e"]
        )

        traversed_terms = []
        self.assertTransformed(
            parse_symbolic_term(self.lib, "a(b(c,d),e)"), "a(x(),e)", function
        )
        self.assertEqual(
            [str(t) for t in traversed_terms], ["a(b(c,d),e)", "b(c,d)", "e"]
        )


        traversed_terms = []
        self.assertTransformed(
            parse_symbolic_term(self.lib, "a(b(c(d(b))))"), "a(x())", function
        )
        self.assertEqual(
            [str(t) for t in traversed_terms], ['a(b(c(d(b))))', 'b(c(d(b)))']
        )


    def test_replacement_recursive(self):

        traversed_terms = []

        def function(term, depth, loc, fun):
            traversed_terms.append((str(term), depth))
            if isinstance(term, ast.terms.TermFunction) and term.name == "b":
                fun(term, depth + 1)
                return ast.terms.TermFunction(self.lib, term.location, "x", term.pool)
            if isinstance(term, Symbol):
                if (term.type == SymbolType.Function and term.name == "b"):
                    fun(ast.terms.TermSymbolic(self.lib, LOC, term), depth + 1)
                    return ast.terms.TermFunction(self.lib, LOC, "x", [])
                if (term.type != SymbolType.Function):
                    fun(ast.terms.TermSymbolic(self.lib, LOC, term), depth + 1)
                    return ast.terms.TermFunction(self.lib, LOC, "y", [])
            return None

        self.assertTransformed(
            parse_symbolic_term(self.lib, "a(b(c(d(b))))"), "a(x())", function
        )
        self.assertEqual(
            traversed_terms, [('a(b(c(d(b))))', 0), ('b(c(d(b)))', 1), ('c(d(b))', 2), ('d(b)', 3), ('b', 4)]
        )

        traversed_terms = []
        self.assertTransformed(
            parse_symbolic_term(self.lib, "a(b(1))"), "a(x())", function
        )
        self.assertEqual(
            traversed_terms, [('a(b(1))', 0), ('b(1)', 1), ('1', 2)]
        )



class TestReplaceTerm(unittest.TestCase):
    """Tests for the TermTransformer class."""

    def setUp(self):
        """Set up test fixtures for each test."""
        self.lib = Library()
        self.var_gen = util_ast.FreshVariableGenerator()

    def assertTransformed(self, term, expected_str, function, expected_comparisons=None):
        """Assert that the term is transformed correctly."""
        comparisons = []
        transformed_term = util_ast.replace_term(self.lib, term, function, comparisons.append, self.var_gen, ast.literals.Sign.NoSign)
        if expected_str is None:
            self.assertIsNone(transformed_term)
        else:
            self.assertEqual(str(transformed_term), expected_str)

        if expected_comparisons is not None:
            self.assertEqual(list(map(str, comparisons)), expected_comparisons)

    def condition1(self, term, depth):
        """Condition to check if the term is a function named 'b'."""
        return isinstance(term, ast.terms.TermFunction) and term.name == "b"


    def test_replace_term(self):
        """Test that the transformation can replace terms."""
        self.assertTransformed(ast.parse_term(self.lib, "a(b(X,d),e)"), "a(FUN,e)", self.condition1, ["b(X,d)=FUN"])

    def test_replace_term_recursive(self):
        self.assertTransformed(ast.parse_term(self.lib, "a(b(d(b(X))),e)"), "a(FUN2,e)", self.condition1, ['b(X)=FUN', 'b(d(FUN))=FUN2'])

    def condition2(self, term, depth):
        """Condition matching a function named 'b', whether AST or symbolic."""
        if isinstance(term, ast.terms.TermFunction):
            return term.name == "b"
        return (
            isinstance(term, Symbol)
            and term.type == SymbolType.Function
            and term.name == "b"
        )

    def test_replace_term_symbolic_recursive(self):
        """Nested matches inside a symbolic term must be substituted, not dropped."""
        self.assertTransformed(
            parse_symbolic_term(self.lib, "a(b(d(b(c))),e)"),
            "a(FUN2,e)",
            self.condition2,
            ["b(c)=FUN", "b(d(FUN))=FUN2"],
        )


