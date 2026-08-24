"""Open, NTIA-aligned schemas and reference tooling for BEAD compliance evidence.

The toolkit exists so that a manufacturer, a BEAD-subgrantee ISP, and a state
broadband office can exchange the same performance, location, and Build America
Buy America evidence without writing a bespoke parser for every counterparty.

Public surface:

    SCHEMA_VERSION      version string every v0 record carries
    FACT_KINDS          the three fact families, keyed by CLI name
    load_schema         read a normative JSON Schema off disk
    load_records        read a .json or .csv file into records
    validate_records    validate parsed records against schema plus model rules
    validate_file       validate one file end to end
"""

from bead_data.schemas import (
    FACT_KINDS,
    SCHEMA_VERSION,
    FactKind,
    load_schema,
)
from bead_data.validate import (
    RecordError,
    ValidationReport,
    detect_kind,
    load_records,
    validate_file,
    validate_records,
)

__version__ = "0.1.0"

__all__ = [
    "FACT_KINDS",
    "SCHEMA_VERSION",
    "FactKind",
    "RecordError",
    "ValidationReport",
    "__version__",
    "detect_kind",
    "load_records",
    "load_schema",
    "validate_file",
    "validate_records",
]
