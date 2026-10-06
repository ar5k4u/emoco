import os

root_dir = 'src'

for root, dirs, files in os.walk(root_dir):
    for file in files:
        if not file.endswith('.py'): continue
        
        filepath = os.path.join(root, file)
        
        with open(filepath, 'r') as f:
            lines = f.readlines()
        
        new_lines = []
        modified = False
        
        for line in lines:
            # Check if it's a typing import containing override
            if line.strip().startswith('from typing import') and 'override' in line:
                # Naive parsing, assuming comma separated on one line for now (most files adhere to this)
                prefix, imports_part = line.split('import', 1)
                
                # Split imports
                imports = [x.strip() for x in imports_part.strip().split(',')]
                
                if 'override' in imports:
                    imports.remove('override')
                    modified = True
                    
                    # Reconstruct the line without override
                    if imports:
                        new_lines.append(f"{prefix}import {', '.join(imports)}\n")
                    
                    # Add the compat block
                    new_lines.append("try:\n    from typing import override\nexcept ImportError:\n    from typing_extensions import override\n")
                else:
                    new_lines.append(line)
            else:
                new_lines.append(line)
        
        if modified:
            with open(filepath, 'w') as f:
                f.writelines(new_lines)
            print(f"Fixed {filepath}")
