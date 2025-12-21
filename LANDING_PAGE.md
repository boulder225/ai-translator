# Landing Page Content - LexDeep Legal Translator

## Hero Section

### Headline
**Professional Legal Translation with AI-Powered Consistency**

### Subheadline
Translate legal documents with guaranteed terminology accuracy. Built for Swiss legal professionals, translators, and law firms who demand precision.

### Primary CTA
**Start Translating** (or "Try Free Demo")

### Key Value Points (3 bullets)
- ✅ **Terminology Consistency** - Maintain exact terminology across all documents
- ✅ **Translation Memory** - Reuse previous translations to save time and costs
- ✅ **Format Preservation** - DOCX/PDF in, polished PDF out

---

## Problem Statement Section

### Headline
**Legal Translation Shouldn't Be a Guessing Game**

### Body
Legal documents require absolute precision. One inconsistent term can change meaning, create liability, or break compliance. Traditional translation tools don't understand legal terminology hierarchies or maintain consistency across document batches.

**Common Pain Points:**
- Inconsistent terminology across documents
- Manual glossary management is time-consuming
- No way to enforce reference document priorities
- Translation memory scattered across tools
- Formatting gets lost in translation

---

## Solution Section

### Headline
**AI-Powered Translation That Understands Legal Context**

### Body
LexDeep combines Claude AI with intelligent terminology management to deliver translations that maintain consistency, respect legal hierarchies, and preserve document formatting.

### Key Features Grid

#### 1. **Intelligent Terminology Management**
- **Glossary System**: CSV-based glossaries with exact term matching
- **Translation Memory**: JSON-based memory with 70% similarity threshold for contextual reuse
- **Reference Documents**: Upload reference documents that take absolute priority over all other sources
- **Term Hierarchy**: Reference Doc → Glossary → Memory → AI (enforced automatically)

#### 2. **Batch Processing**
- Process **50+ documents** in a single batch
- Automatic progress tracking
- Per-document translation reports
- Batch manifest with aggregated statistics

#### 3. **Format Preservation**
- **Input Formats**: DOCX, PDF, TXT
- **Output Format**: Polished PDF with preserved formatting
- Side-by-side original and translated content
- Highlighted terminology matches

#### 4. **Swiss Legal Specialization**
- **Swiss Italian variant** (not Italian from Italy)
- Specialized prompts for:
  - Professional pensions / pension funds
  - Insurance documents (especially Aon Switzerland Ltd)
  - Legal documents, HR, corporate regulations, contracts
  - Related texts (notices, internal regulations, policyholder documents)
- Compliance with admin.ch and fedlex.admin.ch standards

#### 5. **Translation Statistics & Reporting**
- Real-time progress tracking
- Translation statistics dashboard:
  - Terms found in glossary
  - Terms reused from memory
  - Terms from reference documents
  - Model API calls
  - Processing time
- Detailed per-paragraph logs
- JSON reports for audit trails

#### 6. **User-Friendly Interface**
- Clean, modern web UI (inspired by DeepL)
- Drag-and-drop file upload
- Automatic source language detection
- Settings toolbar with glossary viewer
- Side-by-side translation review

---

## How It Works Section

### Step 1: **Upload Document**
Upload your legal document (DOCX, PDF, or TXT). The system automatically detects the source language.

### Step 2: **Configure Translation**
- Select target language
- Choose glossary (if available)
- Enable/disable translation memory
- Upload reference document (optional, highest priority)

### Step 3: **Review & Download**
- View side-by-side original and translated content
- Check translation statistics
- Download polished PDF with both original and translated text

---

## Use Cases Section

### For Legal Translators
- **Batch Processing**: Translate 50+ documents while maintaining terminology consistency
- **Memory Reuse**: Save time and API costs by reusing previous translations
- **Reference Documents**: Ensure client-specific terminology takes priority
- **Audit Trail**: Detailed reports for client review

### For Law Firms
- **Internal Document Translation**: Translate HR policies, contracts, and regulations
- **Client Document Preparation**: Ensure consistent terminology across client communications
- **Compliance**: Maintain Swiss legal standards (admin.ch, fedlex)

### For LSPs (Language Service Providers)
- **Workflow Integration**: Designed to work with existing tools (Trados mentioned in roadmap)
- **Cost Efficiency**: Translation memory reduces API calls
- **Quality Assurance**: Built-in terminology consistency checks

---

## Technical Specifications

### Supported Languages
- **Source**: French, German, English
- **Target**: English, German, Italian (Swiss variant)

### File Formats
- **Input**: DOCX, PDF, TXT
- **Output**: PDF (with original and translated content)

### Technology Stack
- **AI Engine**: Claude (Anthropic) - configurable model selection
- **Backend**: FastAPI REST API
- **Frontend**: React application
- **Processing**: Paragraph-level translation with chunking

### Performance
- **Speed**: < 5 minutes per document (average)
- **Memory Reuse**: 90%+ on similar documents
- **Batch Capacity**: 50+ documents per batch

---

## Differentiators Section

### What Makes LexDeep Different?

1. **Terminology Hierarchy Enforcement**
   - Reference documents → Glossary → Memory → AI
   - Automatic priority enforcement (no manual configuration needed)

2. **Swiss Legal Specialization**
   - Built specifically for Swiss legal context
   - Swiss Italian variant support
   - Compliance with Swiss legal standards

3. **Translation Memory Intelligence**
   - 70% similarity threshold for contextual reuse
   - Automatic exact match detection
   - Reduces API costs significantly

4. **Format Preservation**
   - Maintains document structure
   - Side-by-side original/translated output
   - Highlighted terminology matches

5. **Reference Document Priority**
   - Upload reference documents that override all other sources
   - Perfect for client-specific terminology requirements

---

## Pricing / CTA Section

### Headline
**Ready to Translate with Confidence?**

### Body
LexDeep is currently in MVP phase, optimized for securing the first paying customer. Contact us for early access or demo.

### CTA Buttons
- **Request Demo** (primary)
- **Contact Sales** (secondary)

---

## Footer Information

### Product
- Features
- Use Cases
- Documentation
- API Reference

### Company
- About
- Contact
- Privacy Policy
- Terms of Service

### Contact
- Email: [contact email]
- Support: [support email]

---

## SEO Keywords

- Legal document translation
- Swiss legal translation
- Terminology management
- Translation memory
- Legal AI translation
- Document translation software
- Legal translator tool
- Swiss Italian translation
- Legal terminology consistency
- Batch document translation

---

## Social Proof / Testimonials (Placeholder)

*"LexDeep has transformed how we handle legal document translation. The terminology consistency is unmatched."* - Legal Translator

*"Finally, a tool that understands Swiss legal context and maintains formatting."* - Law Firm Partner

---

## Trust Indicators

- ✅ Built with Claude AI (Anthropic)
- ✅ Swiss legal compliance
- ✅ Format preservation guaranteed
- ✅ Translation memory reduces costs
- ✅ Detailed audit trails

---

## Additional Notes

- **MVP Status**: Currently optimized for first paying customer (3-4 week timeline)
- **Target Market**: Legal translators, law firms, LSPs in Switzerland
- **Deployment**: Local or Heroku deployment
- **Roadmap**: Trados export, multi-user support, database migration (post-MVP)
