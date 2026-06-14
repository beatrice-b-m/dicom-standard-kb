from pathlib import Path

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
PS37_MESSAGES_DOCBOOK = (
    FIXTURE_DIR / "synthetic_ps3_7_messages_docbook.xml"
).read_text(encoding="utf-8")
PS38_NETWORK_DOCBOOK = (
    FIXTURE_DIR / "synthetic_ps3_8_network_docbook.xml"
).read_text(encoding="utf-8")
PS310_MEDIA_STORAGE_DOCBOOK = (
    FIXTURE_DIR / "synthetic_ps3_10_media_storage_docbook.xml"
).read_text(encoding="utf-8")
