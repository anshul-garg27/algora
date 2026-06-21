"""
Main driver and test cases for the Course Registration System.
Exercises the core operations and verifies the design is correct.
"""

from datetime import datetime
from models import Student, Course, EnrollmentStatus
from service import (
    CourseRegistrationService,
    StudentNotFoundError,
    CourseNotFoundError,
    DuplicateEnrollmentError,
    EnrollmentNotAllowedError,
    AlreadyDroppedError,
)
from validator import SimpleValidator


def main():
    print("=" * 70)
    print("STUDENT COURSE REGISTRATION SYSTEM — LLD Test Suite")
    print("=" * 70)

    # Setup: Create service with simple validator
    validator = SimpleValidator()
    svc = CourseRegistrationService(validator)

    # Create students
    alice = Student(
        id="s001",
        name="Alice Chen",
        email="alice@university.edu",
        major="Computer Science",
    )
    bob = Student(
        id="s002",
        name="Bob Smith",
        email="bob@university.edu",
        major="Mathematics",
    )
    charlie = Student(
        id="s003",
        name="Charlie Davis",
        email="charlie@university.edu",
        major="Computer Science",
    )
    diana = Student(
        id="s004",
        name="Diana Prince",
        email="diana@university.edu",
        major="Engineering",
    )

    svc.add_student(alice)
    svc.add_student(bob)
    svc.add_student(charlie)
    svc.add_student(diana)

    # Simulate some students have taken prerequisites
    alice.complete_course("CS101")
    alice.complete_course("MATH101")
    bob.complete_course("CS101")
    bob.complete_course("MATH101")
    # Charlie has taken both
    charlie.complete_course("CS101")
    charlie.complete_course("MATH101")

    # Create courses
    cs201 = Course(
        id="cs201",
        name="Data Structures",
        instructor="Dr. Johnson",
        capacity=2,  # Small capacity for testing
        schedule="MWF 10:00-11:00",
        prerequisites=["CS101"],
    )

    math301 = Course(
        id="math301",
        name="Discrete Math",
        instructor="Dr. Martinez",
        capacity=3,
        schedule="TTh 14:00-15:30",
        prerequisites=["MATH101"],
    )

    svc.add_course(cs201)
    svc.add_course(math301)

    print("\n### TEST 1: Happy Path — Student enrolls successfully ####\n")
    print(f"Alice enrolls in {cs201.name} (capacity={cs201.capacity})...")
    try:
        enr_alice = svc.enroll("s001", "cs201")
        print(f"✓ Enrollment created: {enr_alice.id}")
        print(f"  Course {cs201.id} now has {cs201.enrolled_count}/{cs201.capacity} seats filled")
        assert enr_alice.student_id == "s001"
        assert enr_alice.course_id == "cs201"
        assert enr_alice.status == EnrollmentStatus.ACTIVE
    except Exception as e:
        print(f"✗ FAILED: {e}")
        return False

    print("\n### TEST 2: Duplicate Enrollment — Student tries to enroll twice ####\n")
    print(f"Alice tries to enroll in {cs201.name} again...")
    try:
        svc.enroll("s001", "cs201")
        print(f"✗ FAILED: Should have raised DuplicateEnrollmentError")
        return False
    except DuplicateEnrollmentError as e:
        print(f"✓ Correctly rejected: {e}")

    print("\n### TEST 3: Capacity Limit — Fill course and reject over-capacity ####\n")
    print(f"Bob enrolls in {cs201.name} (filling the course)...")
    try:
        enr_bob = svc.enroll("s002", "cs201")
        print(f"✓ Enrollment created: {enr_bob.id}")
        print(f"  Course {cs201.id} now has {cs201.enrolled_count}/{cs201.capacity} seats filled")
        assert cs201.enrolled_count == cs201.capacity
    except Exception as e:
        print(f"✗ FAILED: {e}")
        return False

    print(f"\nCharlie tries to enroll in {cs201.name} (course is full)...")
    try:
        svc.enroll("s003", "cs201")
        print(f"✗ FAILED: Should have raised EnrollmentNotAllowedError (capacity)")
        return False
    except EnrollmentNotAllowedError as e:
        print(f"✓ Correctly rejected: {e}")

    print("\n### TEST 4: Prerequisites — Student without prerequisites is rejected ####\n")
    print(f"Diana (missing CS101 prerequisite) tries to enroll in {cs201.name}...")
    try:
        svc.enroll("s004", "cs201")
        print(f"✗ FAILED: Should have raised EnrollmentNotAllowedError (prerequisites)")
        return False
    except EnrollmentNotAllowedError as e:
        print(f"✓ Correctly rejected: {e}")

    print("\n### TEST 5: Unenroll — Student drops course and seat becomes available ####\n")
    print(f"Alice drops {cs201.name}...")
    try:
        svc.unenroll(enr_alice.id)
        print(f"✓ Unenrolled successfully")
        print(f"  Course {cs201.id} now has {cs201.enrolled_count}/{cs201.capacity} seats filled")
        assert cs201.enrolled_count == 1
    except Exception as e:
        print(f"✗ FAILED: {e}")
        return False

    print(f"\nCharlie enrolls in {cs201.name} (now has capacity again)...")
    try:
        enr_charlie = svc.enroll("s003", "cs201")
        print(f"✓ Enrollment created: {enr_charlie.id}")
        print(f"  Course {cs201.id} now has {cs201.enrolled_count}/{cs201.capacity} seats filled")
        assert cs201.enrolled_count == 2
    except Exception as e:
        print(f"✗ FAILED: {e}")
        return False

    print("\n### TEST 6: Student Not Found ####\n")
    print("Alice tries to enroll in a course but her ID is invalid...")
    try:
        svc.enroll("s999", "cs201")
        print(f"✗ FAILED: Should have raised StudentNotFoundError")
        return False
    except StudentNotFoundError as e:
        print(f"✓ Correctly rejected: {e}")

    print("\n### TEST 7: Course Not Found ####\n")
    print("Alice tries to enroll in a non-existent course...")
    try:
        svc.enroll("s001", "cs999")
        print(f"✗ FAILED: Should have raised CourseNotFoundError")
        return False
    except CourseNotFoundError as e:
        print(f"✓ Correctly rejected: {e}")

    print("\n### TEST 8: Browse Available Courses ####\n")
    print(f"Alice browses available courses...")
    available = svc.get_available_courses("s001")
    print(f"✓ Available courses for Alice: {len(available)}")
    for course in available:
        print(f"  - {course.name} ({course.available_seats()} seats available)")

    print("\n### TEST 9: Get Student Enrollments ####\n")
    print(f"Charlie's current enrollments:")
    enrollments = svc.get_student_enrollments("s003")
    print(f"✓ Enrolled in {len(enrollments)} course(s):")
    for enr in enrollments:
        course = svc._courses[enr.course_id]
        print(f"  - {course.name} (enrolled on {enr.enrollment_date})")

    print("\n### TEST 10: Get Course Enrollments ####\n")
    print(f"Students enrolled in {cs201.name}:")
    enrollments = svc.get_course_enrollments("cs201")
    print(f"✓ {len(enrollments)} student(s) enrolled:")
    for enr in enrollments:
        student = svc._students[enr.student_id]
        print(f"  - {student.name}")

    print("\n" + "=" * 70)
    print("ALL TESTS PASSED ✓")
    print("=" * 70)
    return True


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
