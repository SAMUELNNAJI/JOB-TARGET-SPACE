"""Print a slice of website/models.py with line numbers (read helper)."""
import sys

start = int(sys.argv[1]) if len(sys.argv) > 1 else 1
end = int(sys.argv[2]) if len(sys.argv) > 2 else 200

with open("website/models.py", encoding="utf-8") as fh:
    lines = fh.readlines()

for i in range(start - 1, min(end, len(lines))):
    print("%4d| %s" % (i + 1, lines[i].rstrip("\n")))
print("TOTAL_LINES=%d" % len(lines))
