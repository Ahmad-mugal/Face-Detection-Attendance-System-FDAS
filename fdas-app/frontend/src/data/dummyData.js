// ============================================================
// FDAS — Dummy Data (Phase 1 Static Frontend)
// All data here is placeholder/demonstration only.
// Real data will come from FastAPI backend in later phases.
// ============================================================

export const DEPARTMENTS = [
  'Computer Science',
  'Mathematics',
  'Physics',
  'Chemistry',
  'English',
  'Islamic Studies',
  'Commerce',
];

export const CLASSES = [
  { id: 1, name: 'BSCS-2022', department: 'Computer Science', students: 45, isArchived: false, createdAt: '2022-09-01' },
  { id: 2, name: 'BSCS-2023', department: 'Computer Science', students: 52, isArchived: false, createdAt: '2023-09-01' },
  { id: 3, name: 'BSCS-2024', department: 'Computer Science', students: 48, isArchived: false, createdAt: '2024-09-01' },
  { id: 4, name: 'BSMath-2022', department: 'Mathematics', students: 38, isArchived: false, createdAt: '2022-09-01' },
  { id: 5, name: 'BSMath-2023', department: 'Mathematics', students: 41, isArchived: false, createdAt: '2023-09-01' },
  { id: 6, name: 'BSPhysics-2022', department: 'Physics', students: 35, isArchived: false, createdAt: '2022-09-01' },
  { id: 7, name: 'BSPhysics-2023', department: 'Physics', students: 39, isArchived: false, createdAt: '2023-09-01' },
  { id: 8, name: 'BSCS-2021', department: 'Computer Science', students: 50, isArchived: true, createdAt: '2021-09-01' },
];

export const STUDENTS = [
  { id: 1, name: 'Muhammad Arbaz', rollNumber: 'CS-2022-001', department: 'Computer Science', classId: 1, className: 'BSCS-2022', email: 'arbaz@student.igc.edu.pk', enrolled: true, enrolledAt: '2024-01-15', photo: null },
  { id: 2, name: 'Sarah Ahmed', rollNumber: 'CS-2022-002', department: 'Computer Science', classId: 1, className: 'BSCS-2022', email: 'sarah@student.igc.edu.pk', enrolled: true, enrolledAt: '2024-01-15', photo: null },
  { id: 3, name: 'Usman Tariq', rollNumber: 'CS-2022-003', department: 'Computer Science', classId: 1, className: 'BSCS-2022', email: 'usman@student.igc.edu.pk', enrolled: true, enrolledAt: '2024-01-16', photo: null },
  { id: 4, name: 'Fatima Malik', rollNumber: 'CS-2022-004', department: 'Computer Science', classId: 1, className: 'BSCS-2022', email: 'fatima@student.igc.edu.pk', enrolled: false, enrolledAt: null, photo: null },
  { id: 5, name: 'Ali Hassan', rollNumber: 'CS-2022-005', department: 'Computer Science', classId: 1, className: 'BSCS-2022', email: 'ali@student.igc.edu.pk', enrolled: true, enrolledAt: '2024-01-17', photo: null },
  { id: 6, name: 'Zainab Khan', rollNumber: 'CS-2023-001', department: 'Computer Science', classId: 2, className: 'BSCS-2023', email: 'zainab@student.igc.edu.pk', enrolled: true, enrolledAt: '2024-02-01', photo: null },
  { id: 7, name: 'Hassan Raza', rollNumber: 'CS-2023-002', department: 'Computer Science', classId: 2, className: 'BSCS-2023', email: 'hassan@student.igc.edu.pk', enrolled: true, enrolledAt: '2024-02-01', photo: null },
  { id: 8, name: 'Ayesha Nawaz', rollNumber: 'CS-2023-003', department: 'Computer Science', classId: 2, className: 'BSCS-2023', email: 'ayesha@student.igc.edu.pk', enrolled: false, enrolledAt: null, photo: null },
  { id: 9, name: 'Omar Farooq', rollNumber: 'MATH-2022-001', department: 'Mathematics', classId: 4, className: 'BSMath-2022', email: 'omar@student.igc.edu.pk', enrolled: true, enrolledAt: '2024-01-20', photo: null },
  { id: 10, name: 'Nadia Iqbal', rollNumber: 'MATH-2022-002', department: 'Mathematics', classId: 4, className: 'BSMath-2022', email: 'nadia@student.igc.edu.pk', enrolled: true, enrolledAt: '2024-01-20', photo: null },
  { id: 11, name: 'Bilal Cheema', rollNumber: 'PHY-2022-001', department: 'Physics', classId: 6, className: 'BSPhysics-2022', email: 'bilal@student.igc.edu.pk', enrolled: true, enrolledAt: '2024-01-22', photo: null },
  { id: 12, name: 'Sana Aslam', rollNumber: 'PHY-2022-002', department: 'Physics', classId: 6, className: 'BSPhysics-2022', email: 'sana@student.igc.edu.pk', enrolled: false, enrolledAt: null, photo: null },
];

