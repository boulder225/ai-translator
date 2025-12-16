"""Test PDF generation with memory enabled and glossary disabled, reproducing the <para> tag error."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from translator.processing import translate_file_to_memory
from translator.terminology.memory import TranslationMemory
from translator.pdf_writer import write_pdf_to_bytes


class DummyTranslator:
    """Dummy translator that won't be called since we're using memory."""
    def translate_paragraph(self, paragraph: str, **_: str) -> str:
        return f"translated::{paragraph}"


def test_pdf_generation_with_memory_enabled_glossary_disabled():
    """Test PDF generation when memory is enabled and glossary is disabled.
    
    This reproduces the scenario where:
    - Glossary is disabled (use_glossary=False)
    - Memory is enabled (skip_memory=False)
    - Translation comes from memory (has <memory> tags)
    - Content includes a long markdown table that gets split into chunks
    - PDF generation should work without <para> tag errors
    """
    # Create a temporary directory for memory file
    with tempfile.TemporaryDirectory() as tmpdir:
        memory_path = Path(tmpdir) / "memory.json"
        memory = TranslationMemory(memory_path)
        
        # Source text (French) - exact content from user's file
        source_text = (
            "\n\n2. OBJET DU BAIL\n\n"
            "☐ Appartement de ______ pièces  \n"
            "☐ ______ chambre(s) meublée(s)\n\n"
            "Adresse de l'immeuble: [À compléter]"
        )
        
        # Translated text (Italian) - use the EXACT content from memory.json that causes the issue
        # This is 4128 characters and includes a long markdown table that will be split into chunks
        translated_text = (
            "# TRADUZIONE\n\n"
            "## 2. OGGETTO DELLA LOCAZIONE\n\n"
            "☐ Sgabuzzino di ______ locali al ___ piano\n"
            "☐ Casa di ______ locali\n"
            "☐ ______ camera/e ammobiliata/e\n\n"
            "Indirizzo dell'immobile: [Da completare]\n\n"
            "---\n\n"
            "## TABELLA COMPARATIVA E NOTE\n\n"
            "| Originale | Traduzione | Spiegazione | Fonte |\n"
            "|-----------|------------|-------------|-------|\n"
            "| OBJET DU BAIL | OGGETTO DELLA LOCAZIONE | Terminologia standard del diritto svizzero della locazione. "
            '"Oggetto della locazione" è la formula consolidata per indicare il bene locato nei contratti di locazione. '
            'Alternativa possibile ma meno tecnica: "Oggetto del contratto". | Codice delle obbligazioni (CO), art. 253 e segg.; admin.ch; prassi contrattuale svizzera |\n'
            "| Appartement | Sgabuzzino | **Applicazione del glossario fornito**. Tuttavia, segnalo una **forte incongruenza semantica**: \"appartement\" in francese indica un'abitazione di più locali, mentre \"sgabuzzino\" in italiano designa un locale di servizio di piccole dimensioni (ripostiglio, stanzino). Questa scelta terminologica genera un'**evidente contraddizione** con \"di ______ locali\", che presuppone un'unità abitativa articolata. **Raccomandazione**: verificare con urgenza se il glossario contiene un errore o se il contesto d'uso è diverso da quello standard. | Glossario cliente fornito (obbligatorio per questa richiesta) |\n"
            "| de ______ pièces | di ______ locali | \"Locali\" è il termine standard in italiano di Svizzera per tradurre \"pièces\" nel contesto immobiliare. Indica le stanze abitabili (esclusi cucina, bagno, corridoi). Alternativa meno usata: \"vani\". | Prassi immobiliare svizzera; annunci immobiliari su portali svizzeri (homegate.ch, immoscout24.ch) |\n"
            "| au ___ étage | al ___ piano | Traduzione standard. In italiano di Svizzera si usa \"piano\" come in Italia. | Uso corrente |\n"
            "| Maison | Casa | Traduzione diretta e univoca. | Uso corrente |\n"
            "| chambre(s) meublée(s) | camera/e ammobiliata/e | \"Camera ammobiliata\" è la formula standard per locazioni di singole stanze arredate. La barra obliqua permette di mantenere la flessibilità singolare/plurale del modulo. Alternativa: \"camera/e arredata/e\" (meno formale). | Prassi contrattuale svizzera per locazioni di camere |\n"
            "| Adresse de l'immeuble | Indirizzo dell'immobile | \"Immobile\" è il termine giuridico appropriato per designare il bene immobiliare oggetto di locazione. Alternativa possibile: \"Indirizzo dello stabile\" (più comune in Ticino per edifici plurifamiliari). | CO, art. 253 e segg.; linguaggio giuridico-amministrativo svizzero |\n"
            "| [À compléter] | [Da completare] | Traduzione standard dell'indicazione per campi da riempire. | Uso corrente |"
        )
        
        # Store translation in memory
        memory.record(source_text, translated_text, source_lang="fr", target_lang="it")
        
        # Create a temporary input file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write(source_text)
            input_path = f.name
        
        try:
            # Create a dummy translator (won't be called since memory will be used)
            translator = DummyTranslator()
            
            # Translate with memory enabled and glossary disabled
            pdf_bytes, translated_paragraphs, report = translate_file_to_memory(
                input_path=Path(input_path),
                memory=memory,
                glossary=None,  # Glossary disabled
                translator=translator,
                source_lang="fr",
                target_lang="it",
                skip_memory=False,  # Memory enabled
                reference_doc_pairs=None,
            )
            
            # Verify PDF was generated
            assert pdf_bytes is not None, "PDF bytes should be generated"
            assert len(pdf_bytes) > 0, "PDF should not be empty"
            
            # Verify translated paragraphs
            assert translated_paragraphs is not None, "Translated paragraphs should be generated"
            assert len(translated_paragraphs) > 0, "Should have translated paragraphs"
            
            # Verify report
            assert report is not None, "Report should be generated"
            assert report.get("stats") is not None, "Report should have stats"
            
            # Verify memory was used
            assert report.get("stats", {}).get("reused_from_memory", 0) > 0, "Should have reused from memory"
            
            # The key test: verify PDF can be generated without errors
            # If we get here without an exception, the <para> tag issue is fixed
            print(f"✓ PDF generated successfully: {len(pdf_bytes)} bytes")
            print(f"✓ Translated paragraphs: {len(translated_paragraphs)}")
            print(f"✓ Memory reused: {report.get('stats', {}).get('reused_from_memory', 0)}")
            
        finally:
            # Clean up
            Path(input_path).unlink(missing_ok=True)


if __name__ == '__main__':
    print("Testing PDF generation with memory enabled and glossary disabled...")
    print("This reproduces the scenario that caused the <para> tag error.\n")
    
    try:
        test_pdf_generation_with_memory_enabled_glossary_disabled()
        print("\n✓ Test passed! PDF generation works correctly.")
    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
