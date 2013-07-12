
def format_anchor(s):
    return s.lower().replace(' ', '-').replace('\n', '-').replace('~', '').replace('_', '-')

def dedent(code):
    lines = code.split("\n")
    lines2 = [line for line in lines if line]
    nspaces = len(lines2[0]) - len(lines2[0].lstrip())
    return "\n".join([line[nspaces:] for line in lines])
