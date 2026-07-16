# Project-Scoped Rules and Agent Guidelines

## Web Scraping & Data Fetching (Windows Environment)

When you need to fetch information from URLs (e.g., Japanese wikis or攻略 sites) in this project, **avoid using `curl` directly from PowerShell** as it frequently leads to 403 Forbidden errors (due to basic bot protection like Cloudflare) or severe UTF-8 Mojibake (character encoding issues) on Windows.

Instead, always write a temporary Python script and use `urllib.request` with a standard `User-Agent`, and process the DOM using `BeautifulSoup`. 
When saving the extracted data for yourself to read, output it to a JSON file using `ensure_ascii=False` so that Japanese characters are preserved correctly.

### Recommended Python Snippet for Scraping

```python
import urllib.request
from bs4 import BeautifulSoup
import json

def fetch_page_data():
    url = "TARGET_URL_HERE"
    
    # 1. Provide a User-Agent to bypass simple 403 Forbidden checks
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    })
    
    try:
        with urllib.request.urlopen(req) as res:
            # 2. Decode explicitly as utf-8
            html = res.read().decode('utf-8')
    except Exception as e:
        print(f"Failed to fetch {url}: {e}")
        return

    soup = BeautifulSoup(html, 'html.parser')
    
    # Example: Extract table data
    items = []
    # ... DOM parsing logic ...
    
    # 3. Output as JSON with ensure_ascii=False to avoid \uXXXX encoding on Windows
    with open('scratch/output.json', 'w', encoding='utf-8') as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    
    print("Data successfully saved to scratch/output.json")

if __name__ == "__main__":
    fetch_page_data()
```

### Key Takeaways for Future Agents
- **Do not use `curl` or `Invoke-WebRequest`** for complex Japanese sites. 
- **Always specify `encoding='utf-8'`** when opening files for reading or writing.
- **Use `ensure_ascii=False`** with `json.dump` to prevent Japanese characters from turning into Unicode escape sequences, which are hard for LLMs to read natively from files.
- Place all temporary scripts in the `scratch/` directory and remove them once the data extraction is completed.

## Card Data Management

The godfield card data is managed in YAML files under [`assets/cards/`](../assets/cards/).
When modifying or adding cards, you MUST follow this workflow:

1. Edit the relevant YAML file in `assets/cards/`.
2. Run the build script [`tools/build_cards.py`](../tools/build_cards.py) to generate the consolidated `assets/godfield_cards.json`.
3. Run the validation script [`tools/validate_cards.py`](../tools/validate_cards.py) to ensure the data schema and rules are strictly followed.

**Do NOT directly edit `assets/godfield_cards.json`**, as it is an auto-generated build artifact. Always modify the source YAML files and rebuild.

## Repository Structure & Documentation References

When exploring the codebase or looking for specific game mechanics, refer to these directories and documents:

### `docs/` (System Documentation)
- [`docs/rules.md`](../docs/rules.md): Contains the core rules of GodField. Reference this when implementing game logic.
- [`docs/game_flow.md`](../docs/game_flow.md): Outlines the turn sequence and phases. Reference this when managing game states and timing.
- [`docs/card_schema.md`](../docs/card_schema.md): Explains the technical JSON/YAML structure for card definitions.
- [`docs/ai-policy.md`](../docs/ai-policy.md): Outlines the goals and structure for the RL agent.

### `assets/` (Game Data)
- [`assets/cards/`](../assets/cards/): Contains the master YAML definitions for all game cards.
- `assets/godfield_cards.json`: The auto-generated artifact from the YAML files. NEVER edit this manually.

## Python & PowerShell Encoding on Windows (Important)

When executing Python scripts or commands from the Windows PowerShell environment, the console or default file encoding may fall back to `Shift-JIS (CP932)`. This will cause severe Mojibake (character corruption) when parsing files or outputs containing Japanese characters (e.g., `"火"`).

**Guidelines to prevent encoding issues:**
1. **Always specify `encoding='utf-8'`** explicitly in all Python file I/O operations (`open(..., encoding='utf-8')`).
2. **Never use PowerShell redirection (`>` or `>>`) or `echo` / `cat`** to write files containing Japanese text. PowerShell will often save them in UTF-16 or Shift-JIS, breaking the build or tests. Instead, always use the `write_to_file` or `replace_file_content` tools, or write a temporary Python script to perform the I/O.
3. If test cases fail with string matching errors (like `` not matching expected text) or `UnicodeDecodeError`, it is highly likely that a file was saved in the wrong encoding or read without `encoding='utf-8'`. 

# Project-Scoped Rules and Agent Guidelines

## Web Scraping & Data Fetching (Windows Environment)

When you need to fetch information from URLs (e.g., Japanese wikis or攻略 sites) in this project, **avoid using `curl` directly from PowerShell** as it frequently leads to 403 Forbidden errors (due to basic bot protection like Cloudflare) or severe UTF-8 Mojibake (character encoding issues) on Windows.

