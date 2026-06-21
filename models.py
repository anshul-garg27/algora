"""
Core domain models for the Course Registration System.
These classes represent the nouns in the system: Student, Course, and Enrollment.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Set, List


# ── ENUMS ───────────────────────────────────────────────────────────────────
class EnrollmentStatus(Enum):
    """
    🎙️ "Enrollment has two states: ACTIVE means the student is registered,
    DROPPED means they withdrew."
    """
    ACTIVE = "active"
    DROPPED = "dropped"


# ── CORE ENTITIES ────────────────────────────────────────────────────────────

@dataclass
class Student:
    """
    🎙️ "A Student is just a reference — immutable profile data. We store their
    ID, name, and the courses they've already completed. That's all the system
    needs to make prerequisites decisions."
    """
    id: str
    name: str
    email: str
    major: str
    completed_courses: Set[str] = field(default_factory=set)

    def has_completed(self, course_id: str) -> bool:
        # WHY: O(1) lookup instead of O(n) list scan
        return course_id in self.completed_courses

    def complete_course(self, course_id: str) -> None:
        # WHY: Simulate student completing a course (for testing prerequisites)
        self.completed_courses.add(course_id)


@dataclass
class Course:
    """
    🎙️ "A Course holds static course info: name, instructor, capacity, schedule.
    The only mutable field is enrolled_count — that changes when students
    enroll or drop."
    """
    id: str
    name: str
    instructor: str
    capacity: int
    schedule: str  # e.g., "MWF 10:00-11:00"
    prerequisites: List[str] = field(default_factory=list)
    enrolled_count: int = 0

    def has_capacity(self) -> bool:
        # WHY: Simple check — is there a free seat?
        return self.enrolled_count < self.capacity

    def available_seats(self) -> int:
        # WHY: For human-readable output
        return self.capacity - self.enrolled_count

    def add_enrollment(self) -> None:
        # WHY: Increment counter when a student enrolls.
        #      This must be called inside a lock (in thread-safe version).
        if not self.has_capacity():
            raise ValueError(f"Course {self.id} is at capacity")
        self.enrolled_count += 1

    def remove_enrollment(self) -> None:
        # WHY: Decrement counter when a student drops.
        #      Safe to call even if already at zero (though shouldn't happen).
        if self.enrolled_count > 0:
            self.enrolled_count -= 1


@dataclass(frozen=True)
class Enrollment:
    """
    ── WHY THIS CLASS ──────────────────────────────────────────────────────────
    Enrollment is the commitment record. Once created, it proves the student is
    registered in the course. We mark it frozen so it cannot be mutated by
    accident — it's immutable, a value object.

    🎙️ "An Enrollment is the proof that a student is registered. Once I create
    it, it is frozen — it cannot change. This is the strongest signal that this
    is a committed transaction, not a tentative record."
    """
    id: str
    student_id: str
    course_id: str
    enrollment_date: datetime
    status: EnrollmentStatus = EnrollmentStatus.ACTIVE

    def is_active(self) -> bool:
        # WHY: Check if this enrollment is still valid
        return self.status == EnrollmentStatus.ACTIVE
