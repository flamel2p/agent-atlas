# Source and API evidence

Checked on 19 October 2026. Source research is separate from implementation/runtime verification.

## Book

Imran Ahmad, *30 Agents Every AI Engineer Must Build*, Packt, March 2026. A development source researcher inspected the retained inventory/foundations/brief and original extracted physical PDF pages 177–184. Purchased source files and raw extracted pages remain outside this repository.

| Heading | Printed pages | Physical PDF pages (1-based) |
| --- | --- | --- |
| Knowledge Retrieval agents | 146–153 | 177–184 |
| The retrieval process: Architecture in action | 147–148 | 178–179 |
| Implementation patterns and tools | 148–149 | 179–180 |
| Example: Building a RAG pipeline | 149–151 | 180–182 |
| Chunking strategies / Operational considerations | 151 | 182 |
| Common challenges / Diagnosing retrieval failures | 152 | 183 |

The source supports lexical, semantic, hybrid and single-stage retrieval. Its example uses LangChain, FAISS, OpenAI embeddings, 1,000-character chunks with 200 overlap, top-three retrieval, `text-embedding-3-large`, and `gpt-4o-mini`. The loader glob is `*.txt` despite prose describing broader document types. Returned sources do not establish claim correctness; the sample lacks explicit abstention, retry, freshness and access-control contracts.

Our lexical baseline, paragraph-preserving overlap, strict scope/date filters, extractive output and refusal rules are independent implementation choices. The sample code, prompts and diagrams were not copied.

## Optional OpenAI adapter

- [Python Responses create reference](https://developers.openai.com/api/reference/python/resources/responses/methods/create): `responses.create`, `text.format` JSON schema, tool controls, output-token limit, nonstreaming/background settings and truncation policy. The output cap also includes reasoning tokens, so an incomplete response is a failure, even if it contains a partial selection.
- [Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses): strict schemas require required object fields and `additionalProperties: false`. A refusal can bypass the requested schema. Validate the response envelope and selected IDs locally; schema validity alone is insufficient.
- [Python SDK reference](https://developers.openai.com/api/reference/python): documented defaults are two retries and a ten-minute timeout. The adapter must explicitly disable retries, set a finite HTTP timeout and fix the official endpoint. Transport compatibility is established against the pinned SDK by mocked-transport checks, not inferred from book-era dependencies or current documentation alone.
- [Data controls](https://developers.openai.com/api/docs/guides/your-data): `store=false` disables response application-state storage; it does not establish Zero Data Retention. Optional live mode sends the question and eligible candidate evidence to OpenAI.

The live model ID is explicitly supplied by the caller. No claim is made about latest models, account access, current pricing, live selection quality, or production suitability. Dependency pins and executed runtime checks are recorded in the case manifest/lockfile and README.
