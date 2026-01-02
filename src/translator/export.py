"""Export functions for Trados-compatible formats (TMX and TBX)."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import IO

from .terminology import Glossary, TranslationMemory


def export_tmx(memory: TranslationMemory, output_path: str | Path, source_lang: str, target_lang: str) -> None:
    """
    Export translation memory to TMX (Translation Memory eXchange) format.
    
    TMX is an XML format for exchanging translation memories between tools.
    Compatible with Trados, MemoQ, and other CAT tools.
    
    Args:
        memory: TranslationMemory instance to export
        output_path: Path where TMX file will be written
        source_lang: Source language code (e.g., "de-CH", "fr-CH")
        target_lang: Target language code (e.g., "de-CH", "fr-CH")
    """
    # Map our language codes to ISO 639-1 codes with region if needed
    lang_map = {
        "de": "de-CH",
        "fr": "fr-CH",
        "it": "it-CH",
        "en": "en-US",
    }
    source_lang_code = lang_map.get(source_lang, source_lang)
    target_lang_code = lang_map.get(target_lang, target_lang)
    
    # Create TMX root element
    tmx = ET.Element("tmx", version="1.4")
    
    # Add header
    header = ET.SubElement(tmx, "header")
    header.set("creationtool", "Legal Translator")
    header.set("creationtoolversion", "0.1.0")
    header.set("datatype", "plaintext")
    header.set("segtype", "sentence")
    header.set("adminlang", "en-US")
    header.set("srclang", source_lang_code)
    header.set("o-tmf", "none")
    header.set("creationdate", datetime.now().strftime("%Y%m%dT%H%M%SZ"))
    
    # Add body
    body = ET.SubElement(tmx, "body")
    
    # Add translation units (tu) for each memory record
    for record in memory:
        # Only include records matching the source/target language pair
        if record.source_lang != source_lang or record.target_lang != target_lang:
            continue
        
        tu = ET.SubElement(body, "tu")
        
        # Source language translation unit variant
        tuv_source = ET.SubElement(tu, "tuv")
        tuv_source.set("xml:lang", source_lang_code)
        seg_source = ET.SubElement(tuv_source, "seg")
        seg_source.text = record.source_text
        
        # Target language translation unit variant
        tuv_target = ET.SubElement(tu, "tuv")
        tuv_target.set("xml:lang", target_lang_code)
        seg_target = ET.SubElement(tuv_target, "seg")
        seg_target.text = record.translated_text
    
    # Write to file
    tree = ET.ElementTree(tmx)
    ET.indent(tree, space="  ")
    
    output_path_obj = Path(output_path)
    output_path_obj.parent.mkdir(parents=True, exist_ok=True)
    
    # Write with XML declaration and UTF-8 encoding
    with output_path_obj.open("wb") as f:
        f.write(b'<?xml version="1.0" encoding="UTF-8"?>\n')
        tree.write(f, encoding="utf-8", xml_declaration=False)


def export_tbx(glossary: Glossary, output_path: str | Path) -> None:
    """
    Export glossary to TBX (TermBase eXchange) format.
    
    TBX is an XML format for exchanging terminology/glossary data.
    Compatible with Trados MultiTerm and other terminology management tools.
    
    Args:
        glossary: Glossary instance to export
        output_path: Path where TBX file will be written
    """
    # Map our language codes to ISO 639-1 codes
    lang_map = {
        "de": "de-CH",
        "fr": "fr-CH",
        "it": "it-CH",
        "en": "en-US",
    }
    source_lang_code = lang_map.get(glossary.source_lang, glossary.source_lang)
    target_lang_code = lang_map.get(glossary.target_lang, glossary.target_lang)
    
    # Create TBX root element (TBX-Basic format for simplicity)
    martif = ET.Element("martif")
    martif.set("type", "TBX")
    martif.set("xml:lang", source_lang_code)
    
    # Add header
    martifHeader = ET.SubElement(martif, "martifHeader")
    fileDesc = ET.SubElement(martifHeader, "fileDesc")
    sourceDesc = ET.SubElement(fileDesc, "sourceDesc")
    p = ET.SubElement(sourceDesc, "p")
    p.text = f"Exported from Legal Translator glossary: {glossary.name}"
    
    # Add text body
    text = ET.SubElement(martif, "text")
    body = ET.SubElement(text, "body")
    
    # Add term entries
    for entry in glossary.iter_entries():
        termEntry = ET.SubElement(body, "termEntry")
        termEntry.set("id", f"te-{entry.fingerprint}")
        
        # Source language term
        langSet_source = ET.SubElement(termEntry, "langSet")
        langSet_source.set("xml:lang", source_lang_code)
        ntig = ET.SubElement(langSet_source, "ntig")
        termGrp = ET.SubElement(ntig, "termGrp")
        term_source = ET.SubElement(termGrp, "term")
        term_source.text = entry.term
        
        # Target language term
        langSet_target = ET.SubElement(termEntry, "langSet")
        langSet_target.set("xml:lang", target_lang_code)
        ntig_target = ET.SubElement(langSet_target, "ntig")
        termGrp_target = ET.SubElement(ntig_target, "termGrp")
        term_target = ET.SubElement(termGrp_target, "term")
        term_target.text = entry.translation
        
        # Add context if available
        if entry.context:
            descrip = ET.SubElement(termGrp_target, "descrip")
            descrip.set("type", "context")
            descrip.text = entry.context
    
    # Write to file
    tree = ET.ElementTree(martif)
    ET.indent(tree, space="  ")
    
    output_path_obj = Path(output_path)
    output_path_obj.parent.mkdir(parents=True, exist_ok=True)
    
    # Write with XML declaration and UTF-8 encoding
    with output_path_obj.open("wb") as f:
        f.write(b'<?xml version="1.0" encoding="UTF-8"?>\n')
        tree.write(f, encoding="utf-8", xml_declaration=False)
