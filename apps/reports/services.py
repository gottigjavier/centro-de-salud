"""CSV export services for reports module."""
import csv

from django.http import StreamingHttpResponse


class Echo:
    """An object that implements just the write method of the file-like interface.

    Used to stream CSV data without buffering the entire file in memory.
    """

    def write(self, value):
        return value


def csv_response(rows, headers, filename):
    """Generate StreamingHttpResponse with CSV content.

    Includes UTF-8 BOM for Excel compatibility with Spanish characters (ñ, tildes).

    Args:
        rows: List of lists, each inner list is a CSV row.
        headers: List of column header strings.
        filename: Download filename (e.g. "profesionales_2026-01-01_2026-01-31.csv").

    Returns:
        StreamingHttpResponse with CSV content.
    """

    def generate():
        # BOM for Excel to recognize UTF-8
        yield "\ufeff"
        writer = csv.writer(Echo())
        yield writer.writerow(headers)
        for row in rows:
            yield writer.writerow(row)

    response = StreamingHttpResponse(generate(), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response
