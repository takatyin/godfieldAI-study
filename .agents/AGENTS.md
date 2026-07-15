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
