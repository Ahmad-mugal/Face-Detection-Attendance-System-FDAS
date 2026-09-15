from __future__ import annotations

import hashlib
import json
import math
import tempfile
from pathlib import Path
from unittest.mock import patch

import numpy as np
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models  # noqa: F401
from app.config import (
    DEEP_MATCH_MIN_IDENTITY_MARGIN,
    DEEP_MATCH_SCORING_METHOD,
    DEEP_MATCH_THRESHOLD,
    DEEP_RECOGNITION_ACTIVE_FOR_ATTENDANCE,
    IDENTITY_MATCHING_SAFETY_HOLD,
)
from app.database import Base
from app.models.attendance_record import AttendanceRecord
from app.models.classroom import ClassRoom
from app.models.department import Department
from app.models.face_template import FaceTemplate
from app.models.face_template_embedding import FaceTemplateEmbedding
from app.models.role import Role
from app.models.student import Student
from app.models.user import User
from app.services.deep_face import DeepEncodingResult
from app.services import deep_face_matching as matching


def unit_vector(score: float) -> np.ndarray:
    vector = np.zeros(512, dtype=np.float64)
    vector[0] = score
    vector[1] = math.sqrt(max(0.0, 1.0 - score * score))
    return vector


def serialize(vector: np.ndarray) -> str:
    return json.dumps(vector.astype(float).tolist(), separators=(",", ":"))


def add_gallery(db, student: Student, admin: User, scores: list[float], hash_prefix: str) -> None:
    for index in range(20):
        score = scores[index] if index < len(scores) else scores[-1]
        template = FaceTemplate(
            studentId=student.studentId,
            templatePath=f"storage/test/{student.studentId}/{index}.jpg",
            encodingData=None,
            encodingVersion=None,
            sampleIndex=index + 1,
            status="DeepRecovery",
            isActive=True,
            createdByUserId=admin.userId,
        )
        db.add(template)
        db.flush()
        source_hash = hashlib.sha256(f"{hash_prefix}-{index}".encode()).hexdigest()
        db.add(
            FaceTemplateEmbedding(
                faceTemplateId=template.templateId,
                studentId=student.studentId,
                encodingVersion="arcface_v1",
                embeddingData=serialize(unit_vector(score)),
                embeddingDimension=512,
                modelName="buffalo_l",
                sourceImageSha256=source_hash,
                l2Norm=1.0,
                isActive=True,
            )
        )


def controlled_candidates(student_scores: dict[int, list[float]]) -> list[matching.DeepMatchCandidate]:
    candidates: list[matching.DeepMatchCandidate] = []
    next_id = 1
    for student_id, scores in student_scores.items():
        student = Student(
            studentId=student_id,
            rollNo=f"P107C-{student_id}",
            fullName=f"Student {student_id}",
            departmentId=1,
            classId=1,
            yearSemester="Test",
            section="T",
            status="Active",
        )
        for score in scores:
            template = FaceTemplate(
                templateId=next_id,
                studentId=student_id,
                status="DeepRecovery",
                isActive=True,
            )
            embedding = FaceTemplateEmbedding(
                faceTemplateEmbeddingId=next_id,
                faceTemplateId=next_id,
                studentId=student_id,
                encodingVersion="arcface_v1",
                embeddingData=serialize(unit_vector(score)),
                embeddingDimension=512,
                modelName="buffalo_l",
                sourceImageSha256=hashlib.sha256(f"controlled-{next_id}".encode()).hexdigest(),
                l2Norm=1.0,
                isActive=True,
            )
            candidates.append(
                matching.DeepMatchCandidate(
                    embedding=embedding,
                    template=template,
                    student=student,
                    vector=unit_vector(score),
                )
            )
            next_id += 1
    return candidates


class ControlledDeepService:
    def encode_image_bytes(self, _content: bytes) -> DeepEncodingResult:
        return DeepEncodingResult(
            success=True,
            status="Encoded",
            message="controlled",
            haarFaceCount=1,
            deepFaceCount=1,
            embeddingDimension=512,
            l2Norm=1.0,
            processingMilliseconds=1.0,
            embedding=unit_vector(1.0).astype(np.float32),
        )


