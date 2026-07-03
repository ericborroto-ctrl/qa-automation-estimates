# Tools

This directory contains Python scripts that handle deterministic execution tasks.

## Purpose

Tools are the execution layer of the WAT framework. They handle:
- API calls
- Data transformations
- File operations
- Database queries
- Web scraping
- Cloud service integrations

## Guidelines

### Creating Tools

1. **One purpose per script**: Each tool should do one thing well
2. **Accept parameters**: Use command-line arguments or function parameters
3. **Error handling**: Return clear error messages
4. **Credentials**: Always use `.env` for API keys and secrets
5. **Output**: Return structured data or write to `.tmp/` for intermediate files

### Example Script Structure

```python
#!/usr/bin/env python3
import os
from dotenv import load_dotenv

load_dotenv()

def main():
    """
    Tool description
    """
    # Your implementation here
    pass

if __name__ == "__main__":
    main()
```

### Common Dependencies

Tools commonly use:
- `python-dotenv`: Environment variable management
- `requests`: API calls
- `pandas`: Data manipulation
- `gspread`: Google Sheets integration
- `beautifulsoup4`: Web scraping

## Testing

Test your tools independently before integrating into workflows:

```bash
python tools/your_script.py --arg value
```

## Best Practices

- Make tools idempotent when possible
- Log important steps for debugging
- Handle rate limits gracefully
- Validate inputs before processing
- Return meaningful exit codes
