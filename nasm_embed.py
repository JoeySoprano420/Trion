-- nasm_embed.py

-- Extracts inline NASM blocks from Trion source code
-- between --nasm-start and --nasm-end markers

def extract_nasm_blocks(code):
    blocks = []          -- Collected NASM blocks
    inside = False       -- State: inside a NASM block
    current = []         -- Lines of current NASM block

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
