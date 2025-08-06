import os

def print_structure(root_dir, prefix=''):
    items = sorted([item for item in os.listdir(root_dir) if item not in ('.', '..')])
    output = []
    for index, item in enumerate(items):
        path = os.path.join(root_dir, item)
        is_last = index == len(items) - 1
        connector = '└── ' if is_last else '├── '
        output.append(f"{prefix}{connector}{item}")
        if os.path.isdir(path):
            extension = '    ' if is_last else '│   '
            output.extend(print_structure(path, prefix + extension))
    return output

if __name__ == "__main__":
    root = os.getcwd()
    project_name = os.path.basename(root)
    lines = [f"{project_name}/"]
    lines.extend(print_structure(root))
    
    with open("structure.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    
    print("Структура проекта сохранена в structure.txt")
