import sysconfig
import os

def main():
    project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # Try to locate pybind11 include directory dynamically
    pybind11_include = os.path.join(project_dir, ".venv", "Lib", "site-packages", "pybind11", "include")
    if not os.path.exists(pybind11_include):
        try:
            import pybind11
            pybind11_include = pybind11.get_include()
        except ImportError:
            # Fallback path if not installed yet
            pass

    python_include = sysconfig.get_path("include")
    
    flags = [
        "-xc++",
        "-std=c++17",
        "-Igodfield_core/src",
        f"-I{pybind11_include}",
        f"-I{python_include}"
    ]
    
    flags_path = os.path.join(project_dir, "compile_flags.txt")
    with open(flags_path, "w", encoding="utf-8") as f:
        for flag in flags:
            f.write(flag + "\n")
            
    print(f"Generated compile_flags.txt at {flags_path}")

if __name__ == "__main__":
    main()
