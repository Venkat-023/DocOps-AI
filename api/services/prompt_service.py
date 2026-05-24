from typing import Optional

from api.models.request_models import GenerateRequest, ParsedSymbols

TONE_TECHNICAL = """Write for an experienced engineer contributing to this codebase.
Use precise technical language. Assume familiarity with the domain.
Include internal implementation notes where relevant."""

TONE_ONBOARDING = """Write for a developer joining this project for the first time.
Use plain language. Explain the 'why' behind decisions.
Include analogies where helpful. Define any domain-specific terms."""

FORMAT_PROMPTS = {
    "readme": """Generate a complete, professional README.md file.

Structure EXACTLY as follows:
1. One-line description (sharp, no fluff)
2. Badges row: [Python version] [License] [Tests]
3. ## Features - bullet list of 4-6 key capabilities
4. ## Installation - exact commands, OS-specific if needed
5. ## Quick start - the simplest possible working example
6. ## API reference - table with Function | Parameters | Returns | Description
7. ## Configuration - environment variables or config options
8. ## Contributing - two-sentence guide
9. ## License

Rules:
- Every code example must be copy-paste runnable
- Parameter table must list all parameters found in the symbol list
- Do not invent capabilities that are not in the code
- Use the actual function names, not pseudocode""",
    "jsdoc": """Generate complete JSDoc/docstring comments for every function and class.

For each function include:
- One-line summary that starts with a verb
- @param {{type}} name - description, for every param
- @returns {{type}} - description of return value
- @throws {{ErrorType}} - when this can be thrown
- @example - realistic 3-5 line usage example
- @since 1.0.0
- @complexity O(n) or similar if relevant

For each class include:
- Class purpose in 2 sentences max
- @property descriptions
- Constructor @param docs
- Usage example showing the full lifecycle

Insert comments directly inline with the code.
Preserve all original code. Only add comments; never change logic.""",
    "openapi": """Generate a complete OpenAPI 3.1 YAML specification.

Include:
openapi: 3.1.0
info: title, description, version, contact
paths: every route found, with:
  - GET/POST/PUT/DELETE
  - summary and description
  - parameters with schema and required flag
  - requestBody with JSON schema
  - responses: 200 with schema, 400, 401, 404, 500
components:
  schemas: every model with all properties, types, examples
  securitySchemes if auth detected

Rules:
- Use $ref for shared schemas
- Every example must be realistic
- Mark all required fields
- Add enum values where the code constrains them""",
    "confluence": """Generate Confluence wiki page content in HTML.

Structure:
<h1>Module name</h1>
<ac:structured-macro ac:name="info">
  <ac:parameter ac:name="title">Summary</ac:parameter>
  <ac:rich-text-body><p>one paragraph overview</p></ac:rich-text-body>
</ac:structured-macro>

Then: Overview, Architecture, API Reference table, Usage examples, Troubleshooting FAQ.

Use Confluence table macro for API reference.
Use code macro with correct language for all examples.
Include a Related pages section at the bottom.""",
    "docusaurus": """Generate Docusaurus v3 MDX documentation page.

Include frontmatter:
---
sidebar_label: 'Module name'
sidebar_position: 1
description: 'One-line description'
---

Then full MDX content with:
- import CodeBlock from '@theme/CodeBlock'
- :::tip, :::warning, :::info admonitions where relevant
- Tabs component for multi-language examples
- Full API reference table
- Interactive examples where possible

All code blocks must have language tag and a title prop.""",
}


def build_prompt(req: GenerateRequest) -> tuple[str, str]:
    tone = TONE_ONBOARDING if req.onboarding_mode else TONE_TECHNICAL
    symbol_summary = _build_symbol_summary(req.symbols)
    repository_scan_instructions = _build_repository_scan_instructions(req.code)

    system_prompt = f"""You are a world-class technical writer with 15 years of experience
documenting developer tools. You generate accurate, complete, and genuinely useful documentation.

{tone}

Output only the documentation content. No preamble, no "Here is your documentation",
no explanation. Start directly with the content.

{FORMAT_PROMPTS.get(req.format, FORMAT_PROMPTS["readme"])}"""

    language = req.language or (req.symbols.language if req.symbols else "text")
    user_prompt = f"""Generate documentation for the following source.
{symbol_summary}
{repository_scan_instructions}

SOURCE:
```{language}
{req.code[:30000]}
```"""
    return system_prompt, user_prompt


CRITIQUE_SYSTEM = """You are a documentation quality reviewer.
Review the documentation and return only a JSON object with this exact shape:
{
  "coverage": 0-100,
  "examples": 0-100,
  "params": 0-100,
  "edge_cases": 0-100,
  "overall": 0-100,
  "improvements": ["suggestion 1", "suggestion 2", "suggestion 3"]
}
No other text. Only the JSON object."""


def build_critique_prompt(code: str, documentation: str, symbols: Optional[ParsedSymbols]) -> str:
    fn_count = len(symbols.functions) if symbols else "unknown"
    class_count = len(symbols.classes) if symbols else "unknown"
    return f"""Review this documentation against the source code.

Source has {fn_count} functions and {class_count} classes.

Documentation to review:
{documentation[:5000]}

Source code:
{code[:4000]}"""


def _build_symbol_summary(symbols: Optional[ParsedSymbols]) -> str:
    if not symbols:
        return ""

    fn_names = [symbol.name for symbol in symbols.functions[:40]]
    class_names = [symbol.name for symbol in symbols.classes[:20]]
    return f"""
EXTRACTED SYMBOLS:
Language: {symbols.language}
Functions ({len(symbols.functions)}): {', '.join(fn_names)}
Classes ({len(symbols.classes)}): {', '.join(class_names)}
Total lines: {symbols.line_count}
Key imports: {', '.join(symbols.imports[:10])}
"""


def _build_repository_scan_instructions(code: str) -> str:
    if "## Scanned repository files" not in code and "### File:" not in code:
        return ""

    return """
REPOSITORY SCAN CONTEXT:
The source below is a combined GitHub repository scan. It contains the README,
the repository tree, and representative code/configuration snippets under
sections named "### File: path".

Produce a detailed repository report that covers BOTH:
1. README analysis: problem, goal, dataset/domain, setup, usage, outputs, and documented results.
2. Code analysis: scanned files, each file's role, important functions/classes/scripts, pipeline flow,
   dependencies, configuration, data paths, execution steps, and risks or missing pieces.

Do not only summarize the README. Use the scanned code snippets as evidence.
When details are not present in the scanned files, say so instead of inventing.
"""
