import logging
import concurrent.futures
from typing import Any, Dict, List, Optional
import pymupdf as fitz

logger = logging.getLogger(__name__)

DOCLING_TIMEOUT_SECONDS = 15
_docling_converter = None
_docling_available = None


def _table_grid_to_markdown(grid: List[List[Any]]) -> Optional[str]:
    """Converts a raw table cell grid into a clean Markdown table string."""
    if not grid or len(grid) < 2:
        return None
    cleaned = []
    for row in grid:
        cleaned_row = [str(c or "").strip().replace("\n", " ") for c in row]
        if any(cleaned_row):
            cleaned.append(cleaned_row)
    if len(cleaned) < 2:
        return None
    max_cols = max(len(r) for r in cleaned)
    if max_cols < 2:
        return None
    # Ensure table contains at least one quantitative or alphanumeric figure
    has_content = any(any(char.isdigit() for char in cell) for row in cleaned for cell in row)
    if not has_content:
        return None

    norm_rows = [r + [""] * (max_cols - len(r)) for r in cleaned]
    header = norm_rows[0]
    sep = ["---"] * max_cols
    lines = ["| " + " | ".join(header) + " |", "| " + " | ".join(sep) + " |"]
    for r in norm_rows[1:]:
        lines.append("| " + " | ".join(r) + " |")
    return "\n".join(lines)


def _parse_with_pymupdf(file_path: str, fallback_reason: str = None) -> Dict[str, Any]:
    """Fast parser using PyMuPDF with table detection converting to explicit Markdown tables."""
    try:
        doc = fitz.open(file_path)
    except Exception as e:
        logger.error(f"PyMuPDF failed to open {file_path}: {e}")
        return {
            "page_count": 1,
            "parser_used": "pymupdf_error",
            "fallback_reason": str(e),
            "pages": [{
                "page_number": 1,
                "text": f"Document parsing failed: {str(e)}",
                "tables": []
            }]
        }

    try:
        page_count = len(doc)
        pages_to_parse = min(page_count, 25)
        pages: List[Dict[str, Any]] = []

        for page_idx in range(pages_to_parse):
            page = doc[page_idx]
            text = page.get_text("text").strip()

            # Extract tables if available via PyMuPDF find_tables and format to Markdown
            tables: List[str] = []
            try:
                tab_finder = page.find_tables()
                for tab in tab_finder:
                    md_table = _table_grid_to_markdown(tab.extract())
                    if md_table:
                        tables.append(md_table)
            except Exception as ex:
                logger.debug(f"Table finder exception on p.{page_idx+1}: {ex}")

            # Append structured markdown tables to page text for downstream extraction
            combined_text = text
            if tables:
                table_block = f"\n\n[DATA TABLES ON PAGE {page_idx + 1}]\n" + "\n\n".join(tables)
                combined_text = f"{combined_text}\n{table_block}" if combined_text else table_block

            pages.append({
                "page_number": page_idx + 1,
                "text": combined_text,
                "tables": tables
            })

        result = {
            "page_count": max(1, page_count),
            "parser_used": "pymupdf",
            "pages": pages
        }
        if fallback_reason:
            result["fallback_reason"] = fallback_reason
        return result
    finally:
        doc.close()


def _get_docling_converter():
    global _docling_converter, _docling_available
    if _docling_available is False:
        return None
    if _docling_converter is None:
        try:
            from docling.document_converter import DocumentConverter, PdfFormatOption
            from docling.datamodel.pipeline_options import PdfPipelineOptions
            from docling.datamodel.base_models import InputFormat

            pipeline_options = PdfPipelineOptions()
            pipeline_options.do_ocr = False
            pipeline_options.do_table_structure = True

            _docling_converter = DocumentConverter(
                format_options={
                    InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
                }
            )
        except Exception as e:
            logger.warning(f"Docling initialization failed: {e}. PyMuPDF will be used.")
            _docling_available = False
            return None
    return _docling_converter


def _run_docling(file_path: str, total_pages: int) -> Dict[str, Any]:
    """Executes Docling layout parsing with page bounds handling."""
    converter = _get_docling_converter()
    if not converter:
        return _parse_with_pymupdf(file_path, fallback_reason="Docling unavailable")

    conv_result = converter.convert(file_path)
    doc = conv_result.document

    page_count = len(doc.pages) if hasattr(doc, "pages") and doc.pages else total_pages
    if page_count == 0:
        page_count = total_pages

    pages_dict: Dict[int, Dict[str, Any]] = {
        p: {"page_number": p, "text": "", "tables": []}
        for p in range(1, page_count + 1)
    }

    # Extract structured text items with provenance page numbers
    if hasattr(doc, "texts"):
        for text_item in doc.texts:
            page_no = 1
            if hasattr(text_item, "prov") and text_item.prov:
                page_no = getattr(text_item.prov[0], "page_no", 1)
            item_text = getattr(text_item, "text", "")
            if page_no in pages_dict and item_text:
                if pages_dict[page_no]["text"]:
                    pages_dict[page_no]["text"] += "\n" + item_text
                else:
                    pages_dict[page_no]["text"] = item_text

    # Extract tables if structured in Docling document
    if hasattr(doc, "tables"):
        for table_item in doc.tables:
            page_no = 1
            if hasattr(table_item, "prov") and table_item.prov:
                page_no = getattr(table_item.prov[0], "page_no", 1)

            table_md = ""
            if hasattr(table_item, "export_to_markdown"):
                table_md = table_item.export_to_markdown()
            elif hasattr(table_item, "text"):
                table_md = table_item.text

            if page_no in pages_dict and table_md:
                pages_dict[page_no]["tables"].append(table_md)

    # If pages extracted have no text, export markdown or fallback
    has_any_text = any(p["text"] for p in pages_dict.values())
    if not has_any_text:
        if hasattr(doc, "export_to_markdown"):
            full_md = doc.export_to_markdown()
            if full_md and page_count > 0:
                pages_dict[1]["text"] = full_md
            else:
                return _parse_with_pymupdf(file_path)
        else:
            return _parse_with_pymupdf(file_path)

    return {
        "page_count": page_count,
        "parser_used": "docling",
        "pages": list(pages_dict.values())
    }


def parse_pdf_document(file_path: str) -> Dict[str, Any]:
    """
    Parses a PDF document with fast preliminary inspection, strict timeout on Docling,
    and high-speed PyMuPDF fallback.
    """
    global _docling_available

    # 1. Quick page count check with PyMuPDF
    total_pages = 1
    try:
        with fitz.open(file_path) as fdoc:
            total_pages = len(fdoc)
    except Exception as e:
        logger.warning(f"Failed to open PDF with PyMuPDF: {e}")
        return _parse_with_pymupdf(file_path, fallback_reason=str(e))

    # Fast path: large documents (> 25 pages) or when Docling was previously marked unavailable
    if _docling_available is False or total_pages > 25:
        return _parse_with_pymupdf(file_path, fallback_reason=f"Fast mode ({total_pages} pages)")

    # 2. Run Docling with a strict 15-second timeout
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_run_docling, file_path, total_pages)
            res = future.result(timeout=DOCLING_TIMEOUT_SECONDS)
            _docling_available = True
            return res
    except Exception as exc:
        logger.warning(f"Docling parsing unavailable/failed for {file_path}: {exc}. Falling back to PyMuPDF.")
        _docling_available = False
        return _parse_with_pymupdf(file_path, fallback_reason=str(exc))
