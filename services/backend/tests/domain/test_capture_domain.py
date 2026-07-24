from dataclasses import FrozenInstanceError
from uuid import uuid4

import pytest
from stylecapture_backend.features.capture.domain import (
    Capture,
    CaptureSource,
    CaptureSourceKind,
    InvalidJobTransition,
    JobState,
    OwnershipState,
    ProcessingJob,
)
from stylecapture_backend.features.wardrobe.domain import (
    FieldEnvelope,
    FieldProvenance,
    ItemAttributes,
    ModelField,
)


def test_capture_keeps_the_original_source_immutable() -> None:
    source = CaptureSource(
        kind=CaptureSourceKind.UPLOAD,
        object_key="originals/user-1/garment.heic",
        sha256="b" * 64,
    )

    capture = Capture.create(
        user_id=uuid4(),
        source=source,
        ownership=OwnershipState.OWNED,
    )

    assert capture.source.object_key == "originals/user-1/garment.heic"
    with pytest.raises(FrozenInstanceError):
        capture.source.object_key = "replaced.jpg"  # type: ignore[misc]


def test_processing_job_allows_only_declared_state_transitions() -> None:
    job = ProcessingJob.queued(capture_id=uuid4())

    processing = job.transition(JobState.PROCESSING)
    ready = processing.transition(JobState.READY)

    assert ready.state is JobState.READY
    with pytest.raises(InvalidJobTransition):
        ready.transition(JobState.PROCESSING)


def test_retry_requeues_a_failed_job_without_replacing_capture() -> None:
    capture_id = uuid4()
    job = (
        ProcessingJob.queued(capture_id=capture_id)
        .transition(JobState.PROCESSING)
        .transition(JobState.ERROR)
    )

    retry = job.transition(JobState.QUEUED)

    assert retry.capture_id == capture_id
    assert retry.attempt == 2


def test_model_merge_never_overwrites_a_manually_locked_field() -> None:
    attributes = ItemAttributes(
        fields={
            "category": FieldEnvelope(
                value="上装",
                provenance=FieldProvenance.USER,
                confidence=1.0,
                model_version=None,
                locked=True,
            ),
            "color": FieldEnvelope(
                value="米白",
                provenance=FieldProvenance.MODEL,
                confidence=0.72,
                model_version="vision-v1",
                locked=False,
            ),
        }
    )

    merged = attributes.merge_model(
        {
            "category": ModelField(value="连衣裙", confidence=0.97, model_version="vision-v2"),
            "color": ModelField(value="奶油白", confidence=0.94, model_version="vision-v2"),
            "material": ModelField(value="针织", confidence=0.83, model_version="vision-v2"),
        }
    )

    assert merged.fields["category"].value == "上装"
    assert merged.fields["category"].provenance is FieldProvenance.USER
    assert merged.fields["color"].value == "奶油白"
    assert merged.fields["material"].provenance is FieldProvenance.MODEL
