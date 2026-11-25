import tempfile

from clingo_funasp import core, ast


class TestParseString:

    def setup_method(self):
        self.lib = core.Library()

    def parse_string(self, s):
        statements = []
        ast.parse_string(self.lib, s, lambda x: statements.append(x))
        if isinstance(statements[0], ast.statements.StatementProgram):
            statements = statements[1:]
        return "\n".join(map(str, statements))

    def parse_with_file(self, s):
        # Create a named temporary file
        with tempfile.NamedTemporaryFile(
            mode="w+",  # Read/write mode
        ) as temp_file:
            temp_file.write(s)
            temp_file.write("\n")
            temp_file.flush()

            statements = []
            ast.parse_files(self.lib, [temp_file.name], lambda x: statements.append(x))
            if isinstance(statements[0], ast.statements.StatementProgram):
                statements = statements[1:]
            return "\n".join(map(str, statements))

    def test_parse_string(self):
        assert self.parse_string("a.") == "a."
        assert self.parse_string("a(b).") == "a(b)."
        assert self.parse_string("a(b,c).") == "a(b,c)."
        assert self.parse_string("a(b,c,d).") == "a(b,c,d)."

    def test_parse_string_assignments(self):
        assert self.parse_string("a := 1.") == "Fa(1)."
        assert self.parse_string("a(b) := 1.") == "Fa(b,1)."
        assert self.parse_string("a(b,c) := 1.") == "Fa(b,c,1)."
        assert self.parse_string("a(b,c,d) := 1.") == "Fa(b,c,d,1)."

    def test_parse_string_assignments_with_aggregates(self):
        assert (
            self.parse_string("a := #sum{ X : p(X)}.") == "Fa = #sum { X: NONE: p(X) }."
        )
        assert (
            self.parse_string("a(b) := #sum{ X : p(X)}.")
            == "Fa(b) = #sum { X: NONE: p(X) }."
        )
        assert (
            self.parse_string("a := #some{ X : p(X)}.")
            == "FSa = #sum { X: NONE: p(X) }."
        )
        assert (
            self.parse_string("a(b) := #some{ X : p(X)}.")
            == "FSa(b) = #sum { X: NONE: p(X) }."
        )

    def test_parse_string_assignments_in_aggregates(self):
        assert (
            self.parse_string("#sum{ X : a := X : p(X)}.") == "#sum { X: Fa(X): p(X) }."
        )
        assert (
            self.parse_string("#sum{ X : a(b) := X : p(X)}.")
            == "#sum { X: Fa(b,X): p(X) }."
        )

    def test_showf(self):
        assert self.parse_string("#showf a/0.") == "#show Fa/1. [true]"
        assert self.parse_string("#showf a/1.") == "#show Fa/2. [true]"

    def test_file_string(self):
        assert self.parse_with_file("a.") == "a."
        assert self.parse_with_file("a(b).") == "a(b)."
        assert self.parse_with_file("a(b,c).") == "a(b,c)."
        assert self.parse_with_file("a(b,c,d).") == "a(b,c,d)."

    def test_file_string_assignments(self):
        assert self.parse_with_file("a := 1.") == "Fa(1)."
        assert self.parse_with_file("a(b) := 1.") == "Fa(b,1)."
        assert self.parse_with_file("a(b,c) := 1.") == "Fa(b,c,1)."
        assert self.parse_with_file("a(b,c,d) := 1.") == "Fa(b,c,d,1)."

    def test_file_string_assignments_with_aggregates(self):
        assert (
            self.parse_with_file("a := #sum{ X : p(X)}.")
            == "Fa = #sum { X: NONE: p(X) }."
        )
        assert (
            self.parse_with_file("a(b) := #sum{ X : p(X)}.")
            == "Fa(b) = #sum { X: NONE: p(X) }."
        )
        assert (
            self.parse_with_file("a := #some{ X : p(X)}.")
            == "FSa = #sum { X: NONE: p(X) }."
        )
        assert (
            self.parse_with_file("a(b) := #some{ X : p(X)}.")
            == "FSa(b) = #sum { X: NONE: p(X) }."
        )

    def test_file_string_assignments_in_aggregates(self):
        assert (
            self.parse_with_file("#sum{ X : a := X : p(X)}.")
            == "#sum { X: Fa(X): p(X) }."
        )
        assert (
            self.parse_with_file("#sum{ X : a(b) := X : p(X)}.")
            == "#sum { X: Fa(b,X): p(X) }."
        )

    def test_file_showf(self):
        assert self.parse_with_file("#showf a/0.") == "#show Fa/1. [true]"
        assert self.parse_with_file("#showf a/1.") == "#show Fa/2. [true]"
