"""
Integration tests for the rewriting pipeline (``funasp.ast._rewritings``) over
the ``clingo_funasp`` parser, mirroring the old pipeline tests in
``tests/syntax_tree/rewriting/test_integration.py``.
"""

import io
import sys
import textwrap
import unittest
from contextlib import redirect_stderr

from clingo_funasp import ast

from funasp.ast import RewriteContext, parse_string, rewrite_statements
from funasp.core import Library
from funasp.util.ast import RewritingException
from funasp.util.types import SymbolSignature
from tests.restore_anonymous_term_variables import restore_anonymous_term_variables


class TestRewriteStatements(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures for each test."""
        self.elib = Library(logger=lambda t, m: print(m, file=sys.stderr))
        self.maxDiff = None  # Show full diff on assertion failure

    def assertTransformEqual(
        self,
        program: str,
        expected_program: str | None,
        *,
        intensional_functions: set[str] | None = None,
        prefix: str = "F",
    ):
        """Assert transform equal."""
        if intensional_functions is None:
            intensional_functions = set()

        intensional_functions = {
            SymbolSignature(name, int(arity))
            for name, arity in (s.split("/") for s in intensional_functions)
        }

        context = RewriteContext(
            self.elib, prefix, intensional_functions=intensional_functions
        )

        program = textwrap.dedent(program).strip()
        expected_program = (
            textwrap.dedent(expected_program).strip()
            if expected_program is not None
            else None
        )

        statement_asts = parse_string(self.elib, program)
        transformed = [
            restore_anonymous_term_variables(context, statement)
            for wrapper in rewrite_statements(context, statement_asts)
            for statement in wrapper.rewritten
        ]

        transformed_str = "\n".join(
            str(statement).strip()
            for statement in transformed
            if not isinstance(statement, ast.StatementProgram | ast.StatementComment)
        )
        self.assertEqual(transformed_str, expected_program)

    def test_to_asp(self):
        """Test to asp."""
        self.assertTransformEqual(
            "f(1) := Y :- g(Y).",
            """
            Ff(1,Y) :- g(Y).
            :- Ff(X0,_); 1 < #count { V: Ff(X0,V) }.
            """,
        )

    def test_total_integration(self):
        """Test total integration."""
        self.assertTransformEqual(
            "1 { sk(X, Y)  : skis(Y) } 1 :- sks(X).",
            "1 <= #count { 0,sk(X,Y): sk(X,Y): skis(Y) } <= 1 :- sks(X).",
        )

    def test_king(self):
        """Test king."""
        self.assertTransformEqual(
            """
            country(france).
            country(usa).
            person(felipe).

            {king(C,X) : person(X)}:- country(C).


            :- king(C1,X); king(C2,X); C1!=C2.
            """,
            """
            country(france).
            country(usa).
            person(felipe).
            #count { 0,king(C,X): king(C,X): person(X) } :- country(C).
            :- king(C1,X); king(C2,X); C1!=C2.
            """,
        )

    def test_fact(self):
        """Test fact."""
        self.assertTransformEqual(
            """
            c := 1.
            p(c).
            """,
            """
            Fc(1).
            p(FUN) :- Fc(FUN).
            :- Fc(_); 1 < #count { V: Fc(V) }.
            """,
        )

    def test_pool(self):
        """Test pool."""
        self.assertTransformEqual(
            """
            f(1) := 2.
            p(f(a;b,c;d,e,f)).
            """,
            """
            Ff(1,2).
            p(FUN) :- Ff(a,FUN).
            p(FUN) :- f(b,c)=FUN.
            p(FUN) :- f(d,e,f)=FUN.
            :- Ff(X0,_); 1 < #count { V: Ff(X0,V) }.
            """,
        )

    def test_assignment_rule(self):
        """Test assignment rule."""
        self.assertTransformEqual(
            """
            c := 1.
            a := b :- p(c).
            p(c).
            """,
            """
            Fc(1).
            Fa(b) :- p(FUN); Fc(FUN).
            p(FUN) :- Fc(FUN).
            :- Fa(_); 1 < #count { V: Fa(V) }.
            :- Fc(_); 1 < #count { V: Fc(V) }.
            """,
        )

    def test_head_aggregate_assignment2(self):
        """Test head aggregate assignment2."""
        self.assertTransformEqual(
            "{king(spain) := felipe}.",
            """
            #count { 0,Fking(spain,felipe): Fking(spain,felipe) }.
            :- Fking(X0,_); 1 < #count { V: Fking(X0,V) }.
            """,
        )

    def test_no_change(self):
        """Test no change."""
        self.assertTransformEqual(
            "f(X) :- g(X).",
            "f(X) :- g(X).",
        )

    def test_some_assignment(self):
        """Test #some assignment."""
        self.assertTransformEqual(
            "color(X) := #some{r;g;b} :- country(X).",
            """
            #count { 0,Fcolor(X,r): Fcolor(X,r); 0,Fcolor(X,g): Fcolor(X,g); 0,Fcolor(X,b): Fcolor(X,b) } = 1 :- country(X).
            :- Fcolor(X0,_); 1 < #count { V: Fcolor(X0,V) }.
            """,
        )
        self.assertTransformEqual(
            "a := #some{X : p(X)} :- b.",
            """
            #count { 0,Fa(X): Fa(X): p(X) } = 1 :- #count { X: p(X) } >= 1; b.
            :- Fa(_); 1 < #count { V: Fa(V) }.
            """,
        )
        self.assertTransformEqual(
            "a := #some{X,Y : p(X,Y)}.",
            """
            #count { 0,Fa((X,Y)): Fa((X,Y)): p(X,Y) } = 1 :- #count { X,Y: p(X,Y) } >= 1.
            :- Fa(_); 1 < #count { V: Fa(V) }.
            """,
        )

    def test_some_assignment_with_pool(self):
        """Test #some assignment with a pooled left guard."""
        self.assertTransformEqual(
            "f(a;b) := #some{r;g}.",
            """
            #count { 0,Ff(a,r): Ff(a,r); 0,Ff(a,g): Ff(a,g) } = 1.
            #count { 0,Ff(b,r): Ff(b,r); 0,Ff(b,g): Ff(b,g) } = 1.
            :- Ff(X0,_); 1 < #count { V: Ff(X0,V) }.
            """,
        )

    def test_aggregate_assignment(self):
        """Test aggregate assignment."""
        self.assertTransformEqual(
            "f(X) := #sum{Y: p(Y,Z)} :- b(X,Z).",
            """
            Ff(X,W) :- b(X,Z); W = #sum { Y: p(Y,Z) }.
            :- Ff(X0,_); 1 < #count { V: Ff(X0,V) }.
            """,
        )

    def test_choice_count(self):
        """Test choice count."""
        self.assertTransformEqual(
            """
            f(X) := Y :- p(X,Y).
            #count { Y: p(X): f(X) = Y} :- q(X); r.
            """,
            """
            Ff(X,Y) :- p(X,Y).
            #count { Y: p(X): Ff(X,Y) } :- q(X); r.
            :- Ff(X0,_); 1 < #count { V: Ff(X0,V) }.
            """,
        )

    def test_choice_count_assignment(self):
        """Test choice count with an embedded assignment."""
        self.assertTransformEqual(
            """
            f(X) := Y :- p(X,Y).
            #count { Y: g(X) := Y: f(X) = Y} :- q(X); r.
            """,
            """
            Ff(X,Y) :- p(X,Y).
            #count { Y: Fg(X,Y): Ff(X,Y) } :- q(X); r.
            :- Ff(X0,_); 1 < #count { V: Ff(X0,V) }.
            :- Fg(X0,_); 1 < #count { V: Fg(X0,V) }.
            """,
        )

    def test_to_asp_head_aggregate_assignment(self):
        """Test to asp head aggregate assignment."""
        self.assertTransformEqual(
            "#count { 0,ass(king(f(C)),X): king(g(C)) := h(X): person(e(X)); ass(king(f(C)),X): f(X): person(e(X)) } :- country(C).",
            """
            #count { 0,ass(FUN,X): Fking(g(C),h(X)): person(e(X)), Fking(f(C),FUN); ass(FUN2,X): f(X): person(e(X)), Fking(f(C),FUN2) } :- country(C).
            :- Fking(X0,_); 1 < #count { V: Fking(X0,V) }.
            """,
        )

        self.assertTransformEqual(
            "{king(C) := X: person(X)}:- country(C).",
            """
            #count { 0,Fking(C,X): Fking(C,X): person(X) } :- country(C).
            :- Fking(X0,_); 1 < #count { V: Fking(X0,V) }.
            """,
        )

        self.assertTransformEqual(
            """
            a := 1.
            {f(a) := 1}.
            """,
            """
            Fa(1).
            #count { 0,Ff(FUN,1): Ff(FUN,1): Fa(FUN) }.
            :- Fa(_); 1 < #count { V: Fa(V) }.
            :- Ff(X0,_); 1 < #count { V: Ff(X0,V) }.
            """,
        )

        self.assertTransformEqual(
            """
            a := 1.
            {f(a) := 1} = a.
            """,
            """
            Fa(1).
            #count { 0,Ff(FUN,1): Ff(FUN,1): Fa(FUN) } = FUN2 :- Fa(FUN2).
            :- Fa(_); 1 < #count { V: Fa(V) }.
            :- Ff(X0,_); 1 < #count { V: Ff(X0,V) }.
            """,
        )

    def test_fibo(self):
        """Test fibo."""
        self.assertTransformEqual(
            "fibo(X) := Y :- number(X); X>1; fibo(X-1) + fibo(X-2)=Y.",
            """
            Ffibo(X,Y) :- number(X); Ffibo(1*X+(-1),FUN); Ffibo(1*X+(-2),FUN2); X>1; Y=FUN+FUN2.
            :- Ffibo(X0,_); 1 < #count { V: Ffibo(X0,V) }.
            """,
        )

    def test_company(self):
        """Test company."""
        self.assertTransformEqual(
            "controller(C3) := C1 :- company(C1), company(C3), #sum{controlsStk(C1,C2,C3), C2} > 50.",
            """
            Fcontroller(C3,C1) :- company(C1); company(C3); #sum { FUN,C2: FcontrolsStk(C1,C2,C3,FUN) } > 50.
            :- Fcontroller(X0,_); 1 < #count { V: Fcontroller(X0,V) }.
            :- FcontrolsStk(X0,X1,X2,_); 1 < #count { V: FcontrolsStk(X0,X1,X2,V) }.
            """,
            intensional_functions={"controlsStk/3"},
        )

    def test_show(self):
        """Test show statements with functional conditions."""
        self.assertTransformEqual(
            """
            #show f(X) : f = X.
            #show g(X,Y) : g(X) = Y.
            """,
            """
            #show f(X): Ff(X).
            #show g(X,Y): Fg(X,Y).
            :- Ff(_); 1 < #count { V: Ff(V) }.
            :- Fg(X0,_); 1 < #count { V: Fg(X0,V) }.
            """,
            intensional_functions={"f/0", "g/1"},
        )

    def test_show_negation(self):
        """Test show statements with negated functional conditions."""
        self.assertTransformEqual(
            """
            #show f(X) : dom(X), not f = X.
            #show g(X,Y) : dom(X,Y), not g(X) = Y.
            """,
            """
            #show f(X): dom(X); not Ff(X).
            #show g(X,Y): dom(X,Y); not Fg(X,Y).
            :- Ff(_); 1 < #count { V: Ff(V) }.
            :- Fg(X0,_); 1 < #count { V: Fg(X0,V) }.
            """,
            intensional_functions={"f/0", "g/1"},
        )

    def test_showf_directive(self):
        """Test #showf directive."""
        self.assertTransformEqual(
            """
            #showf color/1.
            color(X) := #some{r;g} :- c(X).
            """,
            """
            #show Fcolor/2. [true]
            #count { 0,Fcolor(X,r): Fcolor(X,r); 0,Fcolor(X,g): Fcolor(X,g) } = 1 :- c(X).
            :- Fcolor(X0,_); 1 < #count { V: Fcolor(X0,V) }.
            """,
        )

    def test_conditional_literal(self):
        """Test conditional literals with functional conditions."""
        self.assertTransformEqual(
            """
            :- p(X); q(X) : f = X.
            :- p(X); q(X) : not f = X.
            :- p(X,Y); q(X) : g(X) = Y.
            :- p(X,Y); q(X) : not g(X) = Y.
            """,
            """
            :- p(X); q(X): Ff(X).
            :- p(X); q(X): not Ff(X).
            :- p(X,Y); q(X): Fg(X,Y).
            :- p(X,Y); q(X): not Fg(X,Y).
            :- Ff(_); 1 < #count { V: Ff(V) }.
            :- Fg(X0,_); 1 < #count { V: Fg(X0,V) }.
            """,
            intensional_functions={"f/0", "g/1"},
        )

    def test_aggregates2(self):
        """Test body aggregates with functional conditions."""
        self.assertTransformEqual(
            """
            :- #sum{X : f = X; Y : f = Y} > 0.
            :- #sum{X : f = X; Y : p(Z), f(Z) = Y} > 0.
            """,
            """
            :- #sum { X: Ff(X); Y: Ff(Y) } > 0.
            :- #sum { X: Ff(X); Y: p(Z), Ff(Z,Y) } > 0.
            :- Ff(_); 1 < #count { V: Ff(V) }.
            :- Ff(X0,_); 1 < #count { V: Ff(X0,V) }.
            """,
            intensional_functions={"f/0", "f/1"},
        )

    def test_aggregates3(self):
        """Test body aggregates with negated functional conditions."""
        self.assertTransformEqual(
            """
            :- #sum{X : f = X; Y : p(Y), not f = Y} > 0.
            :- #sum{X : f = X; Y : p(Z,Y), not f(Z) = Y} > 0.
            """,
            """
            :- #sum { X: Ff(X); Y: p(Y), not Ff(Y) } > 0.
            :- #sum { X: Ff(X); Y: p(Z,Y), not Ff(Z,Y) } > 0.
            :- Ff(_); 1 < #count { V: Ff(V) }.
            :- Ff(X0,_); 1 < #count { V: Ff(X0,V) }.
            """,
            intensional_functions={"f/0", "f/1"},
        )

    def test_aggregates4(self):
        """Test body aggregates with anonymous functional conditions."""
        self.assertTransformEqual(
            """
            :- #sum{X : f = X; Y : p(Y), not f(Y) = _} > 0.
            """,
            """
            :- #sum { X: Ff(X); Y: p(Y), not Ff(Y,*) } > 0.
            :- Ff(_); 1 < #count { V: Ff(V) }.
            :- Ff(X0,_); 1 < #count { V: Ff(X0,V) }.
            """,
            intensional_functions={"f/0", "f/1"},
        )

    def test_aggregates5(self):
        """Test body aggregates with anonymous functional conditions."""
        self.assertTransformEqual(
            """
            :- #sum{X : f = X; Y : Y=1, not f = _} > 0.
            """,
            """
            :- #sum { X: Ff(X); 1: not Ff(*) } > 0.
            :- Ff(_); 1 < #count { V: Ff(V) }.
            """,
            intensional_functions={"f/0"},
        )

    def test_optimize(self):
        """Test optimize statements and weak constraints."""
        self.assertTransformEqual(
            "#minimize{ X : f = X }.",
            """
            :~ Ff(X). [X]
            :- Ff(_); 1 < #count { V: Ff(V) }.
            """,
            intensional_functions={"f/0"},
        )
        self.assertTransformEqual(
            ":~ p(X); f = X. [X@1]",
            """
            :~ p(X); Ff(X). [X@1]
            :- Ff(_); 1 < #count { V: Ff(V) }.
            """,
            intensional_functions={"f/0"},
        )

    def test_family_full(self):
        """Test family full."""
        self.assertTransformEqual(
            """
            father(cain):=adam.
            father(abel):=adam.
            mother(cain):=eve.
            mother(abel):=eve.

            % person(father(X)).
            % person(mother(X)).
            person(Y) :- father(_)=Y.
            person(Y) :- mother(_)=Y.
            person(X) :- father(X)=_.
            person(X) :- mother(X)=_.
            % male(father(X)).
            % female(mother(X)).
            male(Y) :- father(_)=Y.
            female(Y) :- mother(_)=Y.

            orphan(X) :- person(X), not father(X)=_, not mother(X)=_.

            n_orphan := #count{X : orphan(X)}.
            """,
            """
            Ffather(cain,adam).
            Ffather(abel,adam).
            Fmother(cain,eve).
            Fmother(abel,eve).
            person(Y) :- Ffather(_,Y).
            person(Y) :- Fmother(_,Y).
            person(X) :- Ffather(X,_).
            person(X) :- Fmother(X,_).
            male(Y) :- Ffather(_,Y).
            female(Y) :- Fmother(_,Y).
            orphan(X) :- person(X); #false: Ffather(X,*); #false: Fmother(X,*).
            Fn_orphan(W) :- W = #count { X: orphan(X) }.
            :- Ffather(X0,_); 1 < #count { V: Ffather(X0,V) }.
            :- Fmother(X0,_); 1 < #count { V: Fmother(X0,V) }.
            :- Fn_orphan(_); 1 < #count { V: Fn_orphan(V) }.
            """,
        )

    def test_prefix(self):
        """Test the configured prefix is applied across all assignment shapes."""
        self.assertTransformEqual(
            """
            a := 1 :- b.
            f(X) := #sum{Y: p(Y)} :- q(X).
            { c := 1 }.
            p(a).
            #showf a/0.
            """,
            """
            Ga(1) :- b.
            Gf(X,W) :- q(X); W = #sum { Y: p(Y) }.
            #count { 0,Gc(1): Gc(1) }.
            p(FUN) :- Ga(FUN).
            #show Ga/1. [true]
            :- Ga(_); 1 < #count { V: Ga(V) }.
            :- Gc(_); 1 < #count { V: Gc(V) }.
            :- Gf(X0,_); 1 < #count { V: Gf(X0,V) }.
            """,
            prefix="G",
        )

    def test_prefix_some(self):
        """Test the configured prefix with #some assignments and plain statements."""
        self.assertTransformEqual(
            """
            color(X) := #some{r;g;b} :- country(X).
            :- neighbor(C,D), color(C)=color(D).
            country(a).
            :- q.
            #show color/1.
            #count { X: king(C) := X: person(X) } :- country(C).
            1 <= #count{ X: p(X): q(X) } <= 2.
            """,
            """
            #count { 0,Gcolor(X,r): Gcolor(X,r); 0,Gcolor(X,g): Gcolor(X,g); 0,Gcolor(X,b): Gcolor(X,b) } = 1 :- country(X).
            :- neighbor(C,D); Gcolor(C,FUN); Gcolor(D,FUN).
            country(a).
            :- q.
            #show color/1. [true]
            #count { X: Gking(C,X): person(X) } :- country(C).
            1 <= #count { X: p(X): q(X) } <= 2.
            :- Gcolor(X0,_); 1 < #count { V: Gcolor(X0,V) }.
            :- Gking(X0,_); 1 < #count { V: Gking(X0,V) }.
            """,
            prefix="G",
        )

    def test_disjunction(self):
        """Test disjunctive heads pass through unchanged."""
        self.assertTransformEqual(
            "a | b :- c.",
            "a; b :- c.",
        )

    def test_non_intensional_equality(self):
        """Test equalities over non-intensional functions are left untouched.

        The ground comparison is constant-folded away by clingo's rewriting,
        which drops the trivially unsatisfiable rule.
        """
        self.assertTransformEqual(
            """
            f := 1.
            p :- q(g(1;2)); g(1) = 2.
            """,
            """
            Ff(1).
            :- Ff(_); 1 < #count { V: Ff(V) }.
            """,
        )

    def test_conditional_literal_main(self):
        """Test an intensional function in the main literal of a conditional literal.

        The generated equality must stay inside the condition: its variables
        may be local to the conditional literal.
        """
        self.assertTransformEqual(
            """
            a := 1.
            :- p(X); q(a) : r(X).
            """,
            """
            Fa(1).
            :- p(X); q(FUN): r(X), Fa(FUN).
            :- Fa(_); 1 < #count { V: Fa(V) }.
            """,
        )

    def test_head_aggregate_element_unnesting(self):
        """Test intensional functions inside head aggregate elements."""
        self.assertTransformEqual(
            """
            a := 1.
            #count{ X: king(a) := X: p(X,a) }.
            """,
            """
            Fa(1).
            #count { X: Fking(FUN2,X): p(X,FUN), Fa(FUN), Fa(FUN2) }.
            :- Fa(_); 1 < #count { V: Fa(V) }.
            :- Fking(X0,_); 1 < #count { V: Fking(X0,V) }.
            """,
        )

    def test_choice_condition_unnesting(self):
        """Test intensional functions inside choice assignment conditions."""
        self.assertTransformEqual(
            """
            a := 1.
            { c := 1 : p(a) }.
            """,
            """
            Fa(1).
            #count { 0,Fc(1): Fc(1): p(FUN), Fa(FUN) }.
            :- Fa(_); 1 < #count { V: Fa(V) }.
            :- Fc(_); 1 < #count { V: Fc(V) }.
            """,
        )

    def test_optimize_unnesting(self):
        """Test intensional functions inside optimize elements and weak constraints."""
        self.assertTransformEqual(
            """
            a := 1.
            #minimize{ f(a),X : p(X,a) }.
            """,
            """
            Fa(1).
            :~ p(X,FUN2); Fa(FUN); Fa(FUN2). [f(FUN),X]
            :- Fa(_); 1 < #count { V: Fa(V) }.
            """,
        )
        self.assertTransformEqual(
            """
            a := 1.
            :~ q(a). [a@1]
            """,
            """
            Fa(1).
            :~ q(FUN2); Fa(FUN); Fa(FUN2). [FUN@1]
            :- Fa(_); 1 < #count { V: Fa(V) }.
            """,
        )

    def test_ground_nested_function(self):
        """Test ground nested intensional functions (symbolic terms)."""
        self.assertTransformEqual(
            """
            f(1) := 2.
            p(g(f(1))).
            """,
            """
            Ff(1,2).
            p(g(FUN)) :- Ff(1,FUN).
            :- Ff(X0,_); 1 < #count { V: Ff(X0,V) }.
            """,
        )
        self.assertTransformEqual(
            """
            f(1) := 2.
            p(g(h(f(1)))).
            """,
            """
            Ff(1,2).
            p(g(h(FUN))) :- Ff(1,FUN).
            :- Ff(X0,_); 1 < #count { V: Ff(X0,V) }.
            """,
        )

    def test_flipped_equality(self):
        """Test an equality with the intensional function on the right side."""
        self.assertTransformEqual(
            """
            f := 1.
            p(X) :- q(X); X = f.
            """,
            """
            Ff(1).
            p(X) :- q(X); Ff(X).
            :- Ff(_); 1 < #count { V: Ff(V) }.
            """,
        )

    def test_comparison_guard(self):
        """Test an intensional function in a non-equality comparison guard."""
        self.assertTransformEqual(
            """
            f := 1.
            p(X) :- q(X); X < f.
            """,
            """
            Ff(1).
            p(X) :- q(X); Ff(FUN); X<FUN.
            :- Ff(_); 1 < #count { V: Ff(V) }.
            """,
        )

    def test_prefix_disjunction(self):
        """Test that non-assignment heads pass through the renaming pass."""
        self.assertTransformEqual(
            "a | b :- c.",
            "a; b :- c.",
            prefix="G",
        )

    def test_intensional_in_negated_weak_constraint_literal(self):
        """Test that intensional functions in negated weak-constraint literals are rejected."""
        with self.assertRaisesRegex(
            RewritingException,
            r"error: intensional functions are not allowed in negated literals",
        ):
            self.assertTransformEqual(
                """
                f(1) := 2.
                :~ p(X), not q(f(X)). [1@0,X]
                """,
                "",
            )

    def test_intensional_in_negated_set_aggregate_literal(self):
        """Test that intensional functions in negated set-aggregate element literals are rejected."""
        with self.assertRaisesRegex(
            RewritingException,
            r"error: intensional functions are not allowed in negated literals",
        ):
            self.assertTransformEqual(
                """
                f := 1.
                :- { not p(f) : q }.
                """,
                "",
            )

    def test_intensional_in_negated_head_aggregate_literal(self):
        """Test that intensional functions in negated head-aggregate element literals are rejected."""
        with self.assertRaisesRegex(
            RewritingException,
            r"error: intensional functions are not allowed in negated literals",
        ):
            self.assertTransformEqual(
                """
                f := 1.
                1 = #count{ X : not p(f) : q(X) } :- r.
                """,
                "",
            )

    def test_intensional_in_negated_aggregate_condition(self):
        """Test that negated aggregate condition literals are lifted."""
        self.assertTransformEqual(
            """
            f := 1.
            :- 0 < #count{ X : p(X), not q(f) }.
            """,
            """
            Ff(1).
            :- 0 < #count { X: p(X), not AUX1 }.
            AUX1 :- q(FUN); Ff(FUN).
            :- Ff(_); 1 < #count { V: Ff(V) }.
            """,
        )

    def test_negated_condition_literals_in_head(self):
        """Test that head conditional and choice conditions are lifted."""
        self.assertTransformEqual(
            """
            a(X) : b(X), not c(X) :- d(X).
            { p(X) : q(X), not r(X) } :- s(X).
            """,
            """
            a(X): b(X), not AUX1(X) :- d(X).
            AUX1(X) :- c(X).
            #count { 0,p(X): p(X): q(X), not AUX2(X) } :- s(X).
            AUX2(X) :- r(X).
            """,
        )

    def test_intensional_in_negated_condition(self):
        """Test that negated condition literals are lifted into auxiliary rules."""
        self.assertTransformEqual(
            """
            f := 1.
            :- q : not p(f).
            """,
            """
            Ff(1).
            :- q: not AUX1.
            AUX1 :- p(FUN); Ff(FUN).
            :- Ff(_); 1 < #count { V: Ff(V) }.
            """,
        )

    def test_negated_condition_literals_with_variables(self):
        """Test that lifted condition literals carry the literal's variables."""
        self.assertTransformEqual(
            """
            a :- b(X); c(X,Y) : d(Y), not e(5,f(Y;Y+2)).
            b(2) :- c(X) : d(X), e(Y), not p(g(X,Y)).
            """,
            """
            a :- b(X); c(X,Y): d(Y), not AUX1(Y).
            AUX1(Y) :- e(5,f(Y)).
            AUX1(Y) :- e(5,f(1*Y+2)).
            b(2) :- c(X): d(X), e(Y), not AUX2(X,Y).
            AUX2(X,Y) :- p(g(X,Y)).
            """,
        )

    def test_unsafe(self):
        """Test unsafe."""
        out = io.StringIO()
        with redirect_stderr(out):
            with self.assertRaisesRegex(
                RuntimeError,
                r"\('rewriting failed', \[\(<clingo_funasp\.ast\.StatementRule object at 0x[0-9A-Fa-f]+>, RuntimeError\('rewriting failed'\)\)\]\)",
            ):
                self.assertTransformEqual(
                    """
                    p(X) :- q(Y).
                    """,
                    "",
                )
            captured_output = out.getvalue().strip()
            self.assertEqual(
                captured_output,
                textwrap.dedent("""\
                <string>:1:1-14: error: unsafe variables in:
                  p(X) :- q(Y).
                note: the following variables are unsafe:
                  X"""),
            )

    def test_unsafe_fun(self):
        """Test unsafe assignment."""
        out = io.StringIO()
        with redirect_stderr(out):
            with self.assertRaisesRegex(
                RuntimeError,
                r"\('rewriting failed', \[\(<clingo_funasp\.ast\.StatementRule object at 0x[0-9A-Fa-f]+>, RuntimeError\('rewriting failed'\)\)\]\)",
            ):
                self.assertTransformEqual(
                    """
                    f := X :- q(Y).
                    """,
                    "",
                )
            captured_output = out.getvalue().strip()
            self.assertEqual(
                captured_output,
                textwrap.dedent("""\
                <string>:1:1-16: error: unsafe variables in:
                  f := X :- q(Y).
                note: the following variables are unsafe:
                  X"""),
            )

    def test_undefined_operation_fun(self):
        """Test undefined operation in an assignment."""
        out = io.StringIO()
        with redirect_stderr(out):
            self.assertTransformEqual(
                """
                f := a + 1.
                """,
                """
                :- Ff(_); 1 < #count { V: Ff(V) }.
                """,
            )
            captured_output = out.getvalue().strip()
            self.assertEqual(
                captured_output,
                textwrap.dedent("""\
                <string>:1:6-11: info: operation undefined in:
                  f := a+1.
                note: the following operations are undefined:
                  a+1"""),
            )

    def test_hamiltonian(self):
        """Test body aggregates with anonymous functional conditions."""
        self.assertTransformEqual(
            """
            next(X) := #some{Y: edge(X,Y)} :- vertex(X).
            start := #min{X: vertex(X)}.
            visited(next(start)).
            visited(next(X)) :- visited(X).
            :- vertex(X), not visited(X).
            """,
            """
            #count { 0,Fnext(X,Y): Fnext(X,Y): edge(X,Y) } = 1 :- vertex(X); #count { Y: edge(X,Y) } >= 1.
            Fstart(W) :- W = #min { X: vertex(X) }.
            visited(FUN2) :- Fstart(FUN); Fnext(FUN,FUN2).
            visited(FUN) :- visited(X); Fnext(X,FUN).
            :- vertex(X); #false: visited(X).
            :- Fnext(X0,_); 1 < #count { V: Fnext(X0,V) }.
            :- Fstart(_); 1 < #count { V: Fstart(V) }.
            """,
            intensional_functions={"start/0", "next/1"},
        )
