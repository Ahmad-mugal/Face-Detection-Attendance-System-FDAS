from pydantic import BaseModel


class StudentImportPreviewRow(BaseModel):
    rowNumber: int
    name: str
    email: str
    rollNo: str
    department: str
    className: str
    status: str
    issues: list[str]


class StudentImportPreview(BaseModel):
    headers: list[str]
    totalRows: int
    validRows: int
    invalidRows: int
    duplicateRows: int
    existingRows: int
    rows: list[StudentImportPreviewRow]


class ImportedStudent(BaseModel):
    studentId: int
    fullName: str
    email: str
    rollNo: str
    departmentName: str
    className: str
    faceStatus: str


class StudentImportResult(BaseModel):
    imported: int
    skippedInvalid: int
    skippedDuplicates: int
    skippedExisting: int
    students: list[ImportedStudent]
    message: str


class DeleteRecordResponse(BaseModel):
    deleted: bool
    message: str
