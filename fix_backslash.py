import sys
with open(sys.argv[1], 'r') as f:
    content = f.read()

# Remove all trailing backslash+newline patterns
import re
# Remove lines that end with backslash (the sed insertion artifact)
lines = content.split('\n')
fixed = []
for line in lines:
    if line.endswith('\\') and not line.endswith('\\\\'):
        fixed.append(line.rstrip('\\'))
    else:
        fixed.append(line)

with open(sys.argv[1], 'w') as f:
    f.write('\n'.join(fixed))

import py_compile
py_compile.compile(sys.argv[1], doraise=True)
print('SYNTAX OK')
