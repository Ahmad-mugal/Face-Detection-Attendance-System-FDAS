"""Read-only near-threshold distinct-person proxy audit for Phase 10.9B."""

from __future__ import annotations

import json

from app.analyze_phase10_9a import load_candidates
from app.config import DEEP_MATCH_SCORING_METHOD
from app.services.deep_face_matching import exclude_query_leakage, rank_deep_candidates


AUDIT_FLOOR = 0.75
CONTROLLED_THRESHOLD = 0.80
CONTROLLED_MARGIN = 0.10


def main() -> None:
    candidates = load_candidates()
    cases = []
    for query in candidates:
        leakage_safe, excluded_count = exclude_query_leakage(
            candidates,
            excluded_embedding_id=query.embedding.faceTemplateEmbeddingId,
            excluded_source_sha256=query.embedding.sourceImageSha256,
        )
        proxy_gallery = [
            candidate
            for candidate in leakage_safe
            if candidate.student.studentId != query.student.studentId
        ]
        ranking = rank_deep_candidates(query.vector, proxy_gallery, DEEP_MATCH_SCORING_METHOD)
        top = ranking[0]
        second = ranking[1]
        if top.score < AUDIT_FLOOR:
            continue
        margin = round(top.score - second.score, 6)
        score_passed = top.score >= CONTROLLED_THRESHOLD
        margin_passed = margin >= CONTROLLED_MARGIN
        cases.append(
            {
                "queryIdentity": {
                    "studentId": query.student.studentId,
                    "studentName": query.student.fullName,
                    "templateId": query.template.templateId,
                    "embeddingId": query.embedding.faceTemplateEmbeddingId,
                    "sampleIndex": query.template.sampleIndex,
                },
                "wrongTopCandidate": {
                    "studentId": top.student.studentId,
                    "studentName": top.student.fullName,
                    "score": top.score,
                },
                "secondCandidate": {
                    "studentId": second.student.studentId,
                    "studentName": second.student.fullName,
                    "score": second.score,
                },
                "identityMargin": margin,
                "topIdentityActuallyWrong": top.student.studentId != query.student.studentId,
                "excludedLeakageRows": excluded_count,
                "passesControlledScore": score_passed,
                "passesControlledMargin": margin_passed,
                "passesControlledCombinedRule": score_passed and margin_passed,
                "threeQueryConsensus": "Unavailable: this is a single stored-image proxy query, not a three-frame live burst.",
            }
        )

    cases.sort(
        key=lambda item: (
            -item["wrongTopCandidate"]["score"],
            item["queryIdentity"]["studentId"],
            item["queryIdentity"]["embeddingId"],
        )
    )
    print(
        json.dumps(
            {
                "phase": "10.9B",
                "readOnly": True,
                "scoringMethod": DEEP_MATCH_SCORING_METHOD,
                "auditFloor": AUDIT_FLOOR,
                "controlledThreshold": CONTROLLED_THRESHOLD,
                "controlledMargin": CONTROLLED_MARGIN,
                "nearThresholdCaseCount": len(cases),
                "highestDistinctProxyScore": cases[0]["wrongTopCandidate"]["score"] if cases else None,
                "highestDistinctProxyMargin": cases[0]["identityMargin"] if cases else None,
                "combinedRulePassCount": sum(item["passesControlledCombinedRule"] for item in cases),
                "cases": cases,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
