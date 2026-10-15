from pathlib import Path

from dicom_kb.cli.ingest import FIXTURE_EDITION

# Edition labels for synthetic builds. Tests that don't care which edition they
# use take EDITION; OTHER_EDITION is for tests that need two editions apart.
EDITION = FIXTURE_EDITION
OTHER_EDITION = "2000b"

FIXTURE_DIR = Path(__file__).resolve().parent

PS33_CT_IMAGE_DOCBOOK = (
    FIXTURE_DIR / "synthetic_ps3_3_ct_image_docbook.xml"
).read_text(encoding="utf-8")
PS34_SOP_CLASSES_DOCBOOK = (
    FIXTURE_DIR / "synthetic_ps3_4_sop_classes_docbook.xml"
).read_text(encoding="utf-8")
PS35_ENCODING_DOCBOOK = (
    FIXTURE_DIR / "synthetic_ps3_5_encoding_docbook.xml"
).read_text(encoding="utf-8")
PS36_REGISTRY_DOCBOOK = (
    FIXTURE_DIR / "synthetic_ps3_6_registry_docbook.xml"
).read_text(encoding="utf-8")
PS316_CONTENT_MAPPING_DOCBOOK = (
    FIXTURE_DIR / "synthetic_ps3_16_content_mapping_docbook.xml"
).read_text(encoding="utf-8")

# One synthetic DocBook file per part the build parses.
SYNTHETIC_PARTS = {
    "PS3.3": "synthetic_ps3_3_ct_image_docbook.xml",
    "PS3.4": "synthetic_ps3_4_sop_classes_docbook.xml",
    "PS3.5": "synthetic_ps3_5_encoding_docbook.xml",
    "PS3.6": "synthetic_ps3_6_registry_docbook.xml",
    "PS3.16": "synthetic_ps3_16_content_mapping_docbook.xml",
}
