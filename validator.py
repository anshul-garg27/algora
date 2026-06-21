"""
Enrollment validation logic — extracted as a Strategy so the main service
doesn't bloat with if-statements and business rule checks.
"""

from abc import ABC, abstractmethod
from models import Student, Course


# ── STRATEGY INTERFACE ──────────────────────────────────────────────────────

class EnrollmentValidator(ABC):
    """
    ── WHY THIS CLASS ──────────────────────────────────────────────────────────
    This is the Strategy pattern. The CourseRegistrationService asks the
    validator "can this student enroll in this course?" without knowing or
    caring HOW the validation happens. New business rules (check GPA, check
    time conflicts, check major restrictions) are new classes, not changes
    to the core service.

    🎙️ "I extract validation as a Strategy interface. The service doesn't
    know whether it's checking prerequisites, GPA, or time conflicts — it just
    calls validator.can_enroll() and gets a boolean back. New rules are new
    classes, the core service never changes. This is the Open/Closed principle
    at work."
    """

    @abstractmethod
    def can_enroll(self, student: Student, course: Course) -> bool:
        """
        Check if a student is allowed to enroll in a course.

        Returns:
            True if student can enroll, False otherwise.

        Raises:
            (Subclass may raise domain-specific exceptions.)
        """
        pass


# ── CONCRETE STRATEGY ───────────────────────────────────────────────────────

class SimpleValidator(EnrollmentValidator):
    """
    ── WHY THIS CLASS ──────────────────────────────────────────────────────────
    The basic validator: check that the student has completed all
    prerequisites and the course has available capacity.

    🎙️ "This is the simple validator — two checks: prerequisites and capacity.
    If the business wants to add a check for full-time status or major
    restrictions, that's a new validator class. The service code never changes."
    """

    def can_enroll(self, student: Student, course: Course) -> bool:
        """
        Check prerequisites and capacity.

        Returns:
            True if student meets all prerequisites AND course has capacity.
        """
        # WHY: Check prerequisites first. This is a domain rule, not a race.
        #      All students are subject to the same prerequisite list.
        if not self._check_prerequisites(student, course):
            return False

        # WHY: Check capacity second. This CAN race in multi-threaded context.
        #      Two threads can both see capacity=1, both return True here.
        #      The race is resolved at enrollment creation time (inside a lock in §9).
        if not course.has_capacity():
            return False

        return True

    def _check_prerequisites(self, student: Student, course: Course) -> bool:
        """
        Verify student has completed all prerequisite courses.

        WHY: Extracted as a separate method for clarity and testability.
        """
        for prereq_id in course.prerequisites:
            if not student.has_completed(prereq_id):
                return False
        return True
