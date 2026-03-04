import json
import os
import re
import subprocess
from pathlib import Path


def load_schemas(path):
    with open(path) as f:
        return json.load(f)


_approved = set()


def _check_approval(command):
    name = command.strip().split()[0] if command.strip() else ""
    if name in _approved:
        return True
    print(f"\n  Command: {command}")
    choice = input("  Allow? (y)es once / (a)lways / (n)o: ").strip().lower()
    if choice == "a":
        _approved.add(name)
        return True
    return choice == "y"


def execute(name, arguments):
    args = json.loads(arguments)

    if name == "bash":
        if not _check_approval(args["command"]):
            return "Command rejected by user."
        try:
            r = subprocess.run(
                args["command"], shell=True, capture_output=True, text=True, timeout=120
            )
            return (r.stdout + r.stderr).strip() or "(no output)"
        except subprocess.TimeoutExpired:
            return "Command timed out after 120s."

    if name == "read_file":
        try:
            with open(args["file_path"]) as f:
                return f.read()
        except Exception as e:
            return str(e)

    if name == "write_file":
        try:
            os.makedirs(os.path.dirname(args["file_path"]), exist_ok=True)
            with open(args["file_path"], "w") as f:
                f.write(args["content"])
            return f"Wrote {args['file_path']}"
        except Exception as e:
            return str(e)

    if name == "edit":
        try:
            with open(args["file_path"]) as f:
                content = f.read()
            if args["old_string"] not in content:
                return f"old_string not found in {args['file_path']}"
            content = content.replace(args["old_string"], args["new_string"], 1)
            with open(args["file_path"], "w") as f:
                f.write(content)
            return f"Edited {args['file_path']}"
        except Exception as e:
            return str(e)

    if name == "glob":
        try:
            root = Path(args.get("path", os.getcwd()))
            matches = sorted(str(p) for p in root.glob(args["pattern"]) if p.is_file())
            return "\n".join(matches) or "(no matches)"
        except Exception as e:
            return str(e)

    if name == "grep":
        try:
            root = Path(args.get("path", os.getcwd()))
            pattern = re.compile(args["pattern"])
            include = args.get("include")
            results = []
            files = root.rglob(include) if include else root.rglob("*")
            if root.is_file():
                files = [root]
            for fp in sorted(files):
                if not fp.is_file():
                    continue
                try:
                    for i, line in enumerate(fp.read_text().splitlines(), 1):
                        if pattern.search(line):
                            results.append(f"{fp}:{i}: {line}")
                except (UnicodeDecodeError, PermissionError):
                    continue
            return "\n".join(results[:200]) or "(no matches)"
        except Exception as e:
            return str(e)

    if name == "list_files":
        try:
            return "\n".join(sorted(os.listdir(args["path"])))
        except Exception as e:
            return str(e)

    return f"Unknown tool: {name}"
