# html_embed.py

def inline_html_blocks(code):
    blocks = []
    if "<html>" in code:
        start = code.find("<html>")
        end = code.find("</html>") + 7
        blocks.append(code[start:end])
    return blocks
