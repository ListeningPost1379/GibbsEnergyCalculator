from pathlib import Path
from .base import BaseParser
from .gaussian import GaussianParser
from .orca import OrcaParser

AVAILABLE_PARSERS = [GaussianParser, OrcaParser]

def get_parser(filepath: Path) -> BaseParser:
    """自动识别并返回 Parser 实例"""
    if not filepath.exists():
        raise FileNotFoundError(f"File not found: {filepath}")

    # 读取头部 3000 字符进行识别
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            header = f.read(3000)
    except UnicodeDecodeError:
        with open(filepath, 'r', encoding='latin-1') as f:
            header = f.read(3000)

    for parser_cls in AVAILABLE_PARSERS:
        if parser_cls.detect(header):
            return parser_cls(filepath)

    raise ValueError(f"Unsupported file format: {filepath.name}")