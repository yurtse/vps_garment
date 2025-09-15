import os

def print_tree(start_path, prefix=""):
    files = []
    dirs = []
    try:
        for entry in os.listdir(start_path):
            full_path = os.path.join(start_path, entry)
            if os.path.isdir(full_path):
                dirs.append(entry)
            else:
                files.append(entry)
    except PermissionError:
        return

    # Print directories first
    for i, d in enumerate(sorted(dirs)):
        connector = "└── " if i == len(dirs)-1 and not files else "├── "
        print(prefix + connector + d + "/")
        new_prefix = prefix + ("    " if i == len(dirs)-1 and not files else "│   ")
        print_tree(os.path.join(start_path, d), new_prefix)

    # Print files
    for i, f in enumerate(sorted(files)):
        connector = "└── " if i == len(files)-1 else "├── "
        print(prefix + connector + f)


if __name__ == "__main__":
    print_tree(".")
