"""Parser package."""

from knowledge.parsers.router import detect_extension, list_parsers, parse_document, route_parser

__all__ = ["detect_extension", "list_parsers", "parse_document", "route_parser"]
