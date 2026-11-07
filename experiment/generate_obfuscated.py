from pathlib import Path
import ast
import csv
import json
import shutil


MANIFEST = Path("experiment/selected_60_final.csv")
ORIGINAL = Path("experiment/dataset_final/original")
OBFUSCATED = Path("experiment/dataset_final/obfuscated")


class ScopeVisitor(ast.NodeVisitor):
    """Percorre somente o corpo da função atual, sem entrar em novos escopos."""

    def __init__(self, root):
        self.root = root
        self.names = []

    def visit_FunctionDef(self, node):
        if node is self.root:
            for stmt in node.body:
                self.visit(stmt)
        # função aninhada = outro escopo

    def visit_AsyncFunctionDef(self, node):
        if node is self.root:
            for stmt in node.body:
                self.visit(stmt)

    def visit_ClassDef(self, node):
        pass

    def visit_Lambda(self, node):
        pass

    def visit_Name(self, node):
        self.names.append(node)


def keyword_names_used_by_tests(ans_dir):
    """
    Se algum teste chamar uma função com argumento nomeado:
        foo(value=...)
    preservamos esse parâmetro para não quebrar a API do teste.
    """
    preserved = set()

    for path in ans_dir.glob("input_*.txt"):
        try:
            tree = ast.parse(path.read_text(), mode="eval")
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.keyword) and node.arg:
                preserved.add(node.arg)

    return preserved


def all_identifiers(tree):
    result = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            result.add(node.id)
        elif isinstance(node, ast.arg):
            result.add(node.arg)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            result.add(node.name)
        elif isinstance(node, ast.ClassDef):
            result.add(node.name)

    return result


def nested_scope_references(root):
    """
    Nomes usados dentro de funções/classes/lambdas aninhadas.

    Se um nome local da função externa aparecer em um escopo interno,
    nós o preservamos para não quebrar closures.
    """
    refs = set()

    class Visitor(ast.NodeVisitor):
        def visit_FunctionDef(self, node):
            if node is root:
                for stmt in node.body:
                    self.visit(stmt)
                return

            for sub in ast.walk(node):
                if isinstance(sub, ast.Name):
                    refs.add(sub.id)

            # não desce novamente: ast.walk já cobriu esse escopo

        def visit_AsyncFunctionDef(self, node):
            if node is root:
                for stmt in node.body:
                    self.visit(stmt)
                return

            for sub in ast.walk(node):
                if isinstance(sub, ast.Name):
                    refs.add(sub.id)

        def visit_Lambda(self, node):
            for sub in ast.walk(node):
                if isinstance(sub, ast.Name):
                    refs.add(sub.id)

        def visit_ClassDef(self, node):
            for sub in ast.walk(node):
                if isinstance(sub, ast.Name):
                    refs.add(sub.id)

    Visitor().visit(root)
    return refs


def obfuscate(source_path, ans_dir):
    raw = source_path.read_bytes()
    source = raw.decode("utf-8")
    tree = ast.parse(source)

    preserved = {"self", "cls"}
    preserved |= keyword_names_used_by_tests(ans_dir)

    existing = all_identifiers(tree)

    # offsets absolutos em bytes por linha.
    lines = raw.splitlines(keepends=True)
    line_offsets = []
    offset = 0

    for line in lines:
        line_offsets.append(offset)
        offset += len(line)

    replacements = []
    mapping_report = []

    functions = [
        n for n in ast.walk(tree)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]

    for fn in functions:
        visitor = ScopeVisitor(fn)
        visitor.visit(fn)

        occurrences = visitor.names

        # Variáveis externas usadas por closures/escopos internos
        # não são renomeadas nesta transformação conservadora.
        fn_preserved = preserved | nested_scope_references(fn)

        # Argumentos da função atual.
        args = (
            list(fn.args.posonlyargs)
            + list(fn.args.args)
            + list(fn.args.kwonlyargs)
        )

        if fn.args.vararg:
            args.append(fn.args.vararg)
        if fn.args.kwarg:
            args.append(fn.args.kwarg)

        # Nomes que realmente são locais deste escopo:
        # parâmetros + nomes escritos (Store).
        binding_positions = {}

        for arg in args:
            if arg.arg in fn_preserved:
                continue
            binding_positions.setdefault(
                arg.arg,
                (arg.lineno, arg.col_offset)
            )

        for node in occurrences:
            if isinstance(node.ctx, ast.Store):
                if node.id in fn_preserved:
                    continue

                binding_positions.setdefault(
                    node.id,
                    (node.lineno, node.col_offset)
                )

        # ordem de primeira ocorrência = mapeamento determinístico
        ordered = sorted(
            binding_positions,
            key=lambda name: binding_positions[name]
        )

        local_mapping = {}

        counter = 1

        for old in ordered:
            while True:
                new = f"v{counter:03d}"
                counter += 1

                if new not in existing and new not in local_mapping.values():
                    break

            local_mapping[old] = new

        # parâmetros
        for arg in args:
            if arg.arg not in local_mapping:
                continue

            start = line_offsets[arg.lineno - 1] + arg.col_offset
            end = line_offsets[arg.end_lineno - 1] + arg.end_col_offset

            replacements.append(
                (start, end, local_mapping[arg.arg])
            )

        # todos os usos daquele local no mesmo escopo
        for node in occurrences:
            if node.id not in local_mapping:
                continue

            start = line_offsets[node.lineno - 1] + node.col_offset
            end = line_offsets[node.end_lineno - 1] + node.end_col_offset

            replacements.append(
                (start, end, local_mapping[node.id])
            )

        for old, new in local_mapping.items():
            mapping_report.append({
                "scope": fn.name,
                "original": old,
                "obfuscated": new,
            })

    # evita duplicação de posição
    unique = {}

    for start, end, new in replacements:
        unique[(start, end)] = new

    # substituições de trás para frente preservam todos os offsets
    result = raw

    for (start, end), new in sorted(
        unique.items(),
        reverse=True
    ):
        result = result[:start] + new.encode() + result[end:]

    return result, mapping_report


rows = list(csv.DictReader(MANIFEST.open()))

if OBFUSCATED.exists():
    shutil.rmtree(OBFUSCATED)

OBFUSCATED.mkdir(parents=True)

total_renames = 0

print("=== GENERATING OBFUSCATED DATASET ===")

for r in rows:
    q = r["question"]
    bug = r["bug_id"]

    src_dir = ORIGINAL / q / bug
    dst_dir = OBFUSCATED / q / bug

    shutil.copytree(src_dir, dst_dir)

    transformed, mapping = obfuscate(
        src_dir / "bug.py",
        src_dir / "ans"
    )

    (dst_dir / "bug.py").write_bytes(transformed)

    (dst_dir / "identifier_mapping.json").write_text(
        json.dumps(mapping, indent=2),
        encoding="utf-8"
    )

    total_renames += len(mapping)

    print(
        f"{bug:<18} {q:<11} "
        f"renamed={len(mapping):2}"
    )

print()
print(f"CASES: {len(rows)}")
print(f"TOTAL RENAMED IDENTIFIERS: {total_renames}")
print(f"OUTPUT: {OBFUSCATED}")