Instead, always write a temporary Python script and use `urllib.request` with a standard `User-Agent`, and process the DOM using `BeautifulSoup`. 
When saving the extracted data for yourself to read, output it to a JSON file using `ensure_ascii=False` so that Japanese characters are preserved correctly.

### Recommended Python Snippet for Scraping

```python
import urllib.request
from bs4 import BeautifulSoup
import json

def fetch_page_data():
    url = "TARGET_URL_HERE"
    
    # 1. Provide a User-Agent to bypass simple 403 Forbidden checks
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    })
    
    try:
        with urllib.request.urlopen(req) as res:
            # 2. Decode explicitly as utf-8
            html = res.read().decode('utf-8')
    except Exception as e:
        print(f"Failed to fetch {url}: {e}")
        return

    soup = BeautifulSoup(html, 'html.parser')
    
    # Example: Extract table data
    items = []
    # ... DOM parsing logic ...
    
    # 3. Output as JSON with ensure_ascii=False to avoid \uXXXX encoding on Windows
    with open('scratch/output.json', 'w', encoding='utf-8') as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    
    print("Data successfully saved to scratch/output.json")

if __name__ == "__main__":
    fetch_page_data()
```

### Key Takeaways for Future Agents
- **Do not use `curl` or `Invoke-WebRequest`** for complex Japanese sites. 
- **Always specify `encoding='utf-8'`** when opening files for reading or writing.
- **Use `ensure_ascii=False`** with `json.dump` to prevent Japanese characters from turning into Unicode escape sequences, which are hard for LLMs to read natively from files.
- Place all temporary scripts in the `scratch/` directory and remove them once the data extraction is completed.

## Card Data Management

The godfield card data is managed in YAML files under [`assets/cards/`](../assets/cards/).
When modifying or adding cards, you MUST follow this workflow:

1. Edit the relevant YAML file in `assets/cards/`.
2. Run the build script [`tools/build_cards.py`](../tools/build_cards.py) to generate the consolidated `assets/godfield_cards.json`.
3. Run the validation script [`tools/validate_cards.py`](../tools/validate_cards.py) to ensure the data schema and rules are strictly followed.

**Do NOT directly edit `assets/godfield_cards.json`**, as it is an auto-generated build artifact. Always modify the source YAML files and rebuild.

## Repository Structure & Documentation References

When exploring the codebase or looking for specific game mechanics, refer to these directories and documents:

### `docs/` (System Documentation)
- [`docs/rules.md`](../docs/rules.md): Contains the core rules of GodField. Reference this when implementing game logic.
- [`docs/game_flow.md`](../docs/game_flow.md): Outlines the turn sequence and phases. Reference this when managing game states and timing.
- [`docs/card_schema.md`](../docs/card_schema.md): Explains the technical JSON/YAML structure for card definitions.
- [`docs/ai-policy.md`](../docs/ai-policy.md): Outlines the goals and structure for the RL agent.

### `assets/` (Game Data)
- [`assets/cards/`](../assets/cards/): Contains the master YAML definitions for all game cards.
- `assets/godfield_cards.json`: The auto-generated artifact from the YAML files. NEVER edit this manually.

## Python & PowerShell Encoding on Windows (Important)

When executing Python scripts or commands from the Windows PowerShell environment, the console or default file encoding may fall back to `Shift-JIS (CP932)`. This will cause severe Mojibake (character corruption) when parsing files or outputs containing Japanese characters (e.g., `"火"`).

**Guidelines to prevent encoding issues:**
1. **Always specify `encoding='utf-8'`** explicitly in all Python file I/O operations (`open(..., encoding='utf-8')`).
2. **Never use PowerShell redirection (`>` or `>>`) or `echo` / `cat`** to write files containing Japanese text. PowerShell will often save them in UTF-16 or Shift-JIS, breaking the build or tests. Instead, always use the `write_to_file` or `replace_file_content` tools, or write a temporary Python script to perform the I/O.
3. If test cases fail with string matching errors (like `` not matching expected text) or `UnicodeDecodeError`, it is highly likely that a file was saved in the wrong encoding or read without `encoding='utf-8'`. 

## Updating C++ Binding Type Stubs (`.pyi`)

The game core (`godfield_core`) is written in C++ and exposed to Python via pybind11. IDEs and type-checkers cannot natively read types from the compiled `.pyd` binary. We use `pybind11-stubgen` to generate a `.pyi` stub file so the developer gets full auto-completion and type safety.

**Whenever you modify the C++ source files (`.cpp`/`.h`) and rebuild the package**, you MUST regenerate the type stubs to reflect the new API:

```powershell
# Generate the stubs directly into the godfield_core-stubs directory
.\.venv\Scripts\pybind11-stubgen.exe -o . --root-suffix="-stubs" godfield_core
```

**Why use `godfield_core-stubs`?**
If a C++ source folder shares the same name as the Python module (`godfield_core`), Pylance treats the folder as a namespace package and ignores `.pyi` files placed in the project root. By using a PEP 561 compliant stub-only package directory (`godfield_core-stubs/__init__.pyi`), we bypass this namespace shadowing issue completely without mixing Python stubs into the C++ source directory.
