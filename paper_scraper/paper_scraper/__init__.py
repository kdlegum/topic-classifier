# Past paper scraper package (AQA, Edexcel, OCR)

from datetime import date


def compute_max_year() -> int:
    """Returns the latest year whose papers are safe to include.

    Before 1 Sep of the current year the current sitting's papers aren't yet
    released, so we cap at last year.  On or after 1 Sep they're out.
    """
    today = date.today()
    if today >= date(today.year, 9, 1):
        return today.year
    return today.year - 1
