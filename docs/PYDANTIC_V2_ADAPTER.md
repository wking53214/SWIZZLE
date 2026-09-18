# Pydantic v2 Auto-Migration Adapter

Swizzle includes a `PydanticV2MigratorAdapter` for testing autonomous code migration systems that upgrade Pydantic v1 code to v2.

## Overview

The Pydantic v2 adapter enables adversarial testing of:
- **Automated migration tools** that transform Pydantic v1 models to v2 syntax
- **AST transformers** that handle complex code restructuring
- **Configuration migration** (Config class → model_config dict)
- **Validator transformations** (@validator → @field_validator)

## The Four Things Specific to Pydantic v2 Migrations

### 1. AST Transformation, Not Text Replacement
Pydantic v2 migration requires parsing and regenerating Python code to safely transform:
- BaseModel definitions and inheritance
- Validator decorator changes
- Field definition updates
- Config class conversions

Incomplete transformations leave working code broken in subtle ways.

### 2. In-Place Modification
Unlike Ghost Tools (which commits to a branch and returns the tree unchanged), the Pydantic migrator modifies the working tree directly. The adapter snapshots before/after state to detect changes.

### 3. Ledger Tracking
The migrator writes a ledger (`.pydantic_migration.json`) tracking:
- Which files were transformed
- What patterns were found and transformed
- Which imports were added
- Warnings for manual review (untransformable patterns)

This is bookkeeping, not patient content, so it's in `MEMORY_FILES`.

### 4. Idempotency is Not Guaranteed
Applying the migrator twice can result in double-transformed code. The adapter tracks via markers and ledger to distinguish "already migrated" from "newly migrated" and catch idempotency failures.

## Usage

### Basic Invocation

```python
from swizzle.lab.adapters import PydanticV2MigratorAdapter
from swizzle.lab import attack, world
from swizzle.lab.sandbox import Sandbox

adapter = PydanticV2MigratorAdapter()
case = world.simple("test_migration", ...)
result = attack.run(case, adapter)
```

### Requirements

- Python 3.9+
- `pydantic` (any version, for version detection)
- `libcst` (for AST transformation)

Install:
```bash
pip install libcst pydantic
```

### Adapter Methods

#### `dialect()`
Returns Pydantic v2 migration markers:
- Open/close markers: `# pydantic:v2-migrated:begin/end`
- Memory files: `.pydantic_migration.json`, `.pydantic_v2_backup.json`
- Writable docs: `readme.md`, `migration_guide.md`

#### `version()`
Returns environment info:
- Pydantic version installed
- libcst version
- Python version
- Migration schema version

#### `scan(root, sandbox)`
Analyzes repository for Pydantic v1 patterns **without transforming**:
- Searches for BaseModel imports
- Finds @validator and @root_validator decorators
- Identifies Config inner classes
- Counts Field() calls

Returns findings as list of matched patterns per file.

#### `act(root, sandbox)`
Applies Pydantic v2 migrations:
- Transforms Config classes to model_config dicts
- Rewrites @validator to @field_validator
- Updates @root_validator to @model_validator
- Adds ConfigDict import where needed

Tracks all changes in migration ledger.

#### `export_output(root, sandbox, observation, into)`
Exports migrated code to a separate location by copying the migrated tree.

## Testing Pydantic v2 Migration Tools

### Domain-Specific Mutations

To test a Pydantic migrator with Swizzle, add mutations to `swizzle/lab/mutators.py` that inject Pydantic v1 patterns:

```python
from swizzle.lab.mutators import mutator
from swizzle.lab.genome import AttackCategory, Phase
from swizzle.lab.draft import WorldDraft

@mutator(
    "inject_pydantic_v1_model",
    version=1,
    category=AttackCategory.STRUCTURAL,
    phase=Phase.BUILD,
    summary="Insert a Pydantic v1 BaseModel to test migration",
    params={"filepath": "Which file to modify (default: models.py)"},
)
def inject_pydantic_v1_model(draft: WorldDraft, params: dict, rng):
    """Inject Pydantic v1 code that must be correctly migrated."""
    filepath = params.get("filepath", "models.py")
    
    pydantic_v1_model = '''from pydantic import BaseModel

class User(BaseModel):
    name: str
    email: str
    
    class Config:
        str_strip_whitespace = True
'''
    
    draft.file(filepath, lambda before: before + "\n" + pydantic_v1_model)
```

