# nasm_embed.py

def extract_nasm_blocks(code):
    blocks = []
    inside = False
    current = []
    for line in code.splitlines():
        if "--nasm-start" in line:
            inside = True
            continue
        if "--nasm-end" in line:
            inside = False
            blocks.append("\n".join(current))
            current = []
            continue
        if inside:
            current.append(line)
    return blocks
