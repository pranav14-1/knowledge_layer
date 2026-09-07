import logging
from typing import Any, Dict, List
import pymupdf as fitz

logger = logging.getLogger(__name__)


def _parse_with_pymupdf(file_path: str) -> Dict[str, Any]:
    """Fallback parser using PyMuPDF to extract text and tables page-by-page."""
    doc = fitz.open(file_path)
    page_count = len(doc)
    pages: List[Dict[str, Any]] = []

    for page_idx in range(page_count):
        page = doc[page_idx]
        text = page.get_text("text")
        
        # Extract tables if available via PyMuPDF find_tables
        tables = []
        try:
            tab_finder = page.find_tables()
            for tab in tab_finder:
                tables.append(tab.extract())
        except Exception:
            pass

        pages.append({
            "page_number": page_idx + 1,
            "text": text.strip(),
            "tables": tables
        })

    doc.close()

    return {
        "page_count": page_count,
        "parser_used": "pymupdf",
        "pages": pages
    }

_docling_converter = None


def _get_docling_converter():
    global _docling_converter
    if _docling_converter is None:
        from docling.document_converter import DocumentConverter, PdfFormatOption
        from docling.datamodel.pipeline_options import PdfPipelineOptions
        from docling.datamodel.base_models import InputFormat

        pipeline_options = PdfPipelineOptions()
        pipeline_options.do_ocr = False

        _docling_converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
            }
        )
    return _docling_converter


def parse_pdf_document(file_path: str) -> Dict[str, Any]:
    """
    Parses a PDF document using Docling for layout and structure extraction.
    Falls back to PyMuPDF if Docling fails or is unavailable for complex layouts.
    """
    try:
        converter = _get_docling_converter()
        conv_result = converter.convert(file_path)
        doc = conv_result.document

        page_count = len(doc.pages) if hasattr(doc, "pages") and doc.pages else 0
        if page_count == 0:
            # Fall back to PyMuPDF for reliable page count if doc.pages is empty
            with fitz.open(file_path) as fdoc:
                page_count = len(fdoc)

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

        # If pages extracted have no text, fall back to markdown export or PyMuPDF
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

    except Exception as exc:
        logger.warning(
            f"Docling parsing failed for {file_path}: {exc}. Falling back to PyMuPDF."
        )
        return _parse_with_pymupdf(file_path)