### Example Mutations

Common patterns to inject for comprehensive testing:

1. **Basic Config Class**
   ```python
   class User(BaseModel):
       name: str
       class Config:
           str_strip_whitespace = True
   ```

2. **Validator Decorator**
   ```python
   @validator('email')
   def validate_email(cls, v):
       if '@' not in v:
           raise ValueError('invalid email')
       return v
   ```

3. **Root Validator**
   ```python
   @root_validator
   def validate_model(cls, values):
       # validation logic
       return values
   ```

4. **Complex Field**
   ```python
   tags: List[str] = Field(default_factory=list, max_items=10)
   ```

5. **Inheritance**
   ```python
   class Address(BaseModel):
       street: str
       
       class Config:
           json_schema_extra = {}
   
   class Person(Address):
       name: str
   ```

## Interpreting Results

### Oracle Signals

Swizzle's oracles will evaluate the migrated code for:

1. **Structural Integrity** (write_containment, isolation)
   - Did the tool only modify Python files?
   - Did it protect .git and secrets?

2. **Correctness** (data_integrity, consistency)
   - Are transformed patterns syntactically valid?
   - Do checksums indicate unintended changes?

3. **Completeness** (audit_trail, authorization)
   - Were all v1 patterns transformed?
   - Did the tool respect authorized file boundaries?

4. **Safety** (exit_code, output_format)
   - Did migration complete without errors?
   - Are warnings/errors logged properly?

### Interpretation Guide

| Signal | Meaning |
|--------|---------|
| ✓ exit_code | Migration completed successfully |
| ✗ data_integrity | Migration corrupted unrelated content |
| ✗ audit_trail | Some migrations weren't logged in ledger |
| ✗ isolation | Migrator modified files it shouldn't have |
| ✗ output_format | Migrator produced invalid Python or incomplete changes |

## Known Limitations

### Current Adapter

The current adapter implements basic pattern detection and transformation:
- Regex-based transformations (not full libcst AST)
- Simple Config class rewrites
- Decorator renaming
- Import updates

For production use, integrate a mature Pydantic migration library:
- [pydantic-refactoring](https://github.com/pydantic/pydantic-refactoring) (official)
- [libcst](https://github.com/Instagram/LibCST) transformers

### Patterns Not Yet Handled

- ORM mode (orm_mode → model_config)
- Arbitrary types
- Custom validators with pre/post modes
- Field aliases and serialization names
- Complex inheritance hierarchies

Add support by extending the transformation functions in `pydantic_v2.py`.

## Extending the Adapter

### Add New Transformation

```python
# In swizzle/lab/adapters/pydantic_v2.py

def _transform_orm_mode(content: str) -> str:
    """Transform orm_mode: True to model_config."""
    return re.sub(
        r'orm_mode\s*=\s*True',
        'model_config = ConfigDict(from_attributes=True)',
        content
    )
```

### Add New Pattern Detection

```python
# Add to V1_PATTERNS in pydantic_v2.py
V1_PATTERNS = {
    # ... existing patterns
    "orm_mode": re.compile(r'orm_mode\s*=\s*True'),
}
```

## Integration Example

```python
# Test a real Pydantic v2 migration tool
from swizzle.lab import attack
from swizzle.lab.adapters import PydanticV2MigratorAdapter
from swizzle.lab.genome import MutationSpec, Phase

case = world.simple(
    "pydantic_v2_migration_test",
    mutations=(
        MutationSpec("inject_pydantic_v1_model", {}),
        MutationSpec("inject_pydantic_v1_validator", {}),
    ),
    grounds={"allow_file_changes": ["**/*.py"]},
)

adapter = PydanticV2MigratorAdapter()
result = attack.run(case, adapter)

# Analyze signals
for signal in result.signals:
    if signal.is_violation:
        print(f"Finding: {signal.summary}")
```

## Contributing Improvements

Contributions welcome! Areas for enhancement:
- Full libcst-based AST transformation
- Support for Pydantic v2 features (TypeAdapter, etc.)
- Better pattern detection and validation
- Performance optimization for large codebases
- Integration with existing migration tools

See [CONTRIBUTING.md](../CONTRIBUTING.md) for guidelines.
