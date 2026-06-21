"""
CourseRegistrationService — the orchestrator for the course registration system.
This is where the main operations (enroll, unenroll, browse) are coordinated.
"""

import itertools
from contextlib import contextmanager
from datetime import datetime
from typing import Dict, List, Optional, Iterator
from models import Student, Course, Enrollment, EnrollmentStatus
from validator import EnrollmentValidator


# ── CUSTOM EXCEPTIONS ───────────────────────────────────────────────────────

class StudentNotFoundError(Exception):
    """Raised when a student ID is not in the system."""
    pass


class CourseNotFoundError(Exception):
    """Raised when a course ID is not in the system."""
    pass


class EnrollmentNotFoundError(Exception):
    """Raised when an enrollment ID is not found."""
    pass


class DuplicateEnrollmentError(Exception):
    """Raised when a student tries to enroll in a course they're already in."""
    pass


class EnrollmentNotAllowedError(Exception):
    """Raised when a student does not meet prerequisites or course is full."""
    pass


class AlreadyDroppedError(Exception):
    """Raised when trying to drop an enrollment that's already dropped."""
    pass


# ── MAIN SERVICE ────────────────────────────────────────────────────────────

class CourseRegistrationService:
    """
    ── WHY THIS CLASS ──────────────────────────────────────────────────────────
    The orchestrator. Owns the registry of all students, courses, and
    enrollments. Coordinates validation, capacity management, and enrollment
    creation. It's the single point of coordination — every request flows
    through here.

    🎙️ "The CourseRegistrationService is the brain of the system. Every
    operation — browse, enroll, drop — goes through it. It owns the
    registries (students, courses, enrollments) and makes all the decisions
    about whether an enrollment is allowed."
    """

    def __init__(self, validator: EnrollmentValidator, now_fn=datetime.now):
        """
        Initialize the service with a validator strategy and a clock function.

        Args:
            validator: EnrollmentValidator (e.g., SimpleValidator).
            now_fn: A callable that returns the current datetime.
                    (Allows tests to control time without sleeping.)
        """
        self._students: Dict[str, Student] = {}
        self._courses: Dict[str, Course] = {}
        self._enrollments: Dict[str, Enrollment] = {}
        self._student_enrollments: Dict[str, List[Enrollment]] = {}
        self._validator = validator
        self._now_fn = now_fn
        self._id_counter = itertools.count(1)

    # ── HELPER: No-op lock hook (overridden in thread-safe subclass) ────────
    @contextmanager
    def _lock(self, course_id: str) -> Iterator[None]:
        """
        WHY: This method does nothing in the clean version, but the thread-safe
             version replaces it with a real lock. Zero lock code in this file.
        🎙️ "This is a placeholder method — it does nothing here. In the
             thread-safe version, I override this with a real lock per course."
        """
        yield

    # ── HELPER: Generate unique IDs for testing ────────────────────────────
    def _make_id(self, prefix: str) -> str:
        """
        WHY: Use a counter for IDs in tests — enr-1, enr-2 — so assertions
             are easy to read. In production, switch to UUID.
        """
        return f"{prefix}-{next(self._id_counter)}"

    # ── PUBLIC API ──────────────────────────────────────────────────────────

    def add_student(self, student: Student) -> None:
        """Register a student in the system."""
        if student.id in self._students:
            raise ValueError(f"Student {student.id} already exists")
        self._students[student.id] = student
        self._student_enrollments[student.id] = []

    def add_course(self, course: Course) -> None:
        """Add a course to the system."""
        if course.id in self._courses:
            raise ValueError(f"Course {course.id} already exists")
        self._courses[course.id] = course

    def enroll(self, student_id: str, course_id: str) -> Enrollment:
        """
        Enroll a student in a course.

        This is the critical operation — check-then-act under concurrency.
        In the single-threaded version (here), checks and enrollment creation
        are separate. In the thread-safe version (§9), the entire method is
        inside a lock.

        Args:
            student_id: The student's ID.
            course_id: The course's ID.

        Returns:
            The created Enrollment object.

        Raises:
            StudentNotFoundError: If student_id does not exist.
            CourseNotFoundError: If course_id does not exist.
            DuplicateEnrollmentError: If student is already enrolled in this course.
            EnrollmentNotAllowedError: If prerequisites not met or course full.
        """
        # WHY: Guard checks first — fail fast if inputs are invalid.
        #      Lookups are safe, no state changes yet.
        student = self._get_student_or_raise(student_id)
        course = self._get_course_or_raise(course_id)

        # WHY: Check for duplicate enrollment BEFORE asking the validator.
        #      This is a domain rule: one enrollment per (student, course) pair.
        #      In multi-threaded context, this check is also racy — we re-check
        #      inside the lock in §9.
        if self._has_active_enrollment(student_id, course_id):
            raise DuplicateEnrollmentError(
                f"Student {student_id} is already enrolled in {course_id}"
            )

        # WHY: Ask the validator: can this student enroll?
        #      The validator checks prerequisites and capacity.
        #      Again, the capacity check can race — both threads see available.
        #      We'll lock this entire section in §9.
        if not self._validator.can_enroll(student, course):
            raise EnrollmentNotAllowedError(
                f"Student {student_id} cannot enroll in {course_id} "
                f"(prerequisites or capacity)"
            )

        # ───────────────────────────────────────────────────────────────────
        # ✨ CRITICAL SECTION: From here to return, we mutate state.
        #    In §9 (thread-safe), this entire section is inside a lock.
        # ───────────────────────────────────────────────────────────────────

        # WHY: Inside the lock (or here in single-threaded): re-check capacity.
        #      The capacity might have changed since the validator checked it
        #      (in multi-threaded context, another thread might have enrolled
        #      the last student while we were outside the lock).
        #      This re-check inside the lock is what prevents double-booking.
        if not course.has_capacity():
            raise EnrollmentNotAllowedError(
                f"Course {course_id} is at capacity (no seats available)"
            )

        # Create the enrollment record.
        enrollment_id = self._make_id("enr")
        enrollment = Enrollment(
            id=enrollment_id,
            student_id=student_id,
            course_id=course_id,
            enrollment_date=self._now_fn(),
            status=EnrollmentStatus.ACTIVE,
        )

        # WHY: Update all three indexes: enrollments, student_enrollments,
        #      course.enrolled_count. All three must be updated or state is
        #      inconsistent. In a real system with a database, this might be
        #      a single SQL INSERT with a foreign key check and a trigger to
        #      increment the course counter.
        self._enrollments[enrollment_id] = enrollment
        self._student_enrollments[student_id].append(enrollment)
        course.add_enrollment()

        return enrollment

    def unenroll(self, enrollment_id: str) -> None:
        """
        Drop a student from a course.

        Args:
            enrollment_id: The enrollment ID to drop.

        Raises:
            EnrollmentNotFoundError: If enrollment_id does not exist.
            AlreadyDroppedError: If the enrollment is already dropped.
        """
        # WHY: Find the enrollment.
        enrollment = self._get_enrollment_or_raise(enrollment_id)

        # WHY: Guard against dropping twice.
        if enrollment.status != EnrollmentStatus.ACTIVE:
            raise AlreadyDroppedError(
                f"Enrollment {enrollment_id} is already dropped"
            )

        # WHY: Get the course to decrement its counter.
        course = self._get_course_or_raise(enrollment.course_id)

        # WHY: Mark as dropped (or delete from enrollments).
        #      For this design, we delete. In a real system, we'd mark status=DROPPED.
        del self._enrollments[enrollment_id]
        self._student_enrollments[enrollment.student_id].remove(enrollment)
        course.remove_enrollment()

    def get_student_enrollments(self, student_id: str) -> List[Enrollment]:
        """
        Get all ACTIVE enrollments for a student.

        Args:
            student_id: The student's ID.

        Returns:
            List of Enrollment objects (active only).

        Raises:
            StudentNotFoundError: If student_id does not exist.
        """
        self._get_student_or_raise(student_id)  # Validate student exists
        return [
            enr for enr in self._student_enrollments.get(student_id, [])
            if enr.is_active()
        ]

    def get_course_enrollments(self, course_id: str) -> List[Enrollment]:
        """
        Get all ACTIVE enrollments in a course.

        Args:
            course_id: The course's ID.

        Returns:
            List of Enrollment objects (active only).

        Raises:
            CourseNotFoundError: If course_id does not exist.
        """
        self._get_course_or_raise(course_id)  # Validate course exists
        return [
            enr for enr in self._enrollments.values()
            if enr.course_id == course_id and enr.is_active()
        ]

    def get_available_courses(self, student_id: str) -> List[Course]:
        """
        Get all courses a student can still enroll in.

        Args:
            student_id: The student's ID.

        Returns:
            List of Course objects with available capacity that student
            hasn't enrolled in and meets prerequisites for.

        Raises:
            StudentNotFoundError: If student_id does not exist.
        """
        student = self._get_student_or_raise(student_id)
        available = []

        for course in self._courses.values():
            # Skip if already enrolled
            if self._has_active_enrollment(student_id, course.id):
                continue

            # Skip if no capacity
            if not course.has_capacity():
                continue

            # Skip if prerequisites not met
            if not self._validator.can_enroll(student, course):
                continue

            available.append(course)

        return available

    # ── HELPER METHODS ──────────────────────────────────────────────────────

    def _get_student_or_raise(self, student_id: str) -> Student:
        if student_id not in self._students:
            raise StudentNotFoundError(f"Student {student_id} not found")
        return self._students[student_id]

    def _get_course_or_raise(self, course_id: str) -> Course:
        if course_id not in self._courses:
            raise CourseNotFoundError(f"Course {course_id} not found")
        return self._courses[course_id]

    def _get_enrollment_or_raise(self, enrollment_id: str) -> Enrollment:
        if enrollment_id not in self._enrollments:
            raise EnrollmentNotFoundError(f"Enrollment {enrollment_id} not found")
        return self._enrollments[enrollment_id]

    def _has_active_enrollment(self, student_id: str, course_id: str) -> bool:
        """Check if student has an active enrollment in this course."""
        for enrollment in self._student_enrollments.get(student_id, []):
            if enrollment.course_id == course_id and enrollment.is_active():
                return True
        return False
