import os

def export_project_filtered(root_dir: str, output_file: str = "project_dump_small.txt"):
    include_ext = {".py", ".json"}

    lines = []

    for dirpath, dirnames, filenames in os.walk(root_dir):
        # Skip noisy or irrelevant directories
        dirnames[:] = [
            d for d in dirnames
            if d not in {
                "__pycache__",
                ".git",
                "venv",
                "env",
                ".mypy_cache",
                ".idea",
                "product",        # exclude /product
                "node_modules",   # exclude /ui/node_modules or any node_modules
            }
        ]

        for filename in filenames:
            ext = os.path.splitext(filename)[1]
            if ext not in include_ext:
                continue

            full_path = os.path.join(dirpath, filename)
            rel_path = os.path.relpath(full_path, root_dir)

            try:
                with open(full_path, "r", encoding="utf-8") as f:
                    content = f.read()
            except Exception as e:
                content = f"[Could not read file: {e}]"

            lines.append(f"# {rel_path}\n{content}\n")

    with open(output_file, "w", encoding="utf-8") as out:
        out.write("\n".join(lines))

    print(f"Export complete → {output_file}")


if __name__ == "__main__":
    export_project_filtered(".")