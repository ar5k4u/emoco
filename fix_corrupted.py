#!/usr/bin/env python3
"""
Fix corrupted try blocks in source files.
The previous fix_imports.py script corrupted files by creating nested try blocks like:
try:
try:
try:
    from typing import override
except ImportError:
    from typing_extensions import override
except ImportError:
    from typing_extensions import override
except ImportError:
    from typing_extensions import override

This script fixes them back to the correct format:
try:
    from typing import override
except ImportError:
    from typing_extensions import override
"""

import os
import re

root_dir = 'src'

# Pattern to match corrupted try blocks
# Matches: multiple try: followed by from typing import override with multiple except blocks
corrupted_pattern = re.compile(
    r'(try:\n)+(try:\n    from typing import override\nexcept ImportError:\n    from typing_extensions import override\n)(except ImportError:\n    from typing_extensions import override\n)+',
    re.MULTILINE
)

replacement = '''try:
    from typing import override
except ImportError:
    from typing_extensions import override
'''

fixed_count = 0

for root, dirs, files in os.walk(root_dir):
    for file in files:
        if not file.endswith('.py'):
            continue
        
        filepath = os.path.join(root, file)
        
        with open(filepath, 'r') as f:
            content = f.read()
        
        # Check if file has corrupted pattern
        if corrupted_pattern.search(content):
            new_content = corrupted_pattern.sub(replacement, content)
            
            with open(filepath, 'w') as f:
                f.write(new_content)
            
            print(f"Fixed {filepath}")
            fixed_count += 1

print(f"\nTotal files fixed: {fixed_count}")
