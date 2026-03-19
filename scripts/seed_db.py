"""
scripts/seed_db.py
Seed the database with sample data for development and testing.
Run: python scripts/seed_db.py
"""
import sys
import os
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from backend.core.database import SessionLocal, engine, Base
from backend.models.models import User, Circular, ExamSchedule, Subscription, NotificationChannel
from loguru import logger


def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        # ── Users ──────────────────────────────────────────────────
        users_data = [
            {"email": "student1@example.com", "name": "Ravi Kumar", "semester": 5, "branch": "CSE"},
            {"email": "student2@example.com", "name": "Priya Sharma", "semester": 3, "branch": "ECE"},
            {"email": "student3@example.com", "name": "Arjun Naik", "semester": 7, "branch": "ISE"},
        ]
        users = []
        for u in users_data:
            user = User(**u)
            db.add(user)
            users.append(user)
        db.flush()
        logger.info(f"Created {len(users)} users")

        # ── Circulars ──────────────────────────────────────────────
        circulars_data = [
            {
                "title": "5th Semester Examination Schedule November 2025",
                "url": "https://vtu.ac.in/circulars/5th-sem-nov-2025.pdf",
                "content": "5th semester examination for CSE will be held from 10th December 2025. "
                           "DBMS exam on 10/12/2025 at 10:30 AM. OS exam on 12/12/2025. "
                           "CN exam on 14/12/2025.",
                "circular_date": datetime(2025, 11, 1),
                "is_processed": True,
            },
            {
                "title": "3rd Semester Time Table December 2025",
                "url": "https://vtu.ac.in/circulars/3rd-sem-dec-2025.pdf",
                "content": "3rd semester examinations start from 5th January 2026. "
                           "Data Structures exam on 05/01/2026. Maths exam on 07/01/2026.",
                "circular_date": datetime(2025, 11, 15),
                "is_processed": True,
            },
            {
                "title": "Admission Circular 2025-26",
                "url": "https://vtu.ac.in/circulars/admission-2025.pdf",
                "content": "Applications are invited for admission to B.E./B.Tech programs for 2025-26.",
                "circular_date": datetime(2025, 10, 1),
                "is_processed": False,
            },
            {
                "title": "SEE Results November 2025",
                "url": "https://vtu.ac.in/circulars/results-nov-2025.pdf",
                "content": "Semester End Examination results for odd semester 2025 are declared.",
                "circular_date": datetime(2025, 12, 1),
                "is_processed": True,
            },
            {
                "title": "Holiday List 2026",
                "url": "https://vtu.ac.in/circulars/holidays-2026.pdf",
                "content": "List of holidays for the year 2026 for VTU affiliated colleges.",
                "circular_date": datetime(2025, 12, 15),
                "is_processed": False,
            },
        ]
        circulars = []
        for c in circulars_data:
            circ = Circular(**c, scraped_at=datetime.utcnow())
            db.add(circ)
            circulars.append(circ)
        db.flush()
        logger.info(f"Created {len(circulars)} circulars")

        # ── Exam Schedules ─────────────────────────────────────────
        base_date = datetime(2025, 12, 10)
        subjects_5_cse = [
            ("Database Management Systems", "CS501", 1),
            ("Operating Systems", "CS502", 2),
            ("Computer Networks", "CS503", 3),
            ("Software Engineering", "CS504", 4),
            ("Analysis and Design of Algorithms", "CS505", 5),
        ]
        for subj, code, day_offset in subjects_5_cse:
            exam = ExamSchedule(
                subject=subj,
                subject_code=code,
                semester=5,
                branch="CSE",
                exam_date=base_date + timedelta(days=day_offset * 2),
                exam_time="10:30 AM",
                academic_year="2025-26",
                circular_id=circulars[0].id,
            )
            db.add(exam)
        logger.info("Created 5th semester CSE exam schedule")

        # ── Subscriptions ──────────────────────────────────────────
        for user in users:
            sub = Subscription(user_id=user.id, channel=NotificationChannel.EMAIL)
            db.add(sub)
        db.flush()
        logger.info(f"Created {len(users)} subscriptions")

        db.commit()
        logger.info("✅ Seed complete!")

    except Exception as e:
        db.rollback()
        logger.error(f"Seed failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    logger.info("Seeding database...")
    seed()
