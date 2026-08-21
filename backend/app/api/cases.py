"""Upload a charge file.

The only write path for `cases`, and there is no update path at all: a stored
case is immutable, because editing one after a comparison exists silently
invalidates that comparison. A correction is a new case.

One URL takes both input modes, because the interface offers them as two states
of one control. The request is dispatched on its content type rather than
declared as two parameters -- FastAPI reads a body as JSON *or* as multipart,
never as whichever arrived.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

# Starlette's, deliberately: `request.form()` yields that class, and FastAPI's
# `UploadFile` is a *subclass* of it -- so testing against the FastAPI one is
# always false and every upload looks like a missing file.
from starlette.datastructures import UploadFile

from .. import charge_file
from ..database import get_session
from ..models import Case
from ..schemas import ExtractedCharge

router = APIRouter(prefix="/api/cases", tags=["cases"])


async def _store(session: AsyncSession, extraction: charge_file.Extraction, **columns) -> Case:
    case = Case(
        title=extraction.title,
        content=extraction.text,
        word_count=extraction.word_count,
        pages=extraction.pages,
        **columns,
    )
    session.add(case)
    await session.commit()
    await session.refresh(case)
    return case


@router.post("", response_model=ExtractedCharge)
@router.post("/", response_model=ExtractedCharge, include_in_schema=False)
async def create_case(
    request: Request, session: AsyncSession = Depends(get_session)
) -> ExtractedCharge:
    """Extract, refuse or store -- in that order.

    A document that yields no text, or that is too short to carry an
    accusation anyone could argue, is refused here. Failing at upload is the
    point: the alternative is three confident verdicts about nothing.
    """
    content_type = request.headers.get("content-type", "")

    try:
        if content_type.startswith("multipart/form-data"):
            form = await request.form()
            upload = form.get("file")
            if not isinstance(upload, UploadFile):
                raise HTTPException(status_code=422, detail="Send a file under `file`.")
            extraction = charge_file.read(await upload.read(), upload.filename or "charge")
            case = await _store(session, extraction, source="file", filename=upload.filename)
        else:
            try:
                payload = json.loads(await request.body() or b"{}")
            except json.JSONDecodeError as error:
                raise HTTPException(status_code=422, detail="Send JSON or a file.") from error
            text = payload.get("text") if isinstance(payload, dict) else None
            if not isinstance(text, str):
                raise HTTPException(status_code=422, detail="Send either `text` or a file.")
            extraction = charge_file.read_text(text)
            case = await _store(session, extraction, source="text")
    except charge_file.ChargeFileRejected as rejection:
        raise HTTPException(status_code=422, detail=str(rejection)) from rejection

    return ExtractedCharge(
        case_id=case.id,
        title=case.title,
        word_count=case.word_count,
        pages=case.pages,
        has_text_layer=extraction.has_text_layer,
    )
