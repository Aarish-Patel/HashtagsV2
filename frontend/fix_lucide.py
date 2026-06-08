import os
import re
import glob

def camel_to_kebab(name):
    name = re.sub('(.)([A-Z][a-z]+)', r'\1-\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1-\2', name).lower()

jsx_files = glob.glob('src/**/*.jsx', recursive=True)

import_regex = re.compile(r"import\s+\{([^}]+)\}\s+from\s+['\"]lucide-react['\"];?")

for file_path in jsx_files:
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    match = import_regex.search(content)
    if match:
        icons_str = match.group(1)
        # Parse the icons, handling 'Terminal as TerminalIcon'
        icons = [i.strip() for i in icons_str.split(',')]
        new_imports = []
        for icon in icons:
            if not icon: continue
            if ' as ' in icon:
                orig, alias = icon.split(' as ')
                orig = orig.strip()
                alias = alias.strip()
                kebab = camel_to_kebab(orig)
                new_imports.append(f"import {alias} from 'lucide-react/dist/esm/icons/{kebab}';")
            else:
                kebab = camel_to_kebab(icon)
                new_imports.append(f"import {icon} from 'lucide-react/dist/esm/icons/{kebab}';")
        
        replacement = '\n'.join(new_imports)
        new_content = content[:match.start()] + replacement + content[match.end():]
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"Fixed {file_path}")

print("Done fixing lucide-react imports!")
