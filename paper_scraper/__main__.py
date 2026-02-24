"""
Unified paper scraper entry point.

Usage (run from project root):
    python -m paper_scraper --board {aqa,edexcel,ocr} [board-specific options...]

    --board aqa       Scrape AQA past papers
    --board edexcel   Scrape Edexcel / Pearson past papers
    --board ocr       Scrape OCR past papers

All remaining arguments are forwarded to the board-specific scraper.
Run with `--board aqa --help` or `--board edexcel --help` or `--board ocr --help` for board-specific options.
"""

import sys


def main():
    if "--board" not in sys.argv:
        print("Usage: python -m paper_scraper --board {aqa,edexcel,ocr} [options]")
        print("  --board aqa      Scrape AQA past papers")
        print("  --board edexcel  Scrape Edexcel / Pearson past papers")
        print("  --board ocr      Scrape OCR past papers")
        sys.exit(1)

    idx = sys.argv.index("--board")
    if idx + 1 >= len(sys.argv):
        print("Error: --board requires a value (aqa, edexcel, or ocr)")
        sys.exit(1)

    board = sys.argv[idx + 1].lower()
    # Remove --board <value> from argv so the board's own argparse doesn't see it
    sys.argv = sys.argv[:idx] + sys.argv[idx + 2:]

    if board == "aqa":
        from paper_scraper.aqa_scraper import main as _main
        _main()
    elif board == "edexcel":
        from paper_scraper.edexcel_scraper import main as _main
        _main()
    elif board == "ocr":
        from paper_scraper.ocr_scraper import main as _main
        _main()
    else:
        print(f"Unknown board: {board!r}. Available boards: aqa, edexcel, ocr")
        sys.exit(1)


main()