def exception_status(callable_) -> int | None:
    try:
        callable_()
    except HTTPException as exc:
        return exc.status_code
    return None


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="fdas-phase10-7c-") as temp_directory:
        database_path = Path(temp_directory) / "isolated.db"
        engine = create_engine(
            f"sqlite:///{database_path.as_posix()}",
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(bind=engine)
        TestSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)

        with TestSession() as db:
            department_one = Department(departmentId=1, departmentName="Calibration One", status="Active")
            department_two = Department(departmentId=2, departmentName="Calibration Two", status="Active")
            class_one = ClassRoom(
                classId=1,
                className="Calibration One",
                departmentId=1,
                yearSemester="Test",
                section="T",
                status="Active",
            )
            class_two = ClassRoom(
                classId=2,
                className="Calibration Two",
                departmentId=2,
                yearSemester="Test",
                section="T",
                status="Active",
            )
            admin_role = Role(roleId=1, roleName="Admin")
            user_role = Role(roleId=2, roleName="User")
            admin = User(
                userId=1,
                fullName="Calibration Admin",
                email="calibration.admin@fdas.local",
                passwordHash="not-used",
                roleId=1,
                status="Approved",
                accessScope="AllDepartments",
            )
            operator = User(
                userId=2,
                fullName="Calibration Operator",
                email="calibration.operator@fdas.local",
                passwordHash="not-used",
                roleId=2,
                status="Approved",
                accessScope="Department",
                assignedDepartmentId=1,
            )
            students = [
                Student(
                    studentId=student_id,
                    rollNo=f"P107C-{student_id}",
                    fullName=f"Student {student_id}",
                    departmentId=department_id,
                    classId=department_id,
                    yearSemester="Test",
                    section="T",
                    status="Active",
                )
                for student_id, department_id in ((100, 1), (101, 1), (102, 2), (103, 1))
            ]
            db.add_all(
                [
                    department_one,
                    department_two,
                    class_one,
                    class_two,
                    admin_role,
                    user_role,
                    admin,
                    operator,
                    *students,
                ]
            )
            db.flush()
            add_gallery(db, students[0], admin, [0.90, 0.89, 0.88, 0.86], "student-100")
            add_gallery(db, students[1], admin, [0.80, 0.79, 0.78, 0.75], "student-101")
            add_gallery(db, students[2], admin, [0.95, 0.94, 0.93, 0.90], "student-102")
            add_gallery(db, students[3], admin, [0.99, 0.98, 0.97, 0.95], "student-103")
            last_incomplete = (
                db.query(FaceTemplateEmbedding)
                .filter(FaceTemplateEmbedding.studentId == 103)
                .order_by(FaceTemplateEmbedding.faceTemplateEmbeddingId.desc())
                .first()
            )
            db.delete(last_incomplete)
            db.commit()

        query = unit_vector(1.0)
        matched_candidates = controlled_candidates({100: [0.90, 0.89, 0.88], 101: [0.80, 0.79, 0.78]})
        ambiguous_candidates = controlled_candidates({100: [0.90, 0.89, 0.88], 101: [0.85, 0.84, 0.83]})
        below_candidates = controlled_candidates({100: [0.84, 0.83, 0.82], 101: [0.83, 0.82, 0.81]})

        matched = matching.classify_deep_embedding(query, matched_candidates, expected_student_id=100)
        ambiguous = matching.classify_deep_embedding(query, ambiguous_candidates, expected_student_id=100)
        below = matching.classify_deep_embedding(query, below_candidates, expected_student_id=100)
        method_scores = {
            method: matching.rank_deep_candidates(query, matched_candidates, method)[0].score
            for method in matching.DEEP_SCORING_METHODS
        }

        leakage_candidates = controlled_candidates({100: [1.0, 0.90, 0.89], 101: [0.80, 0.79, 0.78]})
        duplicated_hash = leakage_candidates[0].embedding.sourceImageSha256
        leakage_candidates[1].embedding.sourceImageSha256 = duplicated_hash
        filtered, excluded_count = matching.exclude_query_leakage(
            leakage_candidates,
            excluded_embedding_id=leakage_candidates[0].embedding.faceTemplateEmbeddingId,
            excluded_source_sha256=duplicated_hash,
        )

        with TestSession() as db:
            admin = db.query(User).filter(User.userId == 1).one()
            operator = db.query(User).filter(User.userId == 2).one()
            department_one_candidates = matching.load_deep_match_candidates(db, operator, 1)
            department_two_blocked = exception_status(
                lambda: matching.load_deep_match_candidates(db, operator, 2)
            )
            department_two_candidates = matching.load_deep_match_candidates(db, admin, 2)
            attendance_before = db.query(AttendanceRecord).count()
            with patch.object(matching, "get_deep_face_service", return_value=ControlledDeepService()):
                diagnostic = matching.diagnose_deep_face_bytes(
                    db,
                    admin,
                    1,
                    100,
                    b"genuine-query",
                )
            attendance_after = db.query(AttendanceRecord).count()

        policy = matching.deep_matching_policy()
        result = {
            "deep_scoring_method_is_mean_top_3": DEEP_MATCH_SCORING_METHOD == "mean_top_3",
            "preliminary_threshold_is_0_85": DEEP_MATCH_THRESHOLD == 0.85,
            "preliminary_margin_is_0_07": DEEP_MATCH_MIN_IDENTITY_MARGIN == 0.07,
            "all_scoring_methods_available": set(method_scores) == set(matching.DEEP_SCORING_METHODS),
            "mean_top_3_calculation_correct": method_scores["mean_top_3"] == 0.89,
            "threshold_rule_matches": matched["status"] == "DiagnosticMatched" and matched["matched"] is True,
            "ambiguous_match_rule": ambiguous["status"] == "AmbiguousMatch" and ambiguous["matched"] is False,
            "below_threshold_precedes_margin": below["status"] == "MatchBelowThreshold" and below["matched"] is False,
            "exact_embedding_and_source_hash_excluded": excluded_count == 2 and len(filtered) == 4,
            "candidate_scope_excludes_incomplete_and_other_department": (
                {item.student.studentId for item in department_one_candidates} == {100, 101}
                and len(department_one_candidates) == 40
            ),
            "department_authorization_preserved": department_two_blocked == 403,
            "admin_cross_department_scope_valid": (
                {item.student.studentId for item in department_two_candidates} == {102}
                and len(department_two_candidates) == 20
            ),
            "diagnostic_mode_creates_no_attendance": (
                attendance_before == attendance_after == 0
                and diagnostic["attendanceCreated"] is False
                and diagnostic["persistentWrite"] is False
            ),
            "diagnostic_uses_selected_policy": (
                diagnostic["scoringMethod"] == "mean_top_3"
                and diagnostic["thresholdUsed"] == 0.85
                and diagnostic["requiredMargin"] == 0.07
            ),
            "final_deep_activation_released_hold": (
                DEEP_RECOGNITION_ACTIVE_FOR_ATTENDANCE is True
                and IDENTITY_MATCHING_SAFETY_HOLD is False
                and policy["attendanceSafetyHold"] is False
                and policy["activeForAttendance"] is True
            ),
        }
        engine.dispose()

    result["phase10_7c_passed"] = all(bool(value) for value in result.values())
    for name, passed in result.items():
        print(f"{name}={bool(passed)}")
    if not result["phase10_7c_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