export const USERS = [
  { id: 1, fullName: 'Dr. Admin User', username: 'admin', email: 'admin@igc.edu.pk', role: 'admin', status: 'active', department: null, accessScope: 'ALL_DEPARTMENTS', lastUpdated: '2024-01-01' },
  { id: 2, fullName: 'Muhammad Tariq', username: 'tariq_cs', email: 'tariq@igc.edu.pk', role: 'operator', status: 'active', department: 'Computer Science', accessScope: 'DEPARTMENT_ONLY', lastUpdated: '2024-06-01' },
  { id: 3, fullName: 'Asma Bibi', username: 'asma_math', email: 'asma@igc.edu.pk', role: 'operator', status: 'active', department: 'Mathematics', accessScope: 'DEPARTMENT_ONLY', lastUpdated: '2024-06-01' },
  { id: 4, fullName: 'Kamran Akhtar', username: 'kamran', email: 'kamran@igc.edu.pk', role: 'operator', status: 'active', department: null, accessScope: 'ALL_DEPARTMENTS', lastUpdated: '2024-05-15' },
  { id: 5, fullName: 'Razia Sultana', username: 'razia_phy', email: 'razia@igc.edu.pk', role: 'operator', status: 'disabled', department: 'Physics', accessScope: 'DEPARTMENT_ONLY', lastUpdated: '2024-03-10' },
  { id: 6, fullName: 'Imran Butt', username: 'imran_chem', email: 'imran@igc.edu.pk', role: 'operator', status: 'disabled', department: 'Chemistry', accessScope: 'DEPARTMENT_ONLY', lastUpdated: '2024-02-20' },
];

export const PENDING_REQUESTS = [
  { id: 7, fullName: 'Salman Chaudhry', username: 'salman_eng', email: 'salman@igc.edu.pk', role: 'operator', requestedDepartment: 'English', status: 'pending', requestedAt: '2026-07-06T08:30:00' },
  { id: 8, fullName: 'Rubina Parveen', username: 'rubina_is', email: 'rubina@igc.edu.pk', role: 'operator', requestedDepartment: 'Islamic Studies', status: 'pending', requestedAt: '2026-07-07T11:15:00' },
  { id: 9, fullName: 'Junaid Ahmed', username: 'junaid_com', email: 'junaid@igc.edu.pk', role: 'operator', requestedDepartment: 'Commerce', status: 'pending', requestedAt: '2026-07-08T09:00:00' },
];

export const TIMINGS = [
  { id: 1, name: 'Morning A', department: 'Computer Science', startTime: '08:00', endTime: '09:30', createdAt: '2024-01-01' },
  { id: 2, name: 'Morning B', department: 'Computer Science', startTime: '09:45', endTime: '11:15', createdAt: '2024-01-01' },
  { id: 3, name: 'Afternoon A', department: 'Computer Science', startTime: '12:00', endTime: '13:30', createdAt: '2024-01-01' },
  { id: 4, name: 'Morning A', department: 'Mathematics', startTime: '08:30', endTime: '10:00', createdAt: '2024-01-01' },
  { id: 5, name: 'Morning B', department: 'Mathematics', startTime: '10:15', endTime: '11:45', createdAt: '2024-01-01' },
  { id: 6, name: 'Morning A', department: 'Physics', startTime: '08:00', endTime: '09:30', createdAt: '2024-01-01' },
  { id: 7, name: 'Afternoon A', department: 'Physics', startTime: '13:00', endTime: '14:30', createdAt: '2024-01-01' },
];

export const SESSIONS = [
  { id: 1, departmentId: 'Computer Science', classId: 1, className: 'BSCS-2022', startedByUserId: 2, startedByName: 'Muhammad Tariq', scheduledStartTime: '2026-07-08T08:00', scheduledEndTime: '2026-07-08T09:30', actualStartTime: '2026-07-08T08:03', actualEndTime: null, status: 'active', createdDate: '2026-07-08' },
  { id: 2, departmentId: 'Mathematics', classId: 4, className: 'BSMath-2022', startedByUserId: 3, startedByName: 'Asma Bibi', scheduledStartTime: '2026-07-08T08:30', scheduledEndTime: '2026-07-08T10:00', actualStartTime: '2026-07-08T08:32', actualEndTime: '2026-07-08T10:05', status: 'closed', createdDate: '2026-07-08' },
  { id: 3, departmentId: 'Computer Science', classId: 2, className: 'BSCS-2023', startedByUserId: 2, startedByName: 'Muhammad Tariq', scheduledStartTime: '2026-07-07T09:45', scheduledEndTime: '2026-07-07T11:15', actualStartTime: '2026-07-07T09:47', actualEndTime: '2026-07-07T11:20', status: 'closed', createdDate: '2026-07-07' },
];

