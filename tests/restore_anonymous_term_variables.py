from clingo_funasp import ast
from clingo_funasp.core import Library

from funasp.ast import RewriteContext
from funasp.util.ast import AST


def _restore_anonymous_term_variables(library: Library, node: AST) -> AST:
    """Restore anonymous term-variable names to "_" in an AST node."""

    def _dispatch(n: AST) -> AST | None:
        if isinstance(n, ast.terms.TermVariable):
            if not n.anonymous or n.name == "_":
                return None
            return ast.terms.TermVariable(library, n.location, "_", anonymous=True)
        return n.transform(library, _dispatch)

    return _dispatch(node) or node


def restore_anonymous_term_variables(
    context: RewriteContext,
    statement: ast.statements.Statement,
) -> ast.statements.Statement:
    """Restore anonymous term-variable names in a statement."""
    rewritten = _restore_anonymous_term_variables(context.lib.library, statement)
    assert isinstance(rewritten, ast.statements.Statement)
    return rewritten
