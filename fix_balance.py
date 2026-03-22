with open('scripts/polymarket-exec.py', 'r') as f:
    text = f.read()

import re
old_balance = re.search(r'@app\.get\("/balance"\).*?return.*?\}', text, re.DOTALL)

# Let me use multi_replace_file_content instead of regex to be safe.
