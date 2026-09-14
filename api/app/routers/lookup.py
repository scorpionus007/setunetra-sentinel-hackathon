"""#15 VAHAN/SARTHI integration — mocked adapters, documented real path in
the HLD. Persists every lookup (mocked or real) to `external_lookups`
(contracts/schema.sql) — the table existed since Day 0 but nothing ever
wrote to it until now, so there was no audit trail of what got looked up.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_db
from app.models import ExternalLookup

router = APIRouter(prefix="/api/lookup", tags=["lookup"])


def _record_lookup(db: Session, source: str, query_value: str, response: dict) -> None:
    row = ExternalLookup(source=source, query_value=query_value, response_json=response, is_mocked=True)
    db.add(row)
    db.commit()


@router.get("/vahan")
def lookup_vahan(plate: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    # Mocked response shape — swap for the real VAHAN API once credentials
    # and an MOU are in place; see contracts/schema.sql `external_lookups`.
    result = {"source": "vahan", "plate": plate, "is_mocked": True, "result": None}
    _record_lookup(db, "vahan", plate, result)
    return result


@router.get("/sarthi")
def lookup_sarthi(dl: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    # Mocked response shape — swap for the real SARTHI API once credentials
    # and an MOU are in place; see contracts/schema.sql `external_lookups`.
    result = {"source": "sarthi", "licence_number": dl, "is_mocked": True, "result": None}
    _record_lookup(db, "sarthi", dl, result)
    return result
