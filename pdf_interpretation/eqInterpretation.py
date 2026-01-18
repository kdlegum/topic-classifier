from pix2tex.cli import LatexOCR
from PIL import Image
from pylatexenc.latex2text import LatexNodes2Text

# Load model (downloads weights on first run)

def toText(png):
    model = LatexOCR()

    converter = LatexNodes2Text()

    # Load equation image
    img = Image.open(png)

    # Run OCR
    latex = model(img)

    return converter.latex_to_text(latex)