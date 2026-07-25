"""
Unit tests for the head- and condition-literal rewritings in
``funasp.ast._rewritings.negated_literals``.
"""

import unittest

from funasp.ast import RewriteContext, parse_string
from funasp.ast._rewritings.negated_literals import (
    rewrite_negated_condition_literals,
    rewrite_negated_head_literals,
)
from funasp.core import Library
from funasp.util.types import SymbolSignature


class TestRewriteNegatedHeadLiterals(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures for each test."""
        self.lib = Library()
        self.context = RewriteContext(self.lib)

    def _rewrite(self, program: str) -> str:
        """Rewrite a single rule and return its string form."""
        statement = parse_string(self.lib, program)[1].original
        return str(rewrite_negated_head_literals(self.context, statement))

    def _canonical(self, program: str) -> str:
        """Return the string form of a parsed rule (printer canonicalization)."""
        return str(parse_string(self.lib, program)[1].original)

    def test_moves_negated_head_literals(self):
        """Negated head disjuncts move to the body with complemented sign."""
        self.assertEqual(
            self._rewrite("a, not b, not not c :- d."),
            self._canonical("a :- d, not not b, not c."),
        )

    def test_moves_negated_head_literals_with_variables(self):
        """The rewriting preserves the arguments of the moved literals."""
        self.assertEqual(
            self._rewrite("a(X), not b(X), not not c(X) :- d(X,Y)."),
            self._canonical("a(X) :- d(X,Y), not not b(X), not c(X)."),
        )

    def test_moves_single_negated_head_literal(self):
        """A doubly negated simple head becomes a constraint."""
        self.assertEqual(
            self._rewrite("not not c :- not b."),
            self._canonical(":- not b, not c."),
        )

    def test_moves_single_negated_head_literal_single_sign(self):
        """A singly negated simple head becomes a constraint."""
        self.assertEqual(
            self._rewrite("not a :- d."),
            self._canonical(":- d, not not a."),
        )

    def test_non_rule_statement_unchanged(self):
        """A non-rule statement is returned unchanged."""
        statement = parse_string(self.lib, "a :- d.")[0].original
        self.assertIs(rewrite_negated_head_literals(self.context, statement), statement)

    def test_positive_simple_head_unchanged(self):
        """A rule with a non-negated simple head is returned unchanged."""
        statement = parse_string(self.lib, "a :- d.")[1].original
        self.assertIs(rewrite_negated_head_literals(self.context, statement), statement)

    def test_aggregate_head_unchanged(self):
        """A rule whose head is neither simple nor a disjunction is unchanged."""
        statement = parse_string(self.lib, "{ a } :- d.")[1].original
        self.assertIs(rewrite_negated_head_literals(self.context, statement), statement)

    def test_positive_disjunction_unchanged(self):
        """A disjunctive head without negated literals is returned unchanged."""
        statement = parse_string(self.lib, "a, b :- d.")[1].original
        self.assertIs(rewrite_negated_head_literals(self.context, statement), statement)


class TestRewriteNegatedConditionLiterals(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures for each test."""
        self.lib = Library()
        self.context = RewriteContext(self.lib)

    def _rewrite(self, program: str) -> list[str]:
        """Rewrite a single rule and return the resulting statement strings."""
        statement = parse_string(self.lib, program)[1].original
        return [
            str(result)
            for result in rewrite_negated_condition_literals(self.context, statement)
        ]

    def _assert_unchanged(self, statement):
        """Assert the statement is returned unchanged as a singleton list."""
        result = rewrite_negated_condition_literals(self.context, statement)
        self.assertEqual(len(result), 1)
        self.assertIs(result[0], statement)

    def test_lifts_negated_condition_literal(self):
        """A negated condition literal is replaced by an auxiliary call."""
        self.assertEqual(
            self._rewrite("a :- b(X); c(X,Y) : d(Y), not e(5,f(Y;Y+2))."),
            [
                "a :- b(X); c(X,Y): d(Y), not AUX1(Y).",
                "AUX1(Y) :- e(5,f(Y;Y+2)).",
            ],
        )

    def test_lifts_literal_with_two_variables_in_argument(self):
        """The auxiliary call carries the distinct variables of the literal."""
        self.assertEqual(
            self._rewrite("b(2) :- c(X) : d(X), not p(g(X,Y))."),
            [
                "b(2) :- c(X): d(X), not AUX1(X,Y).",
                "AUX1(X,Y) :- p(g(X,Y)).",
            ],
        )

    def test_counter_increments_across_rules(self):
        """Each lifted literal gets the next auxiliary predicate name."""
        self.assertEqual(
            self._rewrite("a :- b(X) : c(X), not d(X)."),
            ["a :- b(X): c(X), not AUX1(X).", "AUX1(X) :- d(X)."],
        )
        self.assertEqual(
            self._rewrite("e :- b(X) : c(X), not f(X)."),
            ["e :- b(X): c(X), not AUX2(X).", "AUX2(X) :- f(X)."],
        )

    def test_skips_used_predicate_names(self):
        """Names already used in the program are skipped by the generator."""
        self.context.predicates.add(SymbolSignature("AUX1", 3))
        self.assertEqual(
            self._rewrite("a :- b(X) : c(X), not d(X)."),
            ["a :- b(X): c(X), not AUX2(X).", "AUX2(X) :- d(X)."],
        )

    def test_zero_variable_literal(self):
        """A negated literal without variables yields a 0-ary auxiliary."""
        self.assertEqual(
            self._rewrite("q :- r(X) : s(X), not t(5)."),
            ["q :- r(X): s(X), not AUX1.", "AUX1 :- t(5)."],
        )

    def test_anonymous_variables_are_projected(self):
        """Anonymous variables do not become auxiliary arguments."""
        self.assertEqual(
            self._rewrite("q :- r(X) : s(X), not t(X,_)."),
            ["q :- r(X): s(X), not AUX1(X).", "AUX1(X) :- t(X,_)."],
        )

    def test_lifts_head_conditional_literal(self):
        """A negated literal in a conditional disjunct condition is lifted."""
        self.assertEqual(
            self._rewrite("a(X) : b(X), not c(X) :- d(X)."),
            ["a(X): b(X), not AUX1(X) :- d(X).", "AUX1(X) :- c(X)."],
        )

    def test_lifts_head_conditional_literal_in_disjunction(self):
        """Bare disjuncts stay while conditional disjunct conditions are lifted."""
        self.assertEqual(
            self._rewrite("p; q(Y) : r(Y,Z), not s(Y,Z) :- t(Y)."),
            [
                "p; q(Y): r(Y,Z), not AUX1(Y,Z) :- t(Y).",
                "AUX1(Y,Z) :- s(Y,Z).",
            ],
        )

    def test_lifts_choice_element_condition(self):
        """A negated literal in a choice element condition is lifted."""
        self.assertEqual(
            self._rewrite("{ p(X) : q(X), not r(X) } :- s(X)."),
            ["{ p(X): q(X), not AUX1(X) } :- s(X).", "AUX1(X) :- r(X)."],
        )

    def test_lifts_choice_with_multiple_elements(self):
        """Each choice element condition gets its own auxiliary predicate."""
        self.assertEqual(
            self._rewrite("1 { a : not b; c(X) : d(X), not e(f(X)) } :- g(X)."),
            [
                "1 <= { a: not AUX1; c(X): d(X), not AUX2(X) } :- g(X).",
                "AUX1 :- b.",
                "AUX2(X) :- e(f(X)).",
            ],
        )

    def test_lifts_head_aggregate_element_condition(self):
        """A negated literal in a head aggregate element condition is lifted."""
        self.assertEqual(
            self._rewrite("1 <= #count{ X : p(X) : q(X), not r(X) } :- s."),
            [
                "1 <= #count { X: p(X): q(X), not AUX1(X) } :- s.",
                "AUX1(X) :- r(X).",
            ],
        )

    def test_lifts_head_aggregate_element_condition_with_variables(self):
        """The lifted head aggregate condition carries the literal's variables."""
        self.assertEqual(
            self._rewrite("2 = #sum{ Y,1 : p(Y) : q(Y), not r(Y,Z), t(Z) } :- u."),
            [
                "2 = #sum { Y,1: p(Y): q(Y), not AUX1(Y,Z), t(Z) } :- u.",
                "AUX1(Y,Z) :- r(Y,Z).",
            ],
        )

    def test_lifts_body_aggregate_element_condition(self):
        """A negated literal in a body aggregate element condition is lifted."""
        self.assertEqual(
            self._rewrite(":- #count{ X : p(X), not q(X) } > 5."),
            [" :- #count { X: p(X), not AUX1(X) } > 5.", "AUX1(X) :- q(X)."],
        )

    def test_lifts_body_aggregate_element_condition_nested_term(self):
        """The lifted literal keeps its nested argument terms in the aux rule."""
        self.assertEqual(
            self._rewrite("a :- #count{ X : p(X), not q(f(X)) } > 0."),
            [
                "a :- #count { X: p(X), not AUX1(X) } > 0.",
                "AUX1(X) :- q(f(X)).",
            ],
        )

    def test_lifts_body_set_aggregate_element_condition(self):
        """A negated literal in a body set aggregate condition is lifted."""
        self.assertEqual(
            self._rewrite("b :- 1 { p(X) : q(X), not r(X) }."),
            ["b :- 1 <= { p(X): q(X), not AUX1(X) }.", "AUX1(X) :- r(X)."],
        )

    def test_lifts_body_set_aggregate_with_multiple_elements(self):
        """Each body set aggregate element condition is lifted independently."""
        self.assertEqual(
            self._rewrite(":- { a : not b(Y), c(Y); d : not e } 0."),
            [
                " :- { a: not AUX1(Y), c(Y); d: not AUX2 } <= 0.",
                "AUX1(Y) :- b(Y).",
                "AUX2 :- e.",
            ],
        )

    def test_non_rule_statement_unchanged(self):
        """A non-rule statement is returned unchanged."""
        self._assert_unchanged(parse_string(self.lib, "a :- d.")[0].original)

    def test_rule_without_conditional_literals_unchanged(self):
        """A rule whose body has no conditional literals is unchanged."""
        self._assert_unchanged(parse_string(self.lib, "a :- d, not e.")[1].original)

    def test_positive_condition_unchanged(self):
        """A conditional literal without negated literals is unchanged."""
        self._assert_unchanged(
            parse_string(self.lib, "a :- b(X) : c(X), d(X).")[1].original
        )

    def test_negated_comparison_unchanged(self):
        """Negated comparisons in conditions are left untouched."""
        self._assert_unchanged(
            parse_string(self.lib, "a :- b(X) : c(X), not X = 3.")[1].original
        )

    def test_positive_aggregate_conditions_unchanged(self):
        """Aggregates and choices without negated condition literals are unchanged."""
        self._assert_unchanged(
            parse_string(self.lib, "{ p(X) : q(X) } :- s(X).")[1].original
        )
        self._assert_unchanged(
            parse_string(self.lib, ":- #count{ X : p(X), q(X) } > 5.")[1].original
        )
        self._assert_unchanged(
            parse_string(self.lib, "b :- 1 { p(X) : q(X) }.")[1].original
        )

    def test_bare_disjunction_unchanged(self):
        """A disjunction without conditional disjuncts is unchanged."""
        self._assert_unchanged(parse_string(self.lib, "a; not b :- d.")[1].original)

    def test_negated_aggregate_element_literal_unchanged(self):
        """The main literal of an aggregate element is never lifted."""
        self._assert_unchanged(
            parse_string(self.lib, "{ not p(X) : q(X) } :- s(X).")[1].original
        )

    def test_double_negation_unchanged(self):
        """Doubly negated condition literals are left untouched."""
        self._assert_unchanged(
            parse_string(self.lib, "a :- b(X) : c(X), not not d(X).")[1].original
        )

    def test_double_negation_in_aggregate_condition_unchanged(self):
        """Doubly negated literals in aggregate conditions are untouched."""
        self._assert_unchanged(
            parse_string(self.lib, ":- #count{ X : p(X), not not q(X) } > 5.")[
                1
            ].original
        )

    def test_double_negation_only_condition_unchanged(self):
        """A condition consisting only of a doubly negated literal is untouched."""
        self._assert_unchanged(
            parse_string(self.lib, "a :- b : not not c.")[1].original
        )

    def test_double_negation_only_condition_with_variables_unchanged(self):
        """A doubly negated condition literal with variables is untouched."""
        self._assert_unchanged(
            parse_string(self.lib, "a(X) :- b(X) : not not c(X,Y).")[1].original
        )


if __name__ == "__main__":
    unittest.main()
