from __future__ import annotations

from dataclasses import dataclass

from app.config import DEEP_ENROLLMENT_MIN_EMBEDDINGS, DEEP_FACE_ENCODING_VERSION
from app.database import SessionLocal
from app.models.face_template import FaceTemplate
from app.models.face_template_embedding import FaceTemplateEmbedding
from app.models.student import Student
from app.services.deep_face_matching import parse_deep_embedding


@dataclass(frozen=True)
class StudentReadiness:
    student_id: int
    name: str
    roll_number: str
    department: str
    status: str
    embedding_count: int
    readiness: str


def load_student_readiness() -> list[StudentReadiness]:
    rows: list[StudentReadiness] = []
    with SessionLocal() as db:
        students = db.query(Student).order_by(Student.studentId).all()
        for student in students:
            embedding_rows = (
                db.query(FaceTemplateEmbedding.embeddingData)
                .join(FaceTemplate, FaceTemplate.templateId == FaceTemplateEmbedding.faceTemplateId)
                .filter(
                    FaceTemplateEmbedding.studentId == student.studentId,
                    FaceTemplateEmbedding.encodingVersion == DEEP_FACE_ENCODING_VERSION,
                    FaceTemplateEmbedding.isActive.is_(True),
                    FaceTemplate.isActive.is_(True),
                )
                .all()
            )
            valid_count = sum(
                1
                for (embedding_data,) in embedding_rows
                if parse_deep_embedding(embedding_data) is not None
            )
            if student.status != "Active":
                readiness = "Excluded"
            elif valid_count >= DEEP_ENROLLMENT_MIN_EMBEDDINGS:
                readiness = "Ready"
            else:
                readiness = "Incomplete"
            rows.append(
                StudentReadiness(
                    student_id=student.studentId,
                    name=student.fullName.strip(),
                    roll_number=student.rollNo,
                    department=student.department.departmentName if student.department else str(student.departmentId),
                    status=student.status,
                    embedding_count=valid_count,
                    readiness=readiness,
                )
            )
    return rows


def main() -> None:
    rows = load_student_readiness()
    print("| Student ID | Name | Roll number | Department | Status | arcface_v1 embeddings | Readiness |")
    print("| ---: | --- | --- | --- | --- | ---: | --- |")
    for row in rows:
        print(
            f"| {row.student_id} | {row.name} | {row.roll_number} | {row.department} | "
            f"{row.status} | {row.embedding_count} | {row.readiness} |"
        )
    print(f"ready={sum(row.readiness == 'Ready' for row in rows)}")
    print(f"incomplete={sum(row.readiness == 'Incomplete' for row in rows)}")
    print(f"inactive_or_excluded={sum(row.readiness == 'Excluded' for row in rows)}")


if __name__ == "__main__":
    main()
