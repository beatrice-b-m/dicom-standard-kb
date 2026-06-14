# Public Distribution Policy

Repository releases contain source code, schemas, documentation, fixtures,
and tests only. They must not contain official DICOM source artifacts,
generated full databases, generated full-text exports, or vector indexes over
the standard.

Generated PS3.16 terminology content follows the same rule. SR templates,
context groups, coded concepts, and code meanings may be built locally from
official artifacts for lookup, but releases and public demos must not publish
standalone terminology dumps or bulk context-group/code exports.
