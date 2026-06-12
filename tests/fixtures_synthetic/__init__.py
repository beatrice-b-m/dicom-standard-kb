from pathlib import Path

FIXTURE_DIR = Path(__file__).resolve().parent

PS33_CT_IMAGE_DOCBOOK = (
    FIXTURE_DIR / "synthetic_ps3_3_ct_image_docbook.xml"
).read_text(encoding="utf-8")
PS36_REGISTRY_DOCBOOK = (
    FIXTURE_DIR / "synthetic_ps3_6_registry_docbook.xml"
).read_text(encoding="utf-8")
