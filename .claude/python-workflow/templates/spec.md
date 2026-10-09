# Specification — <slug>

## Overview
<2–3 sentences linking back to the goal in requirements.md.>

## Public Interfaces

### `module.function_name(...)` (or endpoint, CLI command, class)

**Signature:**
```python
def function_name(arg: Type) -> ReturnType: ...
```

**Pre-conditions:**
- …

**Post-conditions:**
- …

**Failure modes:**
- Raises `ValueError` when …
- Returns `None` when …

**Behavioral examples:**

| # | Given | When | Then |
|---|---|---|---|
| 1 | … | … | … |

<Repeat for every public interface.>

## Data Models / Schemas
<Pydantic models, dataclasses, JSON Schema, OpenAPI snippets — whatever applies.>

```python
class FooModel(BaseModel):
    id: UUID
    name: str
    ...
```

## Non-Functional Requirements
- **Latency:** p99 < … ms
- **Concurrency:** support … concurrent …
- **Security:** …

## Out of Scope
<Verbatim from the non-goals list in requirements.md.>
