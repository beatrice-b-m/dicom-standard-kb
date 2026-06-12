# Validator Example

Runs local identifier normalization helpers without opening a KB:

```bash
python examples/validators/validate_identifier.py --tag '(0008,0060)'
python examples/validators/validate_identifier.py --uid '1.2.840.10008.1.2.1'
```

These helpers validate identifier syntax only. They do not prove conformance or
assert that an identifier exists in a specific DICOM edition. They are included
with the fixture-targeted examples because they require no official artifacts or
generated database.
