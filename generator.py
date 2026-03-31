#!/usr/bin/env python3
import sys
import ipaddress
from pathlib import Path

class Config:
    # Список атрибутов для фильтрации (например, ['cn', '!ads'])
    # Если пусто — включаем всё (кроме того, что явно исключено через @!)
    ATTRIBUTES = ['!ads']

def is_ip_or_cidr(value):
    try:
        ipaddress.ip_network(value, strict=False)
        return True
    except ValueError:
        return False


def match_type(value, mode):
    if mode == "ipset":
        return is_ip_or_cidr(value)
    elif mode == "hostlist":
        return not is_ip_or_cidr(value)
    return False


def check_attributes(attrs, inherited_attrs):
    attrs = set(attrs) | set(inherited_attrs)

    if Config.ATTRIBUTES:
        is_excluded = any(
            f"!{target.lstrip('!')}" in attrs
            for target in Config.ATTRIBUTES
        )
        if is_excluded:
            return False

        if attrs:
            has_inclusion = any(
                target.lstrip('!') in attrs
                for target in Config.ATTRIBUTES
                if not target.startswith('!')
            )
            if any(not t.startswith('!') for t in Config.ATTRIBUTES):
                if not has_inclusion:
                    return False

    return True

def parse_list(file_input, data_dir, result_set, visited, mode, inherited_attrs=None):
    if inherited_attrs is None:
        inherited_attrs = []

    if isinstance(file_input, Path):
        file_path = file_input
        file_id = file_input.name
    else:
        file_path = data_dir / file_input
        file_id = file_input

    if file_id in visited:
        return
    visited.add(file_id)

    if not file_path.exists():
        print(f"Warning: File `{file_path}` not found.")
        return

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for row, line in enumerate(f, start=1):
                line = line.split('#')[0].strip()
                if not line:
                    continue

                if line.startswith('include:'):
                    parts = line.split()
                    include_name = parts[0].split(':', 1)[1]
                    include_attrs = [p.lstrip('@') for p in parts[1:] if p.startswith('@')]

                    parse_list(
                        include_name,
                        data_dir,
                        result_set,
                        visited,
                        mode,
                        include_attrs # inherited_attrs + include_attrs
                    )
                    continue

                if line.startswith('regexp:'):
                    print(f"Warning: Skipping regexp in '{file_path}:{row}'") # Not support
                    continue

                parts = line.split()
                raw_value = parts[0]
                attrs = [p.lstrip('@') for p in parts[1:] if p.startswith('@')]

                if not check_attributes(attrs, inherited_attrs):
                    continue

                if raw_value.startswith('full:'):
                    final_value = raw_value.split(':', 1)[1].strip()
                else:
                    final_value = raw_value

                if final_value and match_type(final_value, mode):
                    result_set.add(final_value)

    except Exception as e:
        print(f"Error reading `{file_path}`: {e}")

def run(mode: str, input_file: str, output_file: str):
    if mode not in ("hostlist", "ipset"):
        raise ValueError("mode must be 'hostlist' or 'ipset'")

    input_path = Path(input_file)
    output_path = Path(output_file)

    data_directory = Path(f"./data/{mode}")

    if not data_directory.is_dir():
        raise FileNotFoundError(f"Directory `{data_directory}` not found.")

    result = set()
    visited = set()

    print(f"Starting build from file: {input_path}")
    parse_list(input_path, data_directory, result, visited, mode)

    with open(output_path, 'w', encoding='utf-8') as f:
        for item in sorted(result):
            f.write(f"{item}\n")

    print(f"Done! Total: {len(result)}")
    print(f"Saved to: {output_path}")

def main():
    import sys

    if len(sys.argv) != 4:
        print("Usage: script.py <mode: hostlist|ipset> <input_file> <output_file>")
        return

    run(sys.argv[1], sys.argv[2], sys.argv[3])


if __name__ == "__main__":
    main()