export const ATTENDANCE_RECORDS = [
  { id: 1, sessionId: 1, studentId: 1, studentName: 'Muhammad Arbaz', rollNumber: 'CS-2022-001', departmentId: 'Computer Science', classId: 1, markedAt: '2026-07-08T08:06:12', status: 'present', recognitionConfidence: 0.97, livenessStatus: 'passed' },
  { id: 2, sessionId: 1, studentId: 2, studentName: 'Sarah Ahmed', rollNumber: 'CS-2022-002', departmentId: 'Computer Science', classId: 1, markedAt: '2026-07-08T08:09:45', status: 'present', recognitionConfidence: 0.94, livenessStatus: 'passed' },
  { id: 3, sessionId: 1, studentId: 3, studentName: 'Usman Tariq', rollNumber: 'CS-2022-003', departmentId: 'Computer Science', classId: 1, markedAt: '2026-07-08T08:12:30', status: 'present', recognitionConfidence: 0.91, livenessStatus: 'passed' },
  { id: 4, sessionId: 1, studentId: 5, studentName: 'Ali Hassan', rollNumber: 'CS-2022-005', departmentId: 'Computer Science', classId: 1, markedAt: '2026-07-08T08:15:10', status: 'present', recognitionConfidence: 0.89, livenessStatus: 'passed' },
];

export const ANALYTICS_WEEKLY = [
  { day: 'Mon', present: 85, absent: 15, total: 100 },
  { day: 'Tue', present: 88, absent: 12, total: 100 },
  { day: 'Wed', present: 82, absent: 18, total: 100 },
  { day: 'Thu', present: 90, absent: 10, total: 100 },
  { day: 'Fri', present: 87, absent: 13, total: 100 },
  { day: 'Sat', present: 75, absent: 25, total: 100 },
  { day: 'Sun', present: 89, absent: 11, total: 100 },
];

export const ANALYTICS_MONTHLY = [
  { month: 'Jan', present: 87, absent: 13 },
  { month: 'Feb', present: 85, absent: 15 },
  { month: 'Mar', present: 90, absent: 10 },
  { month: 'Apr', present: 88, absent: 12 },
  { month: 'May', present: 86, absent: 14 },
  { month: 'Jun', present: 91, absent: 9 },
];

// Admin Dashboard stats
export const ADMIN_STATS = {
  totalStudents: 1245,
  presentToday: 1102,
  absentToday: 143,
  recognitionAccuracy: 99.4,
  totalClasses: 7,
  activeOperators: 4,
  activeSessions: 1,
};

// User dashboard stats (for CS department operator)
export const USER_STATS = {
  totalStudentsInDept: 145,
  presentToday: 132,
  absentToday: 13,
  activeSession: 'Morning A',
  attendanceRate: 91,
  enrolledStudents: 138,
  unenrolledStudents: 7,
};

// Live attendance log (simulated)
export const LIVE_LOG = [
  { id: 1, studentName: 'Muhammad Arbaz', rollNumber: 'CS-2022-001', markedAt: '08:06 AM', confidence: 0.97 },
  { id: 2, studentName: 'Sarah Ahmed', rollNumber: 'CS-2022-002', markedAt: '08:09 AM', confidence: 0.94 },
  { id: 3, studentName: 'Usman Tariq', rollNumber: 'CS-2022-003', markedAt: '08:12 AM', confidence: 0.91 },
  { id: 4, studentName: 'Ali Hassan', rollNumber: 'CS-2022-005', markedAt: '08:15 AM', confidence: 0.89 },
  { id: 5, studentName: 'Zainab Khan', rollNumber: 'CS-2023-001', markedAt: '08:17 AM', confidence: 0.96 },
  { id: 6, studentName: 'Hassan Raza', rollNumber: 'CS-2023-002', markedAt: '08:20 AM', confidence: 0.93 },
  { id: 7, studentName: 'Omar Farooq', rollNumber: 'MATH-2022-001', markedAt: '08:22 AM', confidence: 0.88 },
];
