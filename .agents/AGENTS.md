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

Game rules (the basis for the implementation):
- [`docs/rules.md`](../docs/rules.md): Core rules of GodField. Reference this when implementing game logic.
- [`docs/phase_specifications.md`](../docs/phase_specifications.md): Phase transitions, self-targeting, and turn-end resolution.
- [`docs/special_cards.md`](../docs/special_cards.md): Cards whose behaviour needs special handling.
- [`docs/dream_curse.md`](../docs/dream_curse.md): The dream state and its card groupings.

How the code is built:
- [`docs/core_architecture.md`](../docs/core_architecture.md): `InternalState`, `Observation`, `EnvPool`, and why they look the way they do.
- [`docs/rl_architecture.md`](../docs/rl_architecture.md): Observation and action layout, league training, and the diagnostic tools.
- [`docs/event_log_spec.md`](../docs/event_log_spec.md): Event history entries and when they are emitted.
- [`docs/testing_guide.md`](../docs/testing_guide.md): The declarative test DSL and RNG injection.
- [`docs/card_schema.md`](../docs/card_schema.md): The YAML/JSON structure for card definitions.

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

## Game Specification Changes & Verification Rules (Important)

When working with GodField game rules or mechanics, follow these strict guidelines:

1. **Verify Specifications with the User**: The rules of GodField are highly complex and can be updated/tweaked frequently. Avoid assuming a rule is correct based on general game mechanics or internet search results (as old wikis/blogs may contain outdated or incorrect rules). If you encounter any ambiguous or suspicious game logic/mechanics, **you MUST immediately ask the user for clarification** before proceeding to change code.
2. **Prioritize Documenting Specifications First**: Always update `docs/rules.md` (or other specification docs) when clarifying or implementing a rule.
3. **No Hallucinated Cards or Behaviors (YAML/JSON Verification)**: Never assume card names (e.g., `霧氷の鎧`) or actions exist in the codebase unless they are defined in `assets/godfield_cards.json` or YAML files. **To prevent hallucinations, you MUST search the YAML files under `assets/cards/` or check `assets/godfield_cards.json` directly to verify the exact characters, terms, and spelling before writing code or comments.** In particular, the word `買戻し` (Buyback) is a hallucination and does not exist as a card name; it must always be referred to as `買う` (Buy).

## Code Implementation Quality & Bug Prevention (Critical)

To prevent introducing regression bugs, incomplete logic, or index mismatches, every agent MUST follow these practices:

1. **Verify Data Structures and C++ Source Directly**: Never make assumptions about how lists, states, or bindings are structured (e.g. whether an observation's list is dense, sparse, or maps to hand slots). Use grep to locate the C++ implementation (`make_observation`, bindings, etc.) and check its logic directly before writing Python helper code.
2. **Establish Branch Coverage for Joint/Edge Cases**: Do not implement logic based solely on simple binary outcomes (e.g. win/lose). Consider all combinations of states (e.g. both players dying simultaneously resulting in a draw) and ensure the check order resolves joint conditions first.
3. **Write Diverse Multi-Index Tests**: When testing index-related logic (like hand slots or staged slots), do not write tests using only index `0`. Always test indices greater than `0`, multi-card selections, and various hand slot order permutations to verify that the math/matching holds up.
4. **Remind the User to Restart Daemon Processes**: When modifying server-side files (like `visualize_server.py`), explicitly instruct the developer to restart the running terminal server process, as it does not automatically hot-reload in this codebase.